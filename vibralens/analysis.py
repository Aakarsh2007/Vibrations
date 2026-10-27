"""check_capture_quality + measure_vibration (workflow.md §B5.2–B5.4).
One call to `analyze()` produces both reports from a single decoding pass; the agent tools expose them separately."""
from __future__ import annotations

import numpy as np

from . import config, markers, signal as sig, video

T = config.T
BLOCKING = {"duplicated_frames", "blurry", "marker_too_small", "marker_lost", "ref_missing", "ref_vibrating",
            "camera_shake", "low_light", "marker_tilted", "timing_unreliable"}


def _cadence(roi_diff: np.ndarray):
    d = roi_diff[~np.isnan(roi_diff)]
    if len(d) < 40:
        return 1.0, 0.0
    best = 1.0
    for P in (2, 3, 4, 5, 8):
        ph = [d[p::P].mean() for p in range(P)]
        best = max(best, max(ph) / max(min(ph), 1e-6))
    return float(best), float(np.mean(d < 0.05 * np.median(d)))


def _thin(f, a, fmax, n=400):
    m = f <= fmax
    f, a = f[m], a[m]
    step = max(1, len(f) // n)
    return [round(float(v), 3) for v in f[::step]], [float(v) for v in a[::step]]


def analyze(path: str, marker_mm: float, rpm: float | None = None) -> dict:
    probe = video.probe_video(path)
    out = {"probe": probe, "quality": None, "measurement": None}
    if probe["timing_status"] == video.UNRELIABLE:
        return out
    t_all = video.frame_times(path, probe)
    fs = float(probe["capture_fps"])
    n_use = int(min(len(t_all), T["analysis_max_s"] * fs + 1))
    scan = markers.scan_video(path, max_frames=n_use)
    t = t_all[: scan["n_frames"]]
    q, m = assess(scan, t, fs, probe, marker_mm, rpm)
    out["quality"], out["measurement"] = q, m
    return out


def assess(scan: dict, t: np.ndarray, fs: float, probe: dict, marker_mm: float, rpm: float | None):
    Cm, Cr = scan["corners"][config.MACHINE_ID], scan["corners"][config.REF_ID]
    W, H_img = scan["frame_size"]
    q: dict = {"flags": [], "reasons": [], "metrics": {}}
    met = q["metrics"]
    flag = lambda f, r: (q["flags"].append(f), q["reasons"].append(r))

    rate_m = float(np.mean(~np.isnan(Cm).any(axis=(1, 2))))
    rate_r = float(np.mean(~np.isnan(Cr).any(axis=(1, 2))))
    met.update(detect_rate_machine=round(rate_m, 3), detect_rate_ref=round(rate_r, 3))

    dup_ratio, near_zero = _cadence(scan["roi_diff"])
    met.update(interp_ratio=round(dup_ratio, 3), near_zero_diff_frac=round(near_zero, 3))
    if near_zero > T["dup_frac_max"]:
        flag("duplicated_frames", f"{100*near_zero:.0f}% of frames repeat the previous one: this is not real slow motion")
    elif dup_ratio > T["interp_ratio_warn"]:
        flag("interpolated_suspected", "frame-to-frame motion has a repeating pattern typical of interpolated slow motion (warning only)")

    if rate_m < 0.05:
        flag("marker_lost", "machine marker (ID 1) not found; check it is in view, flat and well lit")
        return q, None
    H, hinfo = markers.plane_homography(Cm, marker_mm, fs)
    met.update(marker_px=hinfo.get("marker_px"), tilt_ratio=hinfo.get("tilt_ratio"))
    if hinfo.get("marker_px") and hinfo["marker_px"] < T["marker_px_min"]:
        flag("marker_too_small", f"marker is {hinfo['marker_px']:.0f} px wide; needs at least {T['marker_px_min']:.0f} px")
    if rate_m < T["detect_rate_min"]:
        flag("marker_lost", f"machine marker found in only {100*rate_m:.0f}% of frames")
    if hinfo.get("tilt_ratio") is not None and hinfo["tilt_ratio"] < T["tilt_ratio_min"]:
        flag("marker_tilted", "marker is viewed at a steep angle; film it face-on")

    blur = float(np.median(scan["blur"])) if len(scan["blur"]) else 0.0
    expo = float(np.nanmean(scan["roi_mean"])) if np.isfinite(scan["roi_mean"]).any() else 0.0
    clip = float(np.nanmean(scan["clip"])) if np.isfinite(scan["clip"]).any() else 0.0
    met.update(sharpness=round(blur, 4), exposure_mean=round(expo, 1), clipped_frac=round(clip, 3))
    if blur < T["blur_min"]:
        flag("blurry", "marker edges are blurred; focus on the marker and hold the phone steady")
    if expo < T["exposure_mean_min"] or expo > T["exposure_mean_max"] or clip > T["clip_frac_max"]:
        flag("low_light", "marker is too dark or over-exposed; add light or avoid direct glare")

    ref_ok = rate_r >= T["detect_rate_min"]
    if not ref_ok:
        flag("ref_missing", "reference marker (ID 7) missing; without it camera shake cannot be removed")

    if H is None or rate_m < 0.5:
        return q, None

    # --- displacement series -------------------------------------------------------------
    raw_c = np.nanmean(Cm, axis=1)                       # (N,2) px, machine centre
    if ref_ok:
        cen, res, cam = markers.compensate(Cm, Cr)
        met["ref_fit_residual_px"] = round(float(np.nanmedian(res)), 4)
        cam_u = sig.to_slots(t, cam, fs)[1]
    else:
        cen, cam_u = raw_c, None
    tu, cen_u = sig.to_slots(t, cen, fs)
    _, raw_u = sig.to_slots(t, raw_c, fs)
    _, bright_u = sig.to_slots(t, scan["roi_mean"], fs)
    seg = sig.longest_segment(cen_u)
    seg_s = (seg.stop - seg.start) / fs
    met["segment_s"] = round(seg_s, 2)
    hard = []
    if seg_s < T["min_segment_s"]:
        hard.append(f"longest continuous tracked segment is {seg_s:.1f} s (needs {T['min_segment_s']:.0f} s)")
        return q, {"result_class": "INCONCLUSIVE", "class_reasons": hard}
    px = cen_u[seg] - np.nanmedian(cen_u[seg], axis=0)
    mm = markers.to_mm(cen_u[seg], H)
    mm = mm - np.nanmedian(mm, axis=0)
    flick = sig.flicker_lines(bright_u[seg], fs)
    met["flicker_hz"] = flick
    if flick:
        q["flags"].append("flicker")

    # axis with the larger 1x response
    cands = []
    for ax in (0, 1):
        f1, src = sig.find_f1x(mm[:, ax], fs, rpm, exclude=flick)
        a1 = sig.tone(mm[:, ax], fs, f_hint=f1, rel_tol=0.02)[1] if np.isfinite(f1) else 0.0
        cands.append((a1, ax, f1, src))
    a1, ax, f1, src = max(cands)
    x_mm, x_px = mm[:, ax], px[:, ax]
    if not np.isfinite(f1):
        return q, {"result_class": "INCONCLUSIVE", "class_reasons": ["no vibration peak found in 8-60 Hz"]}
    px_amp = sig.tone(x_px, fs, f_hint=f1, rel_tol=0.02)[1]
    hm = sig.harmonics(x_mm, fs, f1)
    snr = sig.local_snr(x_mm, fs, f1, hm[1] or 0.0)
    f_lo, f_hi = sig.band(fs)
    v_band = sig.velocity_rms(x_mm, fs)
    nev = sig.noise_equivalent_velocity(x_mm, fs)
    v_corr = sig.corrected_band_rms(v_band, nev)
    dl = sig.tonal_dl(x_mm, fs, f1)
    unexpl = sig.unexplained_peaks(x_mm, fs, f1, exclude=flick)

    # --- reference / camera checks ----------------------------------------------------------
    if ref_ok and cam_u is not None:
        cs = cam_u[seg] - np.nanmedian(cam_u[seg], axis=0)
        cam_rms = float(np.sqrt(np.nanmean(np.sum(cs ** 2, axis=1))))
        r1 = sig.tone(np.nan_to_num(cs[:, ax]), fs, f_hint=f1, rel_tol=0.02)[1]
        m1 = sig.tone(raw_u[seg][:, ax] - np.nanmedian(raw_u[seg][:, ax]), fs, f_hint=f1, rel_tol=0.02)[1]
        met.update(camera_motion_rms_px=round(cam_rms, 3), ref_motion_ratio_1x=round(r1 / max(m1, 1e-9), 3))
        if cam_rms > T["camera_motion_rms_max_px"]:
            flag("camera_shake", f"camera moved {cam_rms:.1f} px RMS; use a tripod or rest the phone on something solid")
        if r1 / max(m1, 1e-9) > T["ref_moving_ratio"]:
            flag("ref_vibrating", "the reference marker (or the camera) also vibrates at the machine's frequency; "
                                  "put the reference and tripod on a different structure")
        if met.get("ref_fit_residual_px", 0) > T["ref_fit_residual_max_px"]:
            hard.append("reference marker motion is not consistent with a rigid camera movement")
        row_off = abs(np.nanmedian(Cm[:, :, 1]) - np.nanmedian(Cr[:, :, 1])) / max(H_img, 1)
        met["row_offset_frac"] = round(float(row_off), 3)
        if row_off > T["row_offset_max_frac"]:
            q["flags"].append("rolling_shutter_risk")
            q["reasons"].append("place the reference marker at the same height in the picture as the machine marker")

    side = np.nanmean(np.linalg.norm(np.roll(Cm, -1, 1) - Cm, axis=2), axis=1)
    _, side_u = sig.to_slots(t, side, fs)
    s = side_u[seg]
    if np.isfinite(s).all():
        osc = sig.tone(s - s.mean(), fs, f_hint=f1, rel_tol=0.02)[1] / s.mean()
        met["scale_osc_1x"] = round(float(osc), 5)
        if osc > T["scale_osc_max"]:
            q["flags"].append("out_of_plane_suspected")
            q["reasons"].append("part of the vibration is towards/away from the camera; a 90-degree view is needed")

    met["px_amp_1x"] = round(float(px_amp), 4)
    if px_amp < T["px_amp_reliable"]:
        q["flags"].append("amplitude_below_reliable")
        width_mm = W * hinfo["mm_per_px"]
        rec = float(np.clip(width_mm * px_amp / T["px_amp_reliable"], 80, 300))
        met["recommended_frame_width_mm"] = round(rec, 0)
    if "low_bitrate" in probe.get("flags", []):
        q["flags"].append("low_bitrate")

    hard.extend("capture quality failed: " + f for f in q["flags"] if f in BLOCKING)
    cls, why = sig.result_class(snr, px_amp, probe.get("bits_per_pixel"), probe["timing_status"], ref_ok, hard)
    fs_sp, A = sig.amp_spectrum(x_mm, fs, "hann")
    sp_f, sp_a = _thin(fs_sp, A, 0.48 * fs)
    meas = {
        "fs": fs, "band_hz": [f_lo, round(f_hi, 1)], "axis": "horizontal" if ax == 0 else "vertical",
        "f1x_hz": round(f1, 3), "f1x_rpm": round(60 * f1, 1), "f1x_source": src,
        "amp_mm": {str(k): (round(v, 6) if v is not None else None) for k, v in hm.items()},
        "px_amp_1x": round(float(px_amp), 4), "mm_per_px": round(hinfo["mm_per_px"], 5),
        "v_band_rms_mm_s": round(v_corr, 4), "v_band_raw_mm_s": round(v_band, 4), "nev_mm_s": round(nev, 4),
        "dl_mm_s": round(dl, 4), "v_1x_rms_mm_s": round(2 * np.pi * f1 * (hm[1] or 0) / np.sqrt(2), 4),
        "snr_1x": round(float(min(snr, 1e4)), 2), "unexplained_peaks_hz": unexpl,
        "result_class": cls, "class_reasons": why, "ref_mode": "similarity" if ref_ok else "none",
        "uncertainty_pct": _uncertainty(snr, hinfo, met),
        "spectrum": {"f": sp_f, "amp_mm": sp_a},
    }
    return q, meas


def _uncertainty(snr, hinfo, met) -> float:
    """Root-sum-square of the symmetric terms (workflow.md §A5.5). Compression bias is one-sided and
    handled by the LOWER_BOUND class, not by this number."""
    scale = 0.5 / 40.0                                        # ruler reading on a 40 mm marker
    tilt = 1 - (hinfo.get("tilt_ratio") or 1)
    noise = 1.0 / snr if snr > 0 else 1.0
    comp = met.get("ref_fit_residual_px", 0.0) / max(met.get("px_amp_1x", 1e-6), 1e-6) if "px_amp_1x" in met else 0.0
    expo = 0.02
    return round(100 * float(np.sqrt(scale ** 2 + tilt ** 2 + noise ** 2 + min(comp, 1.0) ** 2 + expo ** 2)), 1)

"""compare_readings: before/after comparison that refuses to compare unlike recordings.  workflow.md §B5.6"""
from __future__ import annotations

from . import config

T = config.T


def comparable(a: dict, b: dict) -> list[str]:
    """Reasons why two readings are NOT comparable (empty list = comparable)."""
    why = []
    if a.get("point_id") != b.get("point_id"):
        why.append("different measurement points")
    if a.get("view") != b.get("view"):
        why.append("different camera views (radial vs axial)")
    ma, mb = a.get("measurement") or {}, b.get("measurement") or {}
    ok = ("RELIABLE", "LOWER_BOUND")
    if ma.get("result_class") not in ok or mb.get("result_class") not in ok:
        why.append("at least one reading is not a valid measurement")
        return why
    if ma.get("axis") != mb.get("axis"):
        why.append("vibration measured along different axes")
    if abs(ma["fs"] / mb["fs"] - 1) > T["cmp_fs_tol"]:
        why.append("different frame rates (different measurement band)")
    if abs(ma["f1x_hz"] / mb["f1x_hz"] - 1) > T["cmp_f1x_tol"]:
        why.append(f"machine speed differs ({ma['f1x_rpm']:.0f} vs {mb['f1x_rpm']:.0f} rpm): load/speed not the same")
    if abs(ma["mm_per_px"] / mb["mm_per_px"] - 1) > T["cmp_scale_tol"]:
        why.append("camera distance differs a lot (different sensitivity)")
    if (ma["result_class"] == "LOWER_BOUND") != (mb["result_class"] == "LOWER_BOUND"):
        why.append("one reading is a lower bound and the other is not")
    if a.get("marker_mm") != b.get("marker_mm"):
        why.append("different marker sizes")
    return why


def compare_readings(a: dict, b: dict, asset: dict, iso: dict | None = None) -> dict:
    """a = earlier reading, b = later reading (stored reading records)."""
    why = comparable(a, b)
    ma, mb = a.get("measurement") or {}, b.get("measurement") or {}
    out = {"comparable": not why, "not_comparable_reasons": why, "a": a["reading_id"], "b": b["reading_id"],
           "table": {}, "significant_increase": False, "criterion": None, "evidence": []}
    for key in ("f1x_hz", "v_band_rms_mm_s", "v_1x_rms_mm_s", "snr_1x", "result_class", "uncertainty_pct"):
        out["table"][key] = [ma.get(key), mb.get(key)]
    out["table"]["amp_1x_mm"] = [(ma.get("amp_mm") or {}).get("1"), (mb.get("amp_mm") or {}).get("1")]
    out["spectra"] = {"a": ma.get("spectrum"), "b": mb.get("spectrum")}
    if why:
        return out
    va, vb = ma["v_band_rms_mm_s"], mb["v_band_rms_mm_s"]
    out["change_pct"] = round(100 * (vb - va) / va, 1) if va > 0 else None
    # one-sided uncertainty: the change must exceed the combined uncertainty to count
    unc = (ma["uncertainty_pct"] ** 2 + mb["uncertainty_pct"] ** 2) ** 0.5
    if iso and iso.get("applicable") and iso.get("boundary_bc"):
        bc = min(iso["boundary_bc"].values())
        # ISO 10816-3 criterion II (secondary sources): change > 25% of the zone B upper boundary
        thr = 0.25 * bc
        out["criterion"] = f"change > 25% of zone B upper boundary ({thr:.2f} mm/s), secondary-source criterion"
        sig_inc = (vb - va) > thr
    else:
        thr = T["relative_change_heuristic"]
        out["criterion"] = f"relative change > {int(thr*100)}% (team heuristic, not a standard)"
        sig_inc = va > 0 and (vb - va) / va > thr
    out["significant_increase"] = bool(sig_inc and out["change_pct"] is not None and out["change_pct"] > unc)
    if out["change_pct"] is None:
        out["evidence"].append("Baseline level is zero; relative change cannot be estimated. Record a measurable baseline.")
    elif config.AMPLITUDE_VALIDATED:
        out["evidence"].append(f"band velocity {va:.2f} -> {vb:.2f} mm/s ({out['change_pct']:+.0f}%), "
                               f"combined uncertainty ±{unc:.0f}%")
    else:  # trend mode: relative change only (absolute level not validated, gate G3)
        out["evidence"].append(f"vibration level changed by {out['change_pct']:+.0f}% "
                               f"(combined uncertainty ±{unc:.0f}%)")
    out["evidence"].append(f"1x frequency {ma['f1x_hz']:.2f} -> {mb['f1x_hz']:.2f} Hz")
    return out

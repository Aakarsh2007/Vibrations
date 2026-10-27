"""Spectral analysis of marker displacement.  workflow.md §A5.4, §B5.4
Formulas checked against known answers in feasibility/signal_check.py:
  * no linear resampling (it low-passes): frames are assigned to sensor-clock slots, short gaps
    are filled with a cubic spline, long gaps split the record;
  * tone frequency: zero-padded Hann + parabolic interpolation; tone amplitude: flat-top window;
  * band velocity RMS: Welch PSD (density) x (2*pi*f)^2 integrated over the band."""
from __future__ import annotations

import numpy as np
from scipy import signal as ss
from scipy.interpolate import CubicSpline
from scipy.ndimage import median_filter

from . import config


def to_slots(t: np.ndarray, x: np.ndarray, fs: float, max_gap: int | None = None):
    """t: (N,) physical times; x: (N,) or (N,k) with NaN for missing. Returns uniform (M,) / (M,k)."""
    max_gap = max_gap or config.T["max_gap_frames"]
    dt = 1.0 / fs
    k = np.round((t - t[0]) / dt).astype(np.int64)
    x2 = x.reshape(len(x), -1)
    out = np.full((k[-1] + 1, x2.shape[1]), np.nan)
    out[k] = x2
    tu = np.arange(len(out)) * dt
    for c in range(out.shape[1]):
        col = out[:, c]
        ok = ~np.isnan(col)
        if ok.sum() < 4:
            continue
        fill = ~ok
        col[fill] = CubicSpline(tu[ok], col[ok])(tu[fill])
        idx = np.flatnonzero(ok)
        for a, b in zip(idx[:-1], idx[1:]):
            if b - a > max_gap:
                col[a + 1:b] = np.nan
        col[: idx[0]] = np.nan
        col[idx[-1] + 1:] = np.nan
    return tu, out.reshape((len(out),) + x.shape[1:])


def longest_segment(x: np.ndarray) -> slice:
    ok = ~np.isnan(x.reshape(len(x), -1)).any(axis=1)
    best, start, cur = (0, 0), None, 0
    for i, v in enumerate(np.r_[ok, False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return slice(*best)


def amp_spectrum(x: np.ndarray, fs: float, window: str = "hann", pad: int = 1):
    x = x - np.mean(x)
    n = len(x)
    w = ss.windows.get_window(window, n, fftbins=False)
    X = np.abs(np.fft.rfft(x * w, pad * n)) * 2.0 / w.sum()
    return np.fft.rfftfreq(pad * n, 1.0 / fs), X


def tone(x: np.ndarray, fs: float, f_hint: float | None = None, fmin: float = 2.0, fmax: float | None = None,
         rel_tol: float = 0.08):
    """(frequency Hz, peak amplitude) of the strongest tone in [fmin, fmax] (or near f_hint)."""
    fmax = fmax or 0.45 * fs
    f, H = amp_spectrum(x, fs, "hann", pad=8)
    band = (f >= fmin) & (f <= fmax)
    if f_hint:
        band &= np.abs(f - f_hint) <= rel_tol * f_hint
    if not band.any():
        return float("nan"), 0.0
    k = np.flatnonzero(band)[np.argmax(H[band])]
    k = int(np.clip(k, 1, len(H) - 2))
    a, b, c = np.log(H[k - 1:k + 2] + 1e-30)
    den = a - 2 * b + c
    fpk = f[k] + (0.5 * (a - c) / den if den != 0 else 0.0) * (f[1] - f[0])
    ff, F = amp_spectrum(x, fs, "flattop", pad=8)
    kk = int(np.argmin(np.abs(ff - fpk)))
    return float(fpk), float(F[max(kk - 4, 0):kk + 5].max())


def welch_psd(x: np.ndarray, fs: float, f_lo: float):
    sos = ss.butter(4, 0.5 * f_lo, "highpass", fs=fs, output="sos")
    y = ss.sosfiltfilt(sos, x - np.mean(x))
    nper = int(min(len(y), 2.0 * fs))
    return ss.welch(y, fs, window="hann", nperseg=nper, noverlap=nper // 2, detrend="linear", scaling="density")


def band(fs: float):
    return config.T["f_lo"], min(config.T["f_hi_max"], config.T["f_hi_frac"] * fs)


def velocity_rms(x_mm: np.ndarray, fs: float, f_lo: float | None = None, f_hi: float | None = None) -> float:
    lo, hi = band(fs)
    f_lo, f_hi = f_lo or lo, f_hi or hi
    f, P = welch_psd(x_mm, fs, f_lo)
    m = (f >= f_lo) & (f <= f_hi)
    return float(np.sqrt(np.trapezoid(P[m] * (2 * np.pi * f[m]) ** 2, f[m])))


def noise_equivalent_velocity(x_mm: np.ndarray, fs: float) -> float:
    """Band RMS velocity of the local noise floor (running median of the PSD, so tones are ignored)."""
    f_lo, f_hi = band(fs)
    f, P = welch_psd(x_mm, fs, f_lo)
    win = max(5, int(10.0 / (f[1] - f[0])) | 1)          # ~10 Hz running median
    floor = median_filter(P, size=win, mode="nearest")
    m = (f >= f_lo) & (f <= f_hi)
    return float(np.sqrt(np.trapezoid(floor[m] * (2 * np.pi * f[m]) ** 2, f[m])))


def local_snr(x: np.ndarray, fs: float, f0: float, amp: float) -> float:
    f, H = amp_spectrum(x, fs, "hann")
    sel = (np.abs(f - f0) <= 5.0) & (np.abs(f - f0) >= 1.0)
    noise = np.median(H[sel]) if sel.any() else np.nan
    return float(amp / noise) if noise and noise > 0 else float("inf")


def find_f1x(x: np.ndarray, fs: float, rpm: float | None = None, exclude=()):
    """1x shaft frequency. With rpm: search ±5% around rpm/60 and 2*rpm/60. Without: strongest peak in 8-60 Hz."""
    if rpm:
        f_exp = rpm / 60.0
        c1 = tone(x, fs, f_hint=f_exp, rel_tol=config.T["rpm_tol"])
        c2 = tone(x, fs, f_hint=2 * f_exp, rel_tol=config.T["rpm_tol"])
        if c2[1] > 1.5 * c1[1]:
            return c2[0] / 2, "rpm (2x dominant)"
        return c1[0], "rpm"
    lo, hi = config.T["f1x_search"]
    f, H = amp_spectrum(x, fs, "hann", pad=8)
    m = (f >= lo) & (f <= min(hi, 0.45 * fs))
    for fx in exclude:
        m &= np.abs(f - fx) > 1.0
    if not m.any():
        return float("nan"), "none"
    f0 = float(f[np.flatnonzero(m)[np.argmax(H[m])]])
    return tone(x, fs, f_hint=f0, rel_tol=0.03)[0], "assumed (largest peak)"


def harmonics(x: np.ndarray, fs: float, f1: float) -> dict:
    out = {}
    for k in (0.5, 1, 2, 3):
        fk = k * f1
        if fk < 0.45 * fs and fk > 1.0:
            out[k] = tone(x, fs, f_hint=fk, rel_tol=config.T["harmonic_tol"])[1]
        else:
            out[k] = None
    return out


def unexplained_peaks(x: np.ndarray, fs: float, f1: float, exclude=()) -> list[float]:
    f, H = amp_spectrum(x, fs, "hann")
    floor = median_filter(H, size=max(5, int(10.0 / (f[1] - f[0])) | 1), mode="nearest")
    pk, _ = ss.find_peaks(H, height=6 * floor)
    out = []
    for p in pk:
        fp = f[p]
        if fp < config.T["f_lo"] or fp > 0.45 * fs:
            continue
        n = fp / (0.5 * f1)
        if abs(n - round(n)) * 0.5 * f1 <= max(0.3, config.T["harmonic_tol"] * fp):
            continue
        if any(abs(fp - e) < 1.0 for e in exclude):
            continue
        out.append(round(float(fp), 2))
    return out[:8]


def flicker_lines(brightness: np.ndarray, fs: float) -> list[float]:
    """Frequencies of light flicker seen in the marker-ROI mean brightness (e.g. 100 Hz on 50 Hz mains)."""
    b = brightness[~np.isnan(brightness)]
    if len(b) < 64:
        return []
    f, H = amp_spectrum(b, fs, "hann")
    rel = H / max(np.mean(b), 1e-6)
    pk, _ = ss.find_peaks(rel, height=0.005)
    return [round(float(f[p]), 2) for p in pk if f[p] > 5.0][:4]


def corrected_band_rms(v_band: float, nev: float) -> float:
    """Band RMS with the noise floor's power removed: sqrt(max(v^2 - NEV^2, 0))."""
    return float(np.sqrt(max(v_band ** 2 - nev ** 2, 0.0)))


def tonal_dl(x: np.ndarray, fs: float, f0: float) -> float:
    """Detection limit (mm/s RMS) for a tone at f0: 3 x local noise amplitude, converted to RMS velocity."""
    f, H = amp_spectrum(x, fs, "hann")
    sel = (np.abs(f - f0) <= 5.0) & (np.abs(f - f0) >= 1.0)
    noise = float(np.median(H[sel])) if sel.any() else float("nan")
    return 3 * noise * 2 * np.pi * f0 / np.sqrt(2)


def result_class(snr: float, px_amp: float, bpp: float | None, timing: str, ref_ok: bool,
                 hard_reasons: list[str]) -> tuple[str, list[str]]:
    """workflow.md §A5.5. Returns (class, reasons)."""
    if hard_reasons:
        return "INCONCLUSIVE", hard_reasons
    if not ref_ok:
        return "INCONCLUSIVE", ["no usable reference marker: camera motion cannot be removed, amplitude not reported"]
    if snr < config.T["snr_detect"]:
        return "BELOW_DETECTION_LIMIT", ["1x peak is not above the noise floor"]
    why = []
    if px_amp < config.T["px_amp_reliable"]:
        why.append(f"motion is only {px_amp:.2f} px (needs >= {config.T['px_amp_reliable']}): compression may under-read")
    if bpp is not None and bpp < config.T["bpp_reliable"]:
        why.append(f"strong compression ({bpp:.3f} bits/pixel): compression may under-read")
    if snr < config.T["snr_reliable"]:
        why.append(f"signal-to-noise {snr:.1f} (< {config.T['snr_reliable']:.0f})")
    if timing not in ("PROBABLE", "CONFIRMED"):
        return "INCONCLUSIVE", ["capture timing not established"]
    if why:
        return "LOWER_BOUND", why
    return "RELIABLE", []
    # Note: whether absolute values are *displayed* is decided separately by config.AMPLITUDE_VALIDATED
    # (gate G3). Until it is true the app shows frequency + relative trend only (diagnose.py).

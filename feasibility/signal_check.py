"""Checks the signal-processing formulas used in workflow.md §B5.4 against known synthetic answers.
Run: python feasibility/signal_check.py   (needs numpy, scipy)"""
import numpy as np
from scipy import signal as ss


def uniform(t, x, fs, max_gap_frames=3):
    """Put samples on a uniform grid.
    Linear interpolation is a low-pass filter (≈ -5% at 50 Hz with fs=240), so:
      * timestamps whose jitter is small vs the frame period are treated as uniform (no resampling);
      * missing samples (NaN / dropped frames) are filled with a cubic spline;
      * gaps longer than max_gap_frames stay NaN (caller splits segments)."""
    from scipy.interpolate import CubicSpline
    dt = 1.0 / fs
    k = np.round((t - t[0]) / dt).astype(int)            # nearest frame slot for each timestamp
    resid = (t - t[0]) - k * dt
    if np.std(resid) > 0.1 * dt or len(np.unique(k)) != len(k):
        raise ValueError("timestamps too irregular for this sensor clock; mark timing UNRELIABLE")
    xu = np.full(k[-1] + 1, np.nan); xu[k] = x
    tu = t[0] + np.arange(len(xu)) * dt
    ok = ~np.isnan(xu)
    cs = CubicSpline(tu[ok], xu[ok])
    fill = ~ok
    xu[fill] = cs(tu[fill])
    # re-blank long gaps
    idx = np.flatnonzero(ok)
    for a, b in zip(idx[:-1], idx[1:]):
        if b - a > max_gap_frames:
            xu[a + 1:b] = np.nan
    return tu, xu


def tone(x, fs, f_hint=None, fmin=5.0, fmax=None):
    """Frequency (zero-padded Hann + parabolic peak) and peak amplitude (flat-top, low scalloping)."""
    n = len(x); x = x - x.mean()
    fmax = fmax or 0.45 * fs
    pad = 8 * n
    H = np.abs(np.fft.rfft(x * np.hanning(n), pad)); f = np.fft.rfftfreq(pad, 1 / fs)
    band = (f >= fmin) & (f <= fmax)
    if f_hint:
        band &= np.abs(f - f_hint) < 0.08 * f_hint
    k = np.flatnonzero(band)[np.argmax(H[band])]
    a, b, c = np.log(H[k - 1:k + 2] + 1e-30)
    fpk = f[k] + 0.5 * (a - c) / (a - 2 * b + c) * (f[1] - f[0])
    w = ss.windows.flattop(n)
    F = np.abs(np.fft.rfft(x * w, pad)); kk = np.argmin(np.abs(f - fpk))
    amp = 2 * F[kk - 4:kk + 5].max() / w.sum()
    return fpk, amp


def velocity_rms(x_mm, fs, f_lo=10.0, f_hi=None, seg_s=2.0):
    """Band-limited RMS velocity (mm/s) from displacement (mm) via Welch PSD (density scaling)."""
    f_hi = min(f_hi or 1000.0, 0.4 * fs)
    sos = ss.butter(4, 0.5 * f_lo, "highpass", fs=fs, output="sos")
    x = ss.sosfiltfilt(sos, x_mm - np.mean(x_mm))
    f, P = ss.welch(x, fs, window="hann", nperseg=int(seg_s * fs), noverlap=int(seg_s * fs) // 2,
                    detrend="linear", scaling="density")
    Pv = P * (2 * np.pi * f) ** 2
    m = (f >= f_lo) & (f <= f_hi)
    return float(np.sqrt(np.trapezoid(Pv[m], f[m]))), (f_lo, f_hi)


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    fs, dur = 240.0, 10.0
    ok = True
    for f0, A in [(24.3, 0.02), (24.77, 0.05), (49.6, 0.01), (12.1, 0.1)]:
        # irregular timestamps (±0.3 ms jitter) + 1% dropped frames + drift + noise
        t = np.arange(0, dur, 1 / fs) + rng.normal(0, 3e-4, int(dur * fs))
        t.sort()
        x = A * np.sin(2 * np.pi * f0 * t) + 0.3 * A * np.sin(2 * np.pi * 2 * f0 * t) \
            + 0.05 * t + rng.normal(0, A * 0.05, t.size)
        x[rng.random(t.size) < 0.01] = np.nan
        tu, xu = uniform(t, x, fs)
        xu = np.nan_to_num(xu, nan=np.nanmean(xu))
        fp, ap = tone(xu, fs, f_hint=f0)
        v, band = velocity_rms(xu, fs)
        v_true = np.sqrt((2 * np.pi * f0 * A) ** 2 / 2 + ((2 * np.pi * 2 * f0 * 0.3 * A) ** 2 / 2 if 2 * f0 <= band[1] else 0))
        e_f, e_a, e_v = fp - f0, (ap - A) / A, (v - v_true) / v_true
        good = abs(e_f) < 0.02 and abs(e_a) < 0.02 and abs(e_v) < 0.05
        ok &= good
        print(f"f0={f0:6.2f} A={A:.3f}mm | f_est={fp:7.3f} (err {e_f:+.3f} Hz) | amp err {100*e_a:+5.2f}% "
              f"| v_rms={v:6.3f} vs true {v_true:6.3f} mm/s (err {100*e_v:+5.2f}%) band={band[0]:.0f}-{band[1]:.0f} Hz {'OK' if good else 'FAIL'}")
    # sanity of the textbook relation used in the doc: 2.8 mm/s RMS at 25 Hz -> peak displacement
    print("2.8 mm/s RMS @25 Hz -> peak displacement =", round(2.8 * np.sqrt(2) / (2 * np.pi * 25) * 1000, 1), "um")
    print("ALL OK" if ok else "SOME FAILED")

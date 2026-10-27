"""Gates G2/G3: compare VibraLens (camera) with a phyphox accelerometer recording made at the same time.

python eval/compare_accel.py VIDEO PHYPHOX.csv --marker-mm 40.0 [--rpm 1440] [--axis x] [--label fan-5g-speed2]

phyphox: experiment "Acceleration (without g)", export as CSV (comma). Columns: time (s), ax, ay, az (m/s^2).
Tape the phone to the stationary housing next to the marker, one axis aligned with the camera's horizontal.
Appends a row to eval/results/accel_compare.csv. Nothing is summarised here that was not measured."""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy import signal as ss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibralens import analysis, signal as sig  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("csv")
ap.add_argument("--marker-mm", type=float, required=True)
ap.add_argument("--rpm", type=float); ap.add_argument("--axis", default="auto", choices=["auto", "x", "y", "z"])
ap.add_argument("--label", default="")
a = ap.parse_args()

# ---- accelerometer ----
rows = list(csv.reader(open(a.csv, encoding="utf-8-sig")))
data = np.array([[float(v) for v in r[:4]] for r in rows[1:] if len(r) >= 4 and r[0].strip()], float)
t, acc = data[:, 0], data[:, 1:4]
fs_a = 1.0 / np.median(np.diff(t))
tu = np.arange(t[0], t[-1], 1 / fs_a)
acc_u = np.column_stack([np.interp(tu, t, acc[:, k]) for k in range(3)])   # phyphox timing is irregular
jitter = float(np.std(np.diff(t)) * fs_a)

cam = analysis.analyze(a.video, a.marker_mm, a.rpm)
m = cam["measurement"]
if not m or m["result_class"] == "INCONCLUSIVE":
    print(json.dumps({"camera": "INCONCLUSIVE", "probe": cam["probe"].get("reasons"), "quality": (cam["quality"] or {}).get("flags")}))
    sys.exit(1)
f1 = m["f1x_hz"]
f_lo, f_hi_cam = m["band_hz"]
f_hi = min(f_hi_cam, 0.4 * fs_a)          # compare in a band BOTH sensors cover


def accel_metrics(x):
    xa = x - x.mean()
    fa, amp = sig.tone(xa, fs_a, f_hint=f1, rel_tol=0.05)
    sos = ss.butter(4, 0.5 * f_lo, "highpass", fs=fs_a, output="sos")
    y = ss.sosfiltfilt(sos, xa)
    n = int(min(len(y), 2 * fs_a))
    f, P = ss.welch(y, fs_a, window="hann", nperseg=n, noverlap=n // 2, detrend="linear")
    mk = (f >= f_lo) & (f <= f_hi)
    v = float(np.sqrt(np.trapezoid(P[mk] / (2 * np.pi * f[mk]) ** 2, f[mk]))) * 1000   # m/s -> mm/s
    snr = sig.local_snr(xa, fs_a, fa, amp)
    return fa, amp, v, snr


axes = {"x": 0, "y": 1, "z": 2}
cands = [(k, *accel_metrics(acc_u[:, i])) for k, i in axes.items()] if a.axis == "auto" else \
    [(a.axis, *accel_metrics(acc_u[:, axes[a.axis]]))]
ax, fa, amp_a, v_acc, snr_a = max(cands, key=lambda c: c[2])
# camera band velocity in the same band
v_cam_same_band = None
if f_hi < f_hi_cam:
    v_cam_same_band = "camera band wider than accelerometer band: recompute needed (not comparable)"
res = {"label": a.label, "video": Path(a.video).name, "timing": cam["probe"]["timing_status"],
       "cam_f1x": f1, "acc_f1x": round(fa, 3), "f_err_hz": round(abs(f1 - fa), 3), "f_err_pct": round(100 * abs(f1 - fa) / fa, 2),
       "cam_class": m["result_class"], "cam_px_amp": m["px_amp_1x"], "cam_v_band": m["v_band_rms_mm_s"],
       "acc_v_band": round(v_acc, 4), "band_hz": [f_lo, round(f_hi, 1)], "acc_axis": ax, "acc_fs": round(fs_a, 1),
       "acc_jitter": round(jitter, 3), "acc_snr_1x": round(snr_a, 1),
       "velocity_comparable": bool(snr_a >= 10 and fs_a >= 4 * f1 and f_hi >= f_hi_cam),
       "v_err_pct": round(100 * (m["v_band_rms_mm_s"] - v_acc) / v_acc, 1) if v_acc > 0 else None,
       "note": v_cam_same_band}
print(json.dumps(res, indent=1))
out = Path(__file__).resolve().parent / "results" / "accel_compare.csv"
out.parent.mkdir(exist_ok=True)
new = not out.exists()
with open(out, "a", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(res))
    if new:
        w.writeheader()
    w.writerow(res)

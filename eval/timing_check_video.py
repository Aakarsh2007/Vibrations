"""Gate G1: check a phone's slow-motion timing with a filmed screen-flash (web/timing.html).

python eval/timing_check_video.py VIDEO --display-hz 60.0 [--make Samsung --model SM-XXXX --mode 240 --path "browser upload"]

The flashing screen is a 'display_hz / 2' square wave. Using the timebase VibraLens derives (probe_video),
the measured fundamental must be within ±1% of display_hz/2. With --make/--model the result is written to
phone_profiles.json (only if it PASSES)."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibralens import config, video  # noqa: E402
from vibralens.signal import tone  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--display-hz", type=float, required=True)
ap.add_argument("--make"); ap.add_argument("--model"); ap.add_argument("--mode", default="240")
ap.add_argument("--path", default="browser upload")
a = ap.parse_args()

p = video.probe_video(a.video)
print(json.dumps({k: p.get(k) for k in ("timing_status", "capture_fps", "time_scale", "fps_tag", "fps_pts",
                                        "timing_reason", "bits_per_pixel", "make", "model", "flags")}, indent=1))
cap = cv.VideoCapture(a.video)
b = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    g = cv.cvtColor(f, cv.COLOR_BGR2GRAY)
    h, w = g.shape
    b.append(float(g[h // 4: 3 * h // 4, w // 4: 3 * w // 4].mean()))
b = np.asarray(b)
expected = a.display_hz / 2
stored = p.get("fps_pts") or 30.0
print(f"frames={len(b)}  expected flash fundamental={expected:.3f} Hz (physical time)")
if p["timing_status"] == "UNRELIABLE":
    for cand in (240, 120, 960, 480):
        f_seen = tone(b, cand, f_hint=None, fmin=2, fmax=0.49 * cand)[0]
        print(f"  if the true capture rate were {cand} fps: fundamental = {f_seen:.3f} Hz")
    print("RESULT: FAIL (timing UNRELIABLE from the file; see candidates above to learn what this phone does)")
    sys.exit(1)
fs = p["capture_fps"]
f_meas = tone(b, fs, fmin=2, fmax=0.49 * fs)[0]
err = abs(f_meas - expected) / expected
ok = err <= 0.01
print(f"measured fundamental = {f_meas:.3f} Hz using capture fps {fs:.2f}  error = {100*err:.2f}%  ->  {'PASS' if ok else 'FAIL'}")
if ok and a.make and a.model:
    prof = video.load_profiles()
    entry = {"id": f"{a.make}-{a.model}-{a.mode}".lower().replace(" ", "-"), "make": a.make, "model": a.model,
             "mode": a.mode, "capture_fps": fs, "stored_fps": round(stored), "tag_present": bool(p.get("fps_tag")),
             "upload_path": a.path, "verified_on": time.strftime("%Y-%m-%d"), "flash_error_pct": round(100 * err, 3)}
    prof = [x for x in prof if x.get("id") != entry["id"]] + [entry]
    config.PHONE_PROFILES.write_text(json.dumps(prof, indent=1), encoding="utf-8")
    print("phone profile saved:", entry["id"])
sys.exit(0 if ok else 1)

"""Generate synthetic test recordings with KNOWN vibration (for tests, demos and the agent evaluation).
Every file produced here is synthetic and must be labelled as such wherever it is shown.

python tools/make_synthetic.py OUT_DIR            -> writes the standard scenario set
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2 as cv
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibralens.video import ffmpeg_exe  # noqa: E402

DICT = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50)


def render(out: str, *, fps=240, stored_fps=None, tag=True, dur=6.0, W=960, H=540, marker_px=150,
           marker_mm=40.0, f_vib=24.3, amp_mm=0.05, harm2=0.3, ref=True, ref_vib=0.0, shake_px=0.3,
           blur=0, noise=2.5, brightness=1.0, dup_every=1, crf=14, seed=0):
    """Machine marker (ID 1) vibrates horizontally at f_vib with amplitude amp_mm (+ 2x harmonic).
    Reference marker (ID 7) is static (or vibrates with ref_vib mm). Camera shake = low-frequency drift."""
    rng = np.random.default_rng(seed)
    SS = 2
    mm_per_px = marker_mm / marker_px
    bg = cv.resize(rng.normal(115, 22, (H // 6, W // 6)).clip(0, 255).astype(np.uint8), (W * SS, H * SS),
                   interpolation=cv.INTER_CUBIC)

    def mk(i):
        m = cv.aruco.generateImageMarker(DICT, i, marker_px * SS)
        return cv.copyMakeBorder(m, 14 * SS, 14 * SS, 14 * SS, 14 * SS, cv.BORDER_CONSTANT, value=255)

    mm_, mr_ = mk(1), mk(7)
    s = mm_.shape[0]
    pm, pr = (int(W * 0.22) * SS, int(H * 0.25) * SS), (int(W * 0.62) * SS, int(H * 0.25) * SS)
    n = int(fps * dur)
    t = np.arange(n) / fps
    vib = amp_mm * np.sin(2 * np.pi * f_vib * t) + harm2 * amp_mm * np.sin(2 * np.pi * 2 * f_vib * t + 0.6)
    rvib = ref_vib * np.sin(2 * np.pi * f_vib * t + 0.3)
    drift = np.cumsum(rng.normal(0, 0.02, (n, 2)), 0) + shake_px * np.c_[np.sin(2 * np.pi * 3.1 * t),
                                                                          np.cos(2 * np.pi * 2.3 * t)]
    sf = stored_fps or fps
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
           "-r", str(sf), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if tag:
        cmd += ["-movflags", "use_metadata_tags", "-metadata", f"com.android.capture.fps={fps}"]
    p = subprocess.Popen(cmd + [out], stdin=subprocess.PIPE)
    last = None
    for i in range(n):
        if dup_every > 1 and i % dup_every and last is not None:
            p.stdin.write(last.tobytes()); continue
        img = bg.copy()
        dx = vib[i] / mm_per_px * SS
        M = np.float32([[1, 0, pm[0] + dx], [0, 1, pm[1]]])
        cv.warpAffine(mm_, M, (W * SS, H * SS), dst=img, flags=cv.INTER_LINEAR, borderMode=cv.BORDER_TRANSPARENT)
        if ref:
            Mr = np.float32([[1, 0, pr[0] + rvib[i] / mm_per_px * SS], [0, 1, pr[1]]])
            cv.warpAffine(mr_, Mr, (W * SS, H * SS), dst=img, flags=cv.INTER_LINEAR, borderMode=cv.BORDER_TRANSPARENT)
        Mc = np.float32([[1, 0, drift[i, 0] * SS], [0, 1, drift[i, 1] * SS]])
        img = cv.warpAffine(img, Mc, (W * SS, H * SS), flags=cv.INTER_LINEAR, borderMode=cv.BORDER_REFLECT)
        f = cv.resize(img, (W, H), interpolation=cv.INTER_AREA).astype(np.float32)
        if blur:
            f = cv.GaussianBlur(f, (0, 0), blur)
        f = (f * brightness + rng.normal(0, noise, f.shape)).clip(0, 255).astype(np.uint8)
        p.stdin.write(f.tobytes())
        last = f
    p.stdin.close(); p.wait()
    truth = {"synthetic": True, "f_vib": f_vib, "amp_mm": amp_mm, "harm2": harm2, "fps": fps, "marker_mm": marker_mm,
             "v_rms_true_mm_s": float(np.sqrt((2*np.pi*f_vib*amp_mm)**2/2 + (2*np.pi*2*f_vib*harm2*amp_mm)**2/2
                                              * (2*f_vib <= 0.4*fps))),
             "px_amp_true": amp_mm / mm_per_px}
    Path(out).with_suffix(".truth.json").write_text(json.dumps(truth, indent=1))
    return truth


SCENARIOS = {
    "good_imbalance":  dict(amp_mm=0.08),
    "good_healthy":    dict(amp_mm=0.012, harm2=0.2, seed=1),
    "tiny_marker":     dict(marker_px=50, amp_mm=0.08, seed=2),
    "blurry":          dict(blur=3.0, amp_mm=0.08, seed=3),
    "no_reference":    dict(ref=False, amp_mm=0.08, seed=4),
    "ref_vibrating":   dict(ref_vib=0.05, amp_mm=0.08, seed=5),
    "slowed_no_tag":   dict(stored_fps=30, tag=False, amp_mm=0.08, seed=6),
    "slowed_with_tag": dict(stored_fps=30, tag=True, amp_mm=0.08, seed=7),
    "duplicated":      dict(dup_every=4, amp_mm=0.08, seed=8),
    "low_bitrate":     dict(crf=32, amp_mm=0.08, seed=9),
    "dark":            dict(brightness=0.18, noise=1.5, amp_mm=0.08, seed=10),
    "camera_shake":    dict(shake_px=6.0, amp_mm=0.08, seed=11),
}

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/synthetic")
    out.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(SCENARIOS)
    for name in names:
        tr = render(str(out / f"{name}.mp4"), **SCENARIOS[name])
        print(name, json.dumps(tr))

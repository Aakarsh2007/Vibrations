"""Interpolated slow-mo check against ffmpeg motion-compensated interpolation (minterpolate, mci),
which is closer to phone frame interpolation than linear blending. Still NOT a real phone.
Run: python feasibility/interp_check.py   (needs opencv-python-headless==5.0.0.93, numpy, imageio-ffmpeg)"""
import os, subprocess, tempfile
import numpy as np, cv2 as cv, imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = tempfile.mkdtemp()
W, H = 480, 270
rng = np.random.default_rng(3)
bg = cv.resize(rng.normal(110, 25, (H // 4, W // 4)).clip(0, 255).astype(np.uint8), (W, H), interpolation=cv.INTER_CUBIC)
marker = cv.aruco.generateImageMarker(cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50), 1, 80)


def frames(fps, dur=4.0, f_vib=24.3, amp=1.5, noise=2.5):
    for i in range(int(fps * dur)):
        t = i / fps
        img = bg.copy()
        M = np.float32([[1, 0, 200 + amp * np.sin(2 * np.pi * f_vib * t)], [0, 1, 95]])
        cv.warpAffine(marker, M, (W, H), dst=img, borderMode=cv.BORDER_TRANSPARENT)
        yield (img.astype(np.float32) + rng.normal(0, noise, img.shape)).clip(0, 255).astype(np.uint8)


def encode(gen, fps, out, vf=None):
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in gen:
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()


def cadence(path, n=480):
    cap = cv.VideoCapture(path); v = []
    while len(v) < n:
        ok, f = cap.read()
        if not ok: break
        v.append(cv.cvtColor(f, cv.COLOR_BGR2GRAY)[150:214, 20:84].astype(np.float64))  # static patch (no marker)
    v = np.array(v)
    var = (v - np.median(v, 0)).var((1, 2))
    best = 1.0
    for period in (2, 3, 4):
        ph = [var[p::period].mean() for p in range(period)]
        best = max(best, max(ph) / min(ph))
    return best, len(v)


real = os.path.join(TMP, "real240.mp4"); encode(frames(240), 240, real)
fake_mci = os.path.join(TMP, "fake_mci.mp4"); encode(frames(60), 60, fake_mci, "minterpolate=fps=240:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
fake_blend = os.path.join(TMP, "fake_blend.mp4"); encode(frames(60), 60, fake_blend, "minterpolate=fps=240:mi_mode=blend")
fake_dup = os.path.join(TMP, "fake_dup.mp4"); encode(frames(60), 60, fake_dup, "fps=240")
for name, p in [("real 240", real), ("60->240 motion-compensated", fake_mci), ("60->240 blend", fake_blend), ("60->240 duplicated", fake_dup)]:
    r, n = cadence(p)
    print(f"{name:30} max/min noise-variance ratio = {r:6.2f}  ({n} frames)  -> {'FLAG interpolated' if r > 1.4 else 'looks real'}")

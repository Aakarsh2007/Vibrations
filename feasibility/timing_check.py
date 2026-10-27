"""Synthetic timing check: what do OpenCV and ffprobe report for a 240 fps capture stored with
slowed (30 fps) playback timestamps, with and without an Android-style capture-fps tag?
This only exercises our probe logic on files WE generate. It does not prove behaviour of real phones.
Run: python feasibility/timing_check.py   (needs opencv-python-headless==5.0.0.93, numpy, imageio-ffmpeg)"""
import json, os, subprocess, tempfile
import numpy as np, cv2 as cv, imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = tempfile.mkdtemp()
F_TRUE, CAP_FPS, N = 24.3, 240, 960


def make(path, stored_fps, tag=None):
    """Write N frames of a dot oscillating at F_TRUE Hz in *capture* time, stored at stored_fps."""
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "320x240",
           "-r", str(stored_fps), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p"]
    if tag:
        cmd += ["-movflags", "use_metadata_tags", "-metadata", f"com.android.capture.fps={tag}"]
    p = subprocess.Popen(cmd + [path], stdin=subprocess.PIPE)
    for i in range(N):
        img = np.full((240, 320), 40, np.uint8)
        x = 160 + 30 * np.sin(2 * np.pi * F_TRUE * i / CAP_FPS)
        cv.circle(img, (int(round(x * 16)), 120 * 16), 12 * 16, 255, -1, cv.LINE_AA, shift=4)
        p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()


def ffprobe_info(path):
    """Use ffmpeg itself (imageio-ffmpeg ships no ffprobe): parse stream line + metadata from -i output."""
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True)
    lines = [l.strip() for l in r.stderr.splitlines() if "fps" in l or "capture" in l]
    return lines


def track(path):
    cap = cv.VideoCapture(path)
    xs, ts = [], []
    while True:
        ok, f = cap.read()
        if not ok: break
        ts.append(cap.get(cv.CAP_PROP_POS_MSEC) / 1000)
        g = cv.cvtColor(f, cv.COLOR_BGR2GRAY).astype(np.float64)
        m = cv.moments((g > 128).astype(np.uint8))
        xs.append(m["m10"] / m["m00"])
    return np.array(ts), np.array(xs), cap.get(cv.CAP_PROP_FPS)


def peak(x, fs):
    x = x - x.mean(); n = len(x)
    H = np.abs(np.fft.rfft(x * np.hanning(n), 8 * n)); f = np.fft.rfftfreq(8 * n, 1 / fs)
    return f[np.argmax(H[1:]) + 1]


for name, stored, tag in [("true240", 240, None), ("slowed30_tag", 30, "240"), ("slowed30_notag", 30, None)]:
    p = os.path.join(TMP, name + ".mp4"); make(p, stored, tag)
    ts, xs, cvfps = track(p)
    dt = np.median(np.diff(ts))
    print(f"\n[{name}] ffmpeg reports: {ffprobe_info(p)}")
    print(f"  OpenCV CAP_PROP_FPS={cvfps:.2f}, median frame dt from POS_MSEC={dt*1000:.3f} ms -> {1/dt:.1f} fps")
    print(f"  peak using stored timestamps: {peak(xs, 1/dt):.2f} Hz | using capture fps 240: {peak(xs, 240):.2f} Hz | true {F_TRUE} Hz")

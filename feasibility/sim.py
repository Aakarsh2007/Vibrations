"""Synthetic feasibility test: can OpenCV 5 recover sub-pixel vibration of an ArUco
marker from 240 fps video with noise, camera shake, 100 Hz flicker and H.264 compression?"""
import sys, os, tempfile
import numpy as np, cv2 as cv, imageio_ffmpeg

FPS, DUR = 240, 4.0
N = int(FPS * DUR)
W, H = 1280, 720
SS = 2  # supersampling for realistic sub-pixel rendering
MARK_PX = 140  # marker side in px (e.g. 40 mm marker -> 0.286 mm/px)
MARK_MM = 40.0
F_VIB = 24.3  # Hz (1458 rpm motor)
rng = np.random.default_rng(0)
D = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50)


def make_scene():
    bg = (rng.normal(110, 18, (H * SS // 8, W * SS // 8))).clip(0, 255).astype(np.uint8)
    bg = cv.resize(bg, (W * SS, H * SS), interpolation=cv.INTER_CUBIC)
    def mk(id_):
        m = cv.aruco.generateImageMarker(D, id_, MARK_PX * SS)
        return cv.copyMakeBorder(m, 20 * SS, 20 * SS, 20 * SS, 20 * SS, cv.BORDER_CONSTANT, value=255)
    return bg, mk(1), mk(7)


def render(bg, m_mach, m_ref, dx, dy, cam):
    img = bg.copy()
    x0, y0 = 300 * SS, 250 * SS          # machine marker (moves)
    s = m_mach.shape[0]
    # machine marker translated by sub-pixel (dx,dy) at full res: integer shift in SS grid + remainder via warp
    M = np.float32([[1, 0, dx * SS], [0, 1, dy * SS]])
    patch = cv.warpAffine(m_mach, M, (s, s), flags=cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)
    img[y0:y0 + s, x0:x0 + s] = patch
    xr, yr = 850 * SS, 300 * SS          # reference marker (static wall)
    img[yr:yr + s, xr:xr + s] = m_ref
    # whole-camera shake
    Mc = np.float32([[1, 0, cam[0] * SS], [0, 1, cam[1] * SS]])
    img = cv.warpAffine(img, Mc, (W * SS, H * SS), flags=cv.INTER_LINEAR, borderMode=cv.BORDER_REFLECT)
    return cv.resize(img, (W, H), interpolation=cv.INTER_AREA)


def synth(amp_px, shake=True, flicker=0.04, noise=2.5, codec_crf=None):
    bg, mm, mr = make_scene()
    t = np.arange(N) / FPS
    dx = amp_px * np.sin(2 * np.pi * F_VIB * t) + 0.35 * amp_px * np.sin(2 * np.pi * 2 * F_VIB * t + 0.7)
    dy = 0.5 * amp_px * np.sin(2 * np.pi * F_VIB * t + 1.1)
    cam = np.zeros((N, 2))
    if shake:  # tripod drift + 3 Hz tremor-ish, 0.6 px scale
        cam = np.cumsum(rng.normal(0, 0.02, (N, 2)), 0) + 0.3 * np.sin(2 * np.pi * 3.1 * t)[:, None]
    frames = []
    for i in range(N):
        f = render(bg, mm, mr, dx[i], dy[i], cam[i]).astype(np.float32)
        f *= 1 + flicker * np.cos(2 * np.pi * 100 * t[i])   # 100 Hz mains flicker
        f += rng.normal(0, noise, f.shape)
        frames.append(f.clip(0, 255).astype(np.uint8))
    if codec_crf is not None:
        frames = h264_roundtrip(frames, codec_crf)
    return frames, dx, dy


def h264_roundtrip(frames, crf):
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    fn = os.path.join(tempfile.gettempdir(), "vib_sim.mp4")
    import subprocess
    p = subprocess.Popen([exe, "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", fn],
                         stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()
    cap = cv.VideoCapture(fn); out = []
    while True:
        ok, f = cap.read()
        if not ok: break
        out.append(cv.cvtColor(f, cv.COLOR_BGR2GRAY))
    print(f"   h264 crf={crf}: {os.path.getsize(fn)/1e6:.1f} MB for {DUR}s, decoded {len(out)} frames")
    return out


# ---------------- measurement ----------------
def track_aruco(frames):
    p = cv.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 7
    p.cornerRefinementMinAccuracy = 0.001
    p.cornerRefinementMaxIterations = 100
    det = cv.aruco.ArucoDetector(D, p)
    out = {1: [], 7: []}; side = []
    for f in frames:
        c, ids, _ = det.detectMarkers(f)
        got = {int(i): cc.reshape(4, 2) for i, cc in zip(ids.ravel(), c)} if ids is not None else {}
        for k in out:
            out[k].append(got[k].mean(0) if k in got else [np.nan, np.nan])
        if 1 in got:
            side.append(np.mean(np.linalg.norm(np.roll(got[1], -1, 0) - got[1], axis=1)))
    return np.array(out[1]), np.array(out[7]), float(np.nanmedian(side))


def track_phase(frames, roi):
    x, y, w, h = roi
    win = cv.createHanningWindow((w, h), cv.CV_64F)
    ref = frames[0][y:y + h, x:x + w].astype(np.float64)
    res = []
    for f in frames:
        (sx, sy), _ = cv.phaseCorrelate(ref, f[y:y + h, x:x + w].astype(np.float64), win)
        res.append((sx, sy))
    return np.array(res)


def amp_at(sig, f0, fps=FPS):
    sig = sig - np.nanmean(sig)
    sig = np.nan_to_num(sig)
    n = len(sig); w = np.hanning(n)
    S = np.fft.rfft(sig * w); fr = np.fft.rfftfreq(n, 1 / fps)
    k = np.argmin(abs(fr - f0)); k = k - 2 + np.argmax(abs(S[k - 2:k + 3]))
    return 2 * abs(S[k]) / w.sum(), fr[k]


def noise_floor(sig, f0, fps=FPS):
    sig = np.nan_to_num(sig - np.nanmean(sig)); n = len(sig); w = np.hanning(n)
    S = 2 * abs(np.fft.rfft(sig * w)) / w.sum(); fr = np.fft.rfftfreq(n, 1 / fps)
    band = (fr > 5) & (fr < 110) & (abs(fr - f0) > 3) & (abs(fr - 2 * f0) > 3) & (abs(fr - 100) > 3) & (abs(fr - 140) > 3)
    return np.median(S[band])


if __name__ == "__main__":
    print("OpenCV", cv.__version__)
    crfs = [None, 18, 28] if len(sys.argv) < 2 else [None if a == "raw" else int(a) for a in sys.argv[1:]]
    for crf in crfs:
        for amp in [0.02, 0.05, 0.1, 0.3, 1.0]:
            frames, dx, dy = synth(amp, codec_crf=crf)
            mach, ref, side = track_aruco(frames)
            rel = mach - ref  # differential: removes camera shake
            a_rel, fpk = amp_at(rel[:, 0], F_VIB)
            a_raw, _ = amp_at(mach[:, 0], F_VIB)
            nf = noise_floor(rel[:, 0], F_VIB)
            # phase correlation on marker ROI minus reference ROI
            ph_m = track_phase(frames, (300 - 10, 250 - 10, 200, 200))
            ph_r = track_phase(frames, (850 - 10, 300 - 10, 200, 200))
            a_ph, _ = amp_at(ph_m[:, 0] - ph_r[:, 0], F_VIB)
            nf_ph = noise_floor(ph_m[:, 0] - ph_r[:, 0], F_VIB)
            a2, _ = amp_at(rel[:, 0], 2 * F_VIB)
            mm_px = MARK_MM / side
            v_rms = (2 * np.pi * F_VIB * a_rel * mm_px) / np.sqrt(2)  # mm/s at 1x
            print(f"crf={crf} amp={amp:5.2f}px | aruco diff={a_rel:.4f} (raw {a_raw:.4f}) peak@{fpk:.2f}Hz floor={nf:.4f} SNR={a_rel/nf:6.1f}"
                  f" 2x={a2:.4f}/{0.35*amp:.4f} | phaseCorr={a_ph:.4f} floor={nf_ph:.4f} SNR={a_ph/nf_ph:6.1f} | scale={mm_px:.3f}mm/px v1x={v_rms:.2f}mm/s", flush=True)

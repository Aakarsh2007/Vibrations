"""Marker detection, validity checks, metric scale and camera-motion compensation.  workflow.md §B5.2

The video is processed in ONE streaming pass (a 10 s 1080p clip at 240 fps would need ~5 GB as
grey frames), collecting per-frame corners plus the small ROI statistics the quality checks need."""
from __future__ import annotations

import cv2 as cv
import numpy as np

from . import config

DICT = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50)


def make_detector() -> cv.aruco.ArucoDetector:
    p = cv.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 7
    p.cornerRefinementMinAccuracy = 0.001
    p.cornerRefinementMaxIterations = 100
    return cv.aruco.ArucoDetector(DICT, p)


def _detect(det, gray, ids, last):
    """Detect inside a window around the last known positions (fast); fall back to the full frame."""
    found = {}
    if all(last.get(i) is not None for i in ids):
        pts = np.vstack([last[i] for i in ids])
        size = max(np.ptp(last[i][:, 0]) for i in ids)
        x0, y0 = np.maximum(pts.min(0) - 1.5 * size, 0).astype(int)
        x1, y1 = np.minimum(pts.max(0) + 1.5 * size, [gray.shape[1], gray.shape[0]]).astype(int)
        c, f, _ = det.detectMarkers(gray[y0:y1, x0:x1])
        if f is not None:
            for i, cc in zip(f.ravel(), c):
                found[int(i)] = cc.reshape(4, 2).astype(np.float64) + [x0, y0]
        if all(i in found for i in ids):
            return found
    c, f, _ = det.detectMarkers(gray)
    if f is not None:
        for i, cc in zip(f.ravel(), c):
            found[int(i)] = cc.reshape(4, 2).astype(np.float64)
    return found


def scan_video(path: str, max_frames: int | None = None, ids=(config.MACHINE_ID, config.REF_ID)) -> dict:
    det = make_detector()
    cap = cv.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("cannot open video")
    corners = {i: [] for i in ids}
    roi_mean, roi_diff, blur, clip = [], [], [], []
    last = {i: None for i in ids}
    prev_roi = None
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok or (max_frames and n >= max_frames):
            break
        gray = frame if frame.ndim == 2 else cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        found = _detect(det, gray, ids, last)
        for i in ids:
            q = found.get(i)
            corners[i].append(q if q is not None else np.full((4, 2), np.nan))
            if q is not None:
                last[i] = q
        m = found.get(ids[0])
        if m is not None:
            x0, y0 = np.maximum(m.min(0) - 4, 0).astype(int)
            x1, y1 = (m.max(0) + 4).astype(int)
            roi = gray[y0:y1, x0:x1]
            roi_mean.append(float(roi.mean()))
            clip.append(float(np.mean(roi >= 254)))   # saturated whites only (black marker cells are legitimately ~0)
            r = cv.resize(roi, (64, 64), interpolation=cv.INTER_AREA).astype(np.float32)
            roi_diff.append(float(np.abs(r - prev_roi).mean()) if prev_roi is not None else np.nan)
            prev_roi = r
            if n % 10 == 0:
                # contrast-normalised sharpness, computed at a fixed ROI size so it does not depend on distance
                r96 = cv.resize(roi, (96, 96), interpolation=cv.INTER_AREA).astype(np.float64)
                blur.append(float(cv.Laplacian(r96, cv.CV_64F).var() / (r96.var() + 1e-9)))
        else:
            roi_mean.append(np.nan); clip.append(np.nan); roi_diff.append(np.nan); prev_roi = None
        n += 1
    cap.release()
    C = {i: np.asarray(v, dtype=np.float64).reshape(-1, 4, 2) for i, v in corners.items()}
    for i in ids:
        C[i][~valid_quads(C[i])] = np.nan
    return {"corners": C, "roi_mean": np.asarray(roi_mean), "roi_diff": np.asarray(roi_diff),
            "blur": np.asarray(blur), "clip": np.asarray(clip), "n_frames": n,
            "frame_size": (int(gray.shape[1]), int(gray.shape[0])) if n else (0, 0)}


def valid_quads(Q: np.ndarray) -> np.ndarray:
    """Per-frame validity: complete, convex, side ratio >= 0.7, area within ±20% of the median area."""
    ok = ~np.isnan(Q).any(axis=(1, 2))
    if not ok.any():
        return ok
    side = np.linalg.norm(np.roll(Q, -1, axis=1) - Q, axis=2)
    x, y = Q[:, :, 0], Q[:, :, 1]
    area = 0.5 * np.abs(np.sum(x * np.roll(y, -1, 1) - y * np.roll(x, -1, 1), axis=1))
    med = np.nanmedian(area[ok])
    conv = np.zeros(len(Q), bool)
    conv[ok] = [cv.isContourConvex(q.astype(np.float32)) for q in Q[ok]]
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.nanmin(side, 1) / np.nanmax(side, 1)
        return ok & conv & (ratio >= 0.7) & (np.abs(area / med - 1) <= 0.2)


def plane_homography(Cm: np.ndarray, marker_mm: float, fs: float):
    """Homography image px -> marker plane mm from the median corners over the first 0.5 s."""
    head = Cm[: max(1, int(0.5 * fs))]
    ref = np.nanmedian(head, axis=0) if (~np.isnan(head).any(axis=(1, 2))).any() else np.nanmedian(Cm, axis=0)
    if np.isnan(ref).any():
        return None, {"reason": "machine marker not visible"}
    s = float(marker_mm)
    H, _ = cv.findHomography(ref, np.array([[0, 0], [s, 0], [s, s], [0, s]], np.float64))
    side = np.linalg.norm(np.roll(ref, -1, 0) - ref, axis=1)
    tilt_ratio = float(side.min() / side.max())
    info = {"tilt_ratio": round(tilt_ratio, 4), "marker_px": round(float(np.median(side)), 2),
            "mm_per_px": float(s / np.median(side))}
    if H is None or not np.isfinite(H).all() or tilt_ratio < config.T["tilt_ratio_min"]:
        info["reason"] = "invalid homography or marker tilted more than ~30 degrees"
        return None, info
    return H, info


def fit_similarity(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Exact least-squares 2-D similarity (Umeyama 1991): dst ≈ s·R·src + t. Returns a 2x3 matrix.
    (cv.estimateAffinePartial2D with RANSAC/LMEDS on only 4 points left ~0.4 px residual in our test.)"""
    ms, md = src.mean(0), dst.mean(0)
    sc, dc = src - ms, dst - md
    U, S, Vt = np.linalg.svd(dc.T @ sc / len(src))
    D = np.diag([1.0, np.sign(np.linalg.det(U) * np.linalg.det(Vt))])
    R = U @ D @ Vt
    s = np.trace(np.diag(S) @ D) / (sc ** 2).sum(1).mean()
    return np.c_[s * R, md - s * R @ ms]


def compensate(Cm: np.ndarray, Cr: np.ndarray):
    """Map the machine-marker centre into the reference frame with a per-frame similarity transform
    fitted to the 4 reference corners (handles camera translation, roll and zoom/focus breathing).
    Returns centres (N,2) px, rigid-fit residual (N,) px, camera motion (N,2) px."""
    n = len(Cm)
    # Reference pose = a REAL frame (medoid). A per-corner median mixes frames and is not a rigid shape,
    # which left ~0.4 px residual under camera roll/zoom in tests/test_core.py.
    med = np.nanmedian(Cr, axis=0)
    dist = np.nansum(np.abs(Cr - med), axis=(1, 2))
    dist[np.isnan(Cr).any(axis=(1, 2))] = np.inf
    R0 = Cr[int(np.argmin(dist))] if np.isfinite(dist).any() else med
    cen = np.full((n, 2), np.nan)
    res = np.full(n, np.nan)
    cam = np.full((n, 2), np.nan)
    for i in range(n):
        if np.isnan(Cr[i]).any() or np.isnan(Cm[i]).any():
            continue
        A = fit_similarity(Cr[i], R0)
        fit = np.c_[Cr[i], np.ones(4)] @ A.T
        res[i] = float(np.sqrt(np.mean(np.sum((fit - R0) ** 2, axis=1))))
        cen[i] = A @ np.r_[Cm[i].mean(0), 1.0]
        cam[i] = Cr[i].mean(0) - R0.mean(0)
    return cen, res, cam


def to_mm(points_px: np.ndarray, H: np.ndarray) -> np.ndarray:
    out = np.full((len(points_px), 2), np.nan)
    ok = ~np.isnan(points_px).any(axis=1)
    if ok.any():
        out[ok] = cv.perspectiveTransform(points_px[ok].reshape(-1, 1, 2), H).reshape(-1, 2)
    return out


def marker_pdf_png(marker_mm: float = 40.0, dpi: int = 300) -> np.ndarray:
    """A4 page (as an image) with machine marker ID 1, reference marker ID 7 and a 100 mm ruler bar."""
    px = lambda mm: int(round(mm / 25.4 * dpi))
    page = np.full((px(297), px(210)), 255, np.uint8)
    for k, (mid, label) in enumerate([(config.MACHINE_ID, "MACHINE (ID 1)"), (config.REF_ID, "REFERENCE (ID 7)")]):
        m = cv.aruco.generateImageMarker(DICT, mid, px(marker_mm))
        x, y = px(25 + k * 90), px(40)
        page[y:y + m.shape[0], x:x + m.shape[1]] = m
        cv.putText(page, label, (x, y - px(5)), cv.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3)
    y = px(130)
    cv.rectangle(page, (px(25), y), (px(125), y + px(4)), 0, -1)
    for mm in range(0, 101, 10):
        cv.line(page, (px(25 + mm), y + px(4)), (px(25 + mm), y + px(9)), 0, 3)
    cv.putText(page, "100 mm - check with a ruler; enter the measured black-square side in the app",
               (px(25), y + px(20)), cv.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2)
    return page

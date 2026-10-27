"""probe_video: establish the physical timebase of a (slow-motion) recording.  workflow.md Â§B5.1

Key fact (feasibility/timing_check.py): a 240 fps capture stored with 30 fps playback timestamps
reads 8x too low in both OpenCV and the container timestamps. Without independent evidence of the
capture rate the measurement must not run."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import cv2 as cv
import numpy as np

from . import config

UNRELIABLE, PROBABLE, CONFIRMED = "UNRELIABLE", "PROBABLE", "CONFIRMED"


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - server path
        exe = shutil.which("ffmpeg")
        if not exe:
            raise RuntimeError("ffmpeg not found")
        return exe


def read_metadata(path: str) -> dict:
    """Parse `ffmpeg -i` output (works with the ffmpeg shipped by imageio-ffmpeg; no ffprobe needed)."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True,
                       timeout=30)
    err = r.stderr
    meta: dict = {"tags": {}}
    for k, v in re.findall(r"^\s{4,}([A-Za-z0-9_.\-]+)\s*:\s*(.+)$", err, flags=re.M):
        meta["tags"].setdefault(k.strip(), v.strip())
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+).*?bitrate: (\d+) kb/s", err)
    if m:
        h, mi, s, br = m.groups()
        meta["duration_s"] = int(h) * 3600 + int(mi) * 60 + float(s)
        meta["bitrate_mbps"] = int(br) / 1000.0
    v = re.search(r"Stream #\S+.*?Video: (\w+).*?, (\d{2,5})x(\d{2,5}).*?(?:, ([\d.]+) fps)?", err)
    if v:
        meta["codec"] = v.group(1)
        meta["width"], meta["height"] = int(v.group(2)), int(v.group(3))
    f = re.search(r"Video:.*?, ([\d.]+) fps", err)
    meta["stream_fps"] = float(f.group(1)) if f else None
    meta["has_audio"] = "Audio:" in err
    return meta


def read_timestamps(path: str, max_frames: int | None = None) -> np.ndarray:
    """Presentation timestamp (s) of every frame as reported by OpenCV's FFmpeg backend."""
    cap = cv.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("cannot open video")
    ts = []
    while cap.grab():
        ts.append(cap.get(cv.CAP_PROP_POS_MSEC) / 1000.0)
        if max_frames and len(ts) >= max_frames:
            break
    cap.release()
    return np.asarray(ts, dtype=np.float64)


def load_profiles() -> list[dict]:
    try:
        return json.loads(config.PHONE_PROFILES.read_text(encoding="utf-8-sig"))
    except Exception:
        return []


def find_profile(tags: dict, profiles: list[dict]) -> dict | None:
    make = (tags.get("com.android.manufacturer") or tags.get("com.apple.quicktime.make") or "").lower()
    model = (tags.get("com.android.model") or tags.get("com.apple.quicktime.model") or "").lower()
    for p in profiles:
        if p.get("make", "").lower() == make and p.get("model", "").lower() == model and make:
            return p
    return None


def capture_tag(tags: dict) -> float | None:
    for k, v in tags.items():
        if k.lower().endswith("capture.fps"):
            try:
                return float(v)
            except ValueError:
                return None
    return None


def timing_status(fps_tag, fps_pts, profile):
    """Returns (status, capture_fps, time_scale, reason). real_time = pts * time_scale."""
    if not np.isfinite(fps_pts) or fps_pts <= 0:
        return UNRELIABLE, None, None, "missing or invalid frame timestamps"
    if fps_tag is not None and (not np.isfinite(fps_tag) or fps_tag <= 0):
        return UNRELIABLE, None, None, "invalid capture-rate tag"
    tol = config.T["tag_ratio_tol"]
    prof_fps = float(profile["capture_fps"]) if profile and profile.get("capture_fps") else None

    def agrees(fps):
        return prof_fps is not None and abs(fps / prof_fps - 1) < tol

    if fps_tag:
        ratio = fps_tag / fps_pts
        if abs(ratio - 1) < tol:
            return (CONFIRMED if agrees(fps_tag) else PROBABLE), fps_tag, 1.0, "capture tag matches timestamps"
        n = round(ratio)
        if n in (2, 4, 8, 16, 32) and abs(ratio - n) < tol * n:
            return (CONFIRMED if agrees(fps_tag) else PROBABLE), fps_tag, 1.0 / n, \
                f"slowed playback x{n}; capture rate from tag"
        return UNRELIABLE, None, None, "capture tag inconsistent with timestamps"
    if fps_pts >= config.T["min_capture_fps"]:
        return (CONFIRMED if agrees(fps_pts) else PROBABLE), fps_pts, 1.0, \
            "no capture tag; timestamps already at slow-motion rate"
    if profile and profile.get("stored_fps") and abs(fps_pts / float(profile["stored_fps"]) - 1) < tol and prof_fps:
        return PROBABLE, prof_fps, fps_pts / prof_fps, "re-timed file; capture rate from verified phone profile"
    return UNRELIABLE, None, None, ("timestamps show %.1f fps and no capture-rate tag: cannot tell whether "
                                    "this is real time or slowed playback" % fps_pts)


def slot_stats(ts: np.ndarray, fps: float):
    """Assign each frame to its sensor-clock slot. Returns (slots, jitter_frac, dropped_frac, dup_slots)."""
    dt = 1.0 / fps
    k = np.round((ts - ts[0]) / dt).astype(np.int64)
    resid = (ts - ts[0]) - k * dt
    jitter = float(np.std(resid) / dt) if len(ts) > 2 else 0.0
    dup = int(len(k) - len(np.unique(k)))
    dropped = float(1 - len(np.unique(k)) / (k[-1] + 1)) if len(k) else 1.0
    return k, jitter, dropped, dup


def probe_video(path: str) -> dict:
    out: dict = {"flags": [], "reasons": []}
    meta = read_metadata(path)
    out.update({k: meta.get(k) for k in ("codec", "width", "height", "bitrate_mbps", "duration_s", "stream_fps",
                                         "has_audio")})
    tags = meta["tags"]
    out["make"] = tags.get("com.android.manufacturer") or tags.get("com.apple.quicktime.make")
    out["model"] = tags.get("com.android.model") or tags.get("com.apple.quicktime.model")

    # hard limits (workflow.md Â§B7.3)
    if not out.get("codec") or out["codec"] not in ("h264", "hevc", "mpeg4"):
        return _reject(out, "unsupported_codec", f"unsupported video codec: {out.get('codec')}")
    if (out.get("width") or 0) > config.MAX_W or (out.get("height") or 0) > config.MAX_H:
        return _reject(out, "too_large", "resolution above 3840x2160")

    ts = read_timestamps(path, max_frames=config.MAX_FRAMES + 1)
    if len(ts) < 50:
        return _reject(out, "too_short", "fewer than 50 frames decoded")
    if len(ts) > config.MAX_FRAMES:
        return _reject(out, "too_many_frames", "more than 8000 frames")
    d = np.diff(ts)
    d = d[d > 0]
    fps_pts = float(1.0 / np.median(d)) if len(d) else 0.0
    fps_tag = capture_tag(tags)
    profile = find_profile(tags, load_profiles())
    status, cap_fps, scale, why = timing_status(fps_tag, fps_pts, profile)
    out.update({"fps_tag": fps_tag, "fps_pts": round(fps_pts, 3), "n_frames": int(len(ts)),
                "profile": profile.get("id") if profile else None, "timing_reason": why})
    out["timing_status"], out["capture_fps"], out["time_scale"] = status, cap_fps, scale
    if status == UNRELIABLE:
        out["flags"].append("timing_unreliable")
        out["reasons"].append(why)
        return out
    real = (ts - ts[0]) * scale
    _, jitter, dropped, dup = slot_stats(real, cap_fps)
    out.update({"jitter_frac": round(jitter, 4), "dropped_frac": round(dropped, 4),
                "duration_real_s": round(float(real[-1]), 3)})
    if jitter > config.T["jitter_max_frac"] or dup:
        out["timing_status"] = UNRELIABLE
        out["flags"].append("timing_unreliable")
        out["reasons"].append("frame timestamps are too irregular")
    elif dropped > config.T["dropped_max"]:
        out["timing_status"] = UNRELIABLE
        out["flags"].append("timing_unreliable")
        out["reasons"].append(f"{100*dropped:.1f}% of frames missing")
    elif dropped > config.T["dropped_warn"]:
        out["flags"].append("dropped_frames")
    out["bits_per_pixel"] = bits_per_pixel(out)
    if out["bits_per_pixel"] is not None and out["bits_per_pixel"] < config.T["bpp_reliable"]:
        out["flags"].append("low_bitrate")
    if out["timing_status"] != CONFIRMED:
        out["flags"].append("timing_not_confirmed")
    return out


def bits_per_pixel(p: dict):
    """Compression level independent of resolution: bits per pixel per *stored* frame."""
    try:
        return round(p["bitrate_mbps"] * 1e6 / (p["width"] * p["height"] * (p["fps_pts"] or 1)), 4)
    except (TypeError, KeyError, ZeroDivisionError):
        return None


def _reject(out, flag, reason):
    out["timing_status"] = UNRELIABLE
    out["flags"].append(flag)
    if flag != "timing_unreliable":
        out["flags"].append("timing_unreliable")
    out["reasons"].append(reason)
    return out


def frame_times(path: str, probe: dict) -> np.ndarray:
    """Physical capture times (s) for each decoded frame."""
    ts = read_timestamps(path)
    return (ts - ts[0]) * probe["time_scale"]


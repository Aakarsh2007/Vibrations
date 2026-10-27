"""Agent tools. Each tool runs deterministic code (OpenCV / numpy), updates the session, and returns a
compact JSON summary (what the LLM sees). Names and inputs match workflow.md §A4.2 / §B6.3."""
from __future__ import annotations

import hashlib
import time

from . import analysis, compare, diagnose as dg

SPECS = {
    "probe_video": ("Establish the real capture frame rate and timing reliability of the uploaded video.",
                    {"upload_id": {"type": "string"}}),
    "check_capture_quality": ("Check marker visibility/size, blur, light, camera shake and the reference marker.",
                              {"upload_id": {"type": "string"}}),
    "measure_vibration": ("Measure vibration frequency and band velocity from the marker motion.",
                          {"upload_id": {"type": "string"}, "rpm": {"type": ["number", "null"]}}),
    "diagnose": ("Apply ISO applicability rules and fault-pattern heuristics to the measurement.",
                 {"reading_id": {"type": "string"}}),
    "compare_readings": ("Compare this reading with the previous comparable reading of the same asset.",
                         {"asset_id": {"type": "string"}}),
    "request_recapture": ("Ask the technician to record again, for the given reason.",
                          {"reason_code": {"type": "string"}}),
    "ask_user": ("Ask the technician for missing information (e.g. the machine's rpm from its nameplate).",
                 {"kind": {"type": "string", "enum": ["rpm", "machine_info"]}}),
    "draft_work_order": ("Draft a maintenance work order that a human supervisor must approve.", {}),
    "finish": ("End the session.", {"outcome": {"type": "string", "enum": ["completed", "inconclusive"]}}),
}


def spec(name: str) -> dict:
    desc, props = SPECS[name]
    return {"toolSpec": {"name": name, "description": desc,
                         "inputSchema": {"json": {"type": "object", "properties": props, "required": list(props)}}}}


def _analysis(store, sess, rpm):
    """Run (or reuse) the full analysis for the current upload. Cached by input hash (idempotent retries)."""
    key = hashlib.sha256(f"{sess['upload_id']}|{sess['marker_mm']}|{rpm}".encode()).hexdigest()[:32]
    hit = store.get("analyses", key)
    if hit:
        return hit
    up = store.get("uploads", sess["upload_id"])
    t0 = time.time()
    res = analysis.analyze(store.blob_local_path(up["key"]), sess["marker_mm"], rpm)
    res["secs"] = round(time.time() - t0, 2)
    res["analysis_id"] = key
    store.put_new("analyses", key, res)
    return res


def probe_video(store, sess, inp):
    from .video import probe_video as pv
    up = store.get("uploads", sess["upload_id"])
    p = pv(store.blob_local_path(up["key"]))
    sess["probe"], sess["stage"] = p, "probed"
    return {k: p.get(k) for k in ("timing_status", "capture_fps", "timing_reason", "flags", "reasons",
                                  "bits_per_pixel", "width", "height")}


def check_capture_quality(store, sess, inp):
    res = _analysis(store, sess, sess.get("rpm"))
    sess["quality"], sess["stage"] = res["quality"] or {"flags": [], "reasons": [], "metrics": {}}, "assessed"
    sess["_measurement_cache"] = res["analysis_id"]
    q = sess["quality"]
    return {"flags": q["flags"], "reasons": q["reasons"],
            "metrics": {k: q["metrics"].get(k) for k in ("marker_px", "detect_rate_machine", "detect_rate_ref",
                                                         "sharpness", "camera_motion_rms_px", "ref_motion_ratio_1x",
                                                         "px_amp_1x")}}


def measure_vibration(store, sess, inp):
    rpm = inp.get("rpm") or sess.get("rpm")
    res = _analysis(store, sess, rpm)
    m = res["measurement"] or {"result_class": "INCONCLUSIVE", "class_reasons": ["no measurement possible"]}
    sess["measurement"], sess["stage"] = m, "measured"
    sess["quality"] = res["quality"] or sess.get("quality")
    if m.get("result_class") in ("RELIABLE", "LOWER_BOUND", "BELOW_DETECTION_LIMIT"):
        rid = f"{sess['session_id']}-{sess['upload_id']}-{rpm or 0}"
        reading = {"reading_id": rid, "workspace_id": sess["workspace_id"], "asset_id": sess["asset_id"],
                   "session_id": sess["session_id"], "upload_id": sess["upload_id"], "point_id": sess["point_id"],
                   "view": sess["view"], "marker_mm": sess["marker_mm"], "ts": time.time(), "measurement": m,
                   "timing_status": sess["probe"]["timing_status"]}
        store.put_new("readings", rid, reading)       # exactly one reading per (session, upload, rpm)
        sess["reading_id"] = rid
    return {k: m.get(k) for k in ("result_class", "class_reasons", "f1x_hz", "f1x_source", "snr_1x",
                                  "px_amp_1x", "unexplained_peaks_hz")}


def diagnose(store, sess, inp):
    asset = store.get("assets", sess["asset_id"]) or {}
    d = dg.diagnose(sess["probe"], sess["quality"] or {}, sess["measurement"], asset, sess["view"])
    sess["diagnosis"], sess["stage"] = d, "diagnosed"
    return {"iso": d["iso"]["label"], "fault": d["fault"]["pattern"] or d["fault"]["withheld_reason"],
            "fault_confidence": d["fault"]["confidence"], "ambiguous_axial": d["fault"].get("ambiguous_axial", False)}


def previous_reading(store, sess):
    cur = store.get("readings", sess["reading_id"]) if sess.get("reading_id") else None
    if not cur:
        return None, None
    prev = [r for r in store.list("readings", asset_id=sess["asset_id"], workspace_id=sess["workspace_id"])
            if r["session_id"] != sess["session_id"] and r["ts"] < cur["ts"]]
    prev.sort(key=lambda r: r["ts"], reverse=True)
    for r in prev:  # most recent comparable reading, else the most recent one (to explain why not comparable)
        if not compare.comparable(r, cur):
            return r, cur
    return (prev[0], cur) if prev else (None, cur)


def compare_readings(store, sess, inp):
    a, b = previous_reading(store, sess)
    sess["compared"] = True
    if not a:
        sess["comparison"] = None
        return {"comparable": False, "reason": "no earlier reading"}
    asset = store.get("assets", sess["asset_id"]) or {}
    c = compare.compare_readings(a, b, asset, (sess.get("diagnosis") or {}).get("iso"))
    sess["comparison"] = c
    if c.get("significant_increase") and sess.get("diagnosis"):
        sess["diagnosis"]["fault"] = dg.suspect(sess["diagnosis"]["fault"],
                                                f"significant increase vs previous comparable reading ({c['change_pct']:+.0f}%)")
    return {k: c.get(k) for k in ("comparable", "not_comparable_reasons", "change_pct", "significant_increase",
                                  "criterion")}


RUN = {"probe_video": probe_video, "check_capture_quality": check_capture_quality,
       "measure_vibration": measure_vibration, "diagnose": diagnose, "compare_readings": compare_readings}

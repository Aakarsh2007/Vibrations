"""Evidence state machine + allowed actions + deterministic rule planner.  workflow.md §B6.2

The policy decides WHICH actions are allowed in each evidence state. The LLM (agent.py) may choose among
them and explain; the rule planner always computes its own choice (fallback + evaluation baseline)."""
from __future__ import annotations

from . import config

T = config.T
# evidence states (workflow.md §A4.4)
UPLOADED, CAPTURE_ASSESSED = "UPLOADED", "CAPTURE_ASSESSED"
RECAPTURE_REQUIRED, ADDITIONAL_EVIDENCE_REQUIRED = "RECAPTURE_REQUIRED", "ADDITIONAL_EVIDENCE_REQUIRED"
VALID_MEASUREMENT, INCONCLUSIVE, DIAGNOSIS_READY = "VALID_MEASUREMENT", "INCONCLUSIVE", "DIAGNOSIS_READY"
HUMAN_APPROVAL_REQUIRED, COMPLETED = "HUMAN_APPROVAL_REQUIRED", "COMPLETED"
PAUSING = {"request_recapture", "ask_user", "draft_work_order", "finish"}

# order = priority when several capture problems exist (fix the most fundamental first)
RECAPTURE_ORDER = ["timing_unreliable", "duplicated_frames", "marker_lost", "marker_too_small", "blurry",
                   "low_light", "marker_tilted", "camera_shake", "ref_missing", "ref_vibrating"]

TEMPLATES = {  # user-facing instruction per reason code (numbers filled from tool results only)
    "timing_unreliable": "We could not establish the real slow-motion frame rate. Record again in the phone's "
                         "Slow-motion mode (240 or 120 fps) and upload the ORIGINAL file (not via WhatsApp/Telegram).",
    "duplicated_frames": "This video repeats frames, so it is not real slow motion. Use the normal Slow-motion "
                         "mode (not 'super slow-mo' or AI frame boost).",
    "marker_lost": "The machine marker (ID 1) was not visible in enough frames. Keep it fully in view, flat and lit.",
    "marker_too_small": "The marker is {marker_px:.0f} px wide; it needs at least 80 px. Move closer so the picture "
                        "is about {target_mm:.0f} mm wide.",
    "blurry": "The marker is blurred. Tap the marker to focus, lock focus, and keep the phone on a support.",
    "low_light": "The marker is too dark or over-exposed. Add light, avoid glare on the marker.",
    "marker_tilted": "The marker is seen at a steep angle. Film it face-on.",
    "camera_shake": "The camera moved {cam:.1f} px. Put the phone on a tripod or rest it on something solid that "
                    "is NOT standing on the machine's base.",
    "ref_missing": "The reference marker (ID 7) is missing. Stick it on a wall/pillar beside the machine marker, "
                   "at the same height in the picture.",
    "ref_vibrating": "The reference marker (or the camera) vibrates at the machine's frequency. Move the reference "
                     "marker and the tripod to a structure that is not connected to the machine's base.",
    "amplitude_below_reliable": "The vibration is very small in the picture ({px:.2f} px). For an amplitude value, move "
                                "closer so the picture is about {target_mm:.0f} mm wide.",
    "ninety_deg": "Part of the vibration is towards/away from the camera. Record again from 90 degrees to the side.",
    "axial": "To separate imbalance from misalignment, record again looking along the shaft (axial view), "
             "with the machine marker on the end of the motor housing.",
}


def new_session(sid, workspace_id, asset, point_id, view, marker_mm, upload_id):
    return {"session_id": sid, "workspace_id": workspace_id, "asset_id": asset["asset_id"], "point_id": point_id,
            "view": view, "marker_mm": float(marker_mm), "state": UPLOADED, "upload_id": upload_id,
            "uploads": [upload_id], "rpm": asset.get("rated_rpm"), "asked": [], "recaptures": 0,
            "evidence_requests": 0, "llm_turns": 0, "mode": "bedrock" if config.BEDROCK_MODEL_ID else "rules",
            "stage": "uploaded", "probe": None, "quality": None, "measurement": None, "reading_id": None,
            "diagnosis": None, "comparison": None, "compared": False, "pending": None, "outcome": None,
            "work_order_id": None, "version": 0, "trace": []}


def blocking_flags(sess) -> list[str]:
    flags = set((sess.get("probe") or {}).get("flags", [])) | set((sess.get("quality") or {}).get("flags", []))
    return [f for f in RECAPTURE_ORDER if f in flags]


def severe(sess) -> bool:
    d, m = sess.get("diagnosis") or {}, sess.get("measurement") or {}
    iso = d.get("iso") or {}
    if iso.get("applicable"):
        zones = set((iso.get("zone") or {}).values())
        if m.get("result_class") == "RELIABLE" and zones & {"C", "D"}:
            return True
        if m.get("result_class") == "LOWER_BOUND" and zones and zones <= {"C", "D"}:
            return True  # even the lower bound is in C/D for every possible support type
    cmp_ = sess.get("comparison") or {}
    return bool(cmp_.get("comparable") and cmp_.get("significant_increase"))


def options(sess, history_available: bool) -> list[tuple[str, dict]]:
    """Allowed (action, input) pairs for the current evidence state, rule planner's choice FIRST."""
    st, stage = sess["state"], sess["stage"]
    can_recapture = sess["recaptures"] < T["max_recaptures"]
    can_ask = sess["evidence_requests"] < T["max_evidence_requests"]
    give_up = ("finish", {"outcome": "inconclusive"})
    if st in (COMPLETED, HUMAN_APPROVAL_REQUIRED):
        return []
    if stage == "uploaded":
        return [("probe_video", {"upload_id": sess["upload_id"]})]
    if stage == "probed":
        if "timing_unreliable" in sess["probe"].get("flags", []):
            return [("request_recapture", {"reason_code": "timing_unreliable"})] if can_recapture else [give_up]
        return [("check_capture_quality", {"upload_id": sess["upload_id"]})]
    if stage == "assessed":
        blk = blocking_flags(sess)
        if blk:
            if not can_recapture:
                return [give_up]
            return [("request_recapture", {"reason_code": f}) for f in blk]
        return [("measure_vibration", {"upload_id": sess["upload_id"], "rpm": sess.get("rpm")})]
    if stage == "measured":
        m = sess["measurement"] or {}
        cls = m.get("result_class")
        if cls == "INCONCLUSIVE" or cls is None:
            return [give_up]
        opts = []
        if str(m.get("f1x_source", "")).startswith("assumed") and not sess.get("rpm") and can_ask \
                and "rpm" not in sess["asked"]:
            opts.append(("ask_user", {"kind": "rpm"}))
        if "out_of_plane_suspected" in (sess["quality"] or {}).get("flags", []) and can_recapture \
                and sess["view"] != "ninety_deg":
            opts.append(("request_recapture", {"reason_code": "ninety_deg"}))
        opts.append(("diagnose", {"reading_id": sess["reading_id"]}))
        return opts
    if stage == "diagnosed":
        if history_available and not sess["compared"]:
            return [("compare_readings", {"asset_id": sess["asset_id"]})]
        if severe(sess):
            return [("draft_work_order", {})]
        opts = []
        fault = (sess["diagnosis"] or {}).get("fault") or {}
        if fault.get("ambiguous_axial") and sess["view"] != "axial" and can_recapture:
            opts.append(("request_recapture", {"reason_code": "axial"}))
        opts.append(("finish", {"outcome": "completed"}))
        return opts
    return [give_up]


def rule_planner(sess, history_available: bool):
    o = options(sess, history_available)
    return o[0] if o else None


def instruction(reason: str, sess) -> str:
    q = (sess.get("quality") or {}).get("metrics", {})
    vals ={"marker_px": q.get("marker_px") or 0, "target_mm": q.get("recommended_frame_width_mm") or 150,
            "cam": q.get("camera_motion_rms_px") or 0, "px": q.get("px_amp_1x") or 0}
    if reason == "marker_too_small" and q.get("marker_px"):
        # frame width that makes the marker 100 px wide, assuming the same resolution
        frame_w_px = (sess.get("probe") or {}).get("width") or 1920
        vals["target_mm"] = sess["marker_mm"] * frame_w_px / 100.0
    try:
        return TEMPLATES[reason].format(**vals)
    except Exception:
        return TEMPLATES.get(reason, reason)

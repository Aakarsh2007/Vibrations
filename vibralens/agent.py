"""Agent runner: perception (OpenCV tools) -> decision (LLM within policy, or rule planner) -> action.
workflow.md §B6. The LLM sees a compact, current evidence summary each turn and may only call actions the
policy allows now; arguments are validated; any failure falls back to the rule planner (logged)."""
from __future__ import annotations

import json
import logging
import re
import secrets
import time

from . import config, policy, tools

log = logging.getLogger("vibralens.agent")
SYSTEM = (
    "You are VibraLens, a vibration-screening assistant for maintenance technicians. "
    "Each turn, call exactly ONE of the tools you are given; the list is already restricted to what is allowed now. "
    "Choose the action that best resolves the open evidence problem shown in the evidence summary. "
    "Never state, estimate or change numbers; the app shows all values from the tools. "
    "Never claim ISO compliance or a confirmed fault. If evidence is weak, ask for better evidence or finish as "
    "inconclusive. Never control machinery. Before the tool call, write ONE short sentence a technician understands "
    "explaining why you chose this action.")

_brt = None


def _bedrock():
    global _brt
    if _brt is None:
        import boto3
        from botocore.config import Config
        _brt = boto3.client("bedrock-runtime", region_name=config.BEDROCK_REGION,
                            config=Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=30))
    return _brt


def evidence_summary(sess) -> dict:
    p, q, m, d = sess.get("probe") or {}, sess.get("quality") or {}, sess.get("measurement") or {}, sess.get("diagnosis") or {}
    return {"stage": sess["stage"], "view": sess["view"], "rpm_known": bool(sess.get("rpm")),
            "recaptures_used": sess["recaptures"], "recaptures_max": config.T["max_recaptures"],
            "timing": {k: p.get(k) for k in ("timing_status", "timing_reason", "flags")} if p else None,
            "quality_flags": q.get("flags"), "quality_reasons": q.get("reasons"),
            "measurement": {k: m.get(k) for k in ("result_class", "class_reasons", "f1x_source", "snr_1x",
                                                  "unexplained_peaks_hz")} if m else None,
            "iso": (d.get("iso") or {}).get("label"), "fault": (d.get("fault") or {}).get("pattern"),
            "comparison": {k: (sess.get("comparison") or {}).get(k) for k in ("comparable", "significant_increase")}
            if sess.get("comparison") else None}


def strip_numbers(note: str, evidence: dict) -> str:
    """Remove digits the LLM wrote that do not appear in the evidence (no invented numbers reach the UI)."""
    ev = json.dumps(evidence)
    return re.sub(r"\d+(?:\.\d+)?", lambda mm: mm.group(0) if mm.group(0) in ev else "…", note)[:300]


def llm_choose(sess, opts):
    """Ask the LLM to pick one allowed action. Returns (action, input, note) or None."""
    names = list(dict.fromkeys(a for a, _ in opts))
    ev = evidence_summary(sess)
    msg = {"role": "user", "content": [{"text": "Evidence summary (from OpenCV tools):\n" + json.dumps(ev) +
                                        "\nAllowed actions now: " + ", ".join(names)}]}
    r = _bedrock().converse(modelId=config.BEDROCK_MODEL_ID, system=[{"text": SYSTEM}], messages=[msg],
                            toolConfig={"tools": [tools.spec(n) for n in names], "toolChoice": {"any": {}}},
                            inferenceConfig={"maxTokens": 400, "temperature": 0})
    content = r["output"]["message"]["content"]
    uses = [c["toolUse"] for c in content if "toolUse" in c]
    note = " ".join(c.get("text", "") for c in content).strip()
    if len(uses) != 1:
        return None
    u = uses[0]
    # validate: the action and its key argument must match an allowed option
    for a, inp in opts:
        if a != u["name"]:
            continue
        if a == "request_recapture" and u["input"].get("reason_code") != inp.get("reason_code"):
            continue
        return a, inp, strip_numbers(note, ev)
    return None


def trace(sess, **kw):
    entry = {"ts": round(time.time(), 3), "step": len(sess["trace"]) + 1, **kw}
    sess["trace"].append(entry)
    log.info(json.dumps({"session": sess["session_id"], **entry}))


def step(store, sess) -> dict:
    """Advance the session until it pauses (needs the user / approval) or completes. Bounded."""
    for _ in range(40):  # hard bound on actions per job (tool steps + decisions)
        if sess["state"] in (policy.COMPLETED, policy.HUMAN_APPROVAL_REQUIRED) or sess.get("pending"):
            return sess
        hist = bool(sess.get("reading_id")) and tools.previous_reading(store, sess)[0] is not None
        opts = policy.options(sess, hist)
        if not opts:
            return sess
        rule = opts[0]
        choice, mode, note, err = rule, "rules", "", None
        t0 = time.time()
        if sess["mode"] == "bedrock" and len(opts) > 1 and sess["llm_turns"] < config.T["max_llm_turns"]:
            try:
                sess["llm_turns"] += 1
                got = llm_choose(sess, opts)
                if got:
                    choice, mode, note = (got[0], got[1]), "bedrock", got[2]
                else:
                    err = "policy_override: invalid or disallowed LLM choice"
            except Exception as e:  # throttling, no access, timeout -> rule planner for the rest of the session
                err = f"fallback: {type(e).__name__}"
                sess["mode"] = "rules"
        action, inp = choice
        state_before = sess["state"]
        result = None
        if action in tools.RUN:
            result = tools.RUN[action](store, sess, inp)
            sess["state"] = _state_after(sess)
        else:
            _pause(store, sess, action, inp)
        trace(sess, state_before=state_before, state_after=sess["state"], allowed=[a for a, _ in opts],
              rule_choice=rule[0], chosen=action, input=inp, mode=mode, agreed=(action == rule[0] and inp == rule[1]),
              note=note, error=err, latency_ms=int(1000 * (time.time() - t0)), result=result)
    sess["outcome"] = "inconclusive"
    sess["state"] = policy.COMPLETED
    return sess


def _state_after(sess) -> str:
    st = sess["stage"]
    if st == "probed":
        return policy.RECAPTURE_REQUIRED if "timing_unreliable" in sess["probe"].get("flags", []) else policy.CAPTURE_ASSESSED
    if st == "assessed":
        return policy.RECAPTURE_REQUIRED if policy.blocking_flags(sess) else policy.CAPTURE_ASSESSED
    if st == "measured":
        cls = (sess["measurement"] or {}).get("result_class")
        return policy.INCONCLUSIVE if cls in (None, "INCONCLUSIVE") else policy.VALID_MEASUREMENT
    if st == "diagnosed":
        return policy.DIAGNOSIS_READY
    return sess["state"]


def _pause(store, sess, action, inp):
    if action == "request_recapture":
        code = inp["reason_code"]
        sess["recaptures"] += 1
        sess["pending"] = {"kind": "recapture", "reason_code": code, "instruction": policy.instruction(code, sess),
                           "view": {"axial": "axial", "ninety_deg": "ninety_deg"}.get(code, sess["view"])}
        sess["state"] = policy.RECAPTURE_REQUIRED
    elif action == "ask_user":
        sess["evidence_requests"] += 1
        sess["asked"].append(inp["kind"])
        sess["pending"] = {"kind": "ask", "ask": inp["kind"],
                           "instruction": "Enter the machine's rated speed (rpm) from its nameplate."
                           if inp["kind"] == "rpm" else "Enter machine type, coupling and rated power."}
        sess["state"] = policy.ADDITIONAL_EVIDENCE_REQUIRED
    elif action == "draft_work_order":
        wo_id = f"{sess['session_id']}-wo"
        token = secrets.token_urlsafe(32)
        import hashlib
        wo = {"wo_id": wo_id, "workspace_id": sess["workspace_id"], "asset_id": sess["asset_id"],
              "session_id": sess["session_id"], "status": "PENDING", "created": time.time(),
              "expires_at": time.time() + 3600 * config.T["approval_hours"],
              "token_hash": hashlib.sha256(token.encode()).hexdigest(),
              "summary": _wo_summary(sess), "notify_state": "NONE", "audit": []}
        if store.put_new("workorders", wo_id, wo):       # at most one work order per session
            sess["_new_token"] = token                    # handed to the notifier once, never stored in clear
        sess["work_order_id"] = wo_id
        sess["state"] = policy.HUMAN_APPROVAL_REQUIRED
        sess["pending"] = {"kind": "approval", "instruction": "Waiting for a supervisor to approve the work order."}
    elif action == "finish":
        sess["outcome"] = inp.get("outcome", "completed")
        sess["state"] = policy.COMPLETED
        sess["pending"] = None


def _wo_summary(sess):
    m, d, c = sess.get("measurement") or {}, sess.get("diagnosis") or {}, sess.get("comparison") or {}
    ev = [f"1x {m.get('f1x_hz')} Hz ({m.get('f1x_rpm')} rpm), result class {m.get('result_class')}",
          (d.get("iso") or {}).get("label"), (d.get("fault") or {}).get("pattern")]
    ev += c.get("evidence", []) if c else []
    return {"evidence": [e for e in ev if e], "recommended_action":
            "Inspect the machine (balance, alignment, mounting bolts) at the next planned stop; "
            "confirm with a contact measurement before major work."}


def resume_with_evidence(sess, kind, upload_id=None, answer=None):
    """Apply user evidence to a paused session (idempotency is handled by the caller)."""
    pend = sess.get("pending") or {}
    if pend.get("kind") == "recapture" and kind == "video" and upload_id:
        sess.update(upload_id=upload_id, stage="uploaded", state=policy.UPLOADED, probe=None, quality=None,
                    measurement=None, reading_id=None, diagnosis=None, comparison=None, compared=False,
                    view=pend.get("view", sess["view"]), pending=None)
        sess["uploads"].append(upload_id)
    elif pend.get("kind") == "ask" and kind == "answer" and answer:
        if pend.get("ask") == "rpm":
            try:
                rpm = float(answer.get("rpm"))
            except (TypeError, ValueError, AttributeError):
                raise ValueError("rpm must be a number")
            if not 60 <= rpm <= 30000:
                raise ValueError("rpm must be between 60 and 30000")
            sess["rpm"] = rpm
        sess.update(stage="assessed", state=policy.CAPTURE_ASSESSED, pending=None, measurement=None,
                    diagnosis=None, comparison=None, compared=False)
    else:
        raise ValueError("this session is not waiting for that kind of evidence")
    trace(sess, state_before="paused", state_after=sess["state"], chosen="user_evidence", input={"kind": kind},
          mode="user", agreed=True, note="", error=None, latency_ms=0, result=None)
    return sess

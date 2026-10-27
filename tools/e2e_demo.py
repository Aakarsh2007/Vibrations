"""End-to-end check against a running server: the 10-step demo flow (workflow.md §B14.3) on the samples.
python tools/e2e_demo.py [BASE_URL]   (server must run with VL_DEV=1 to read the approval link from the dev outbox)"""
import json
import sys
import time
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=60)
tok = c.post("/api/workspaces").json()["workspace_token"]
H = {"Authorization": f"Bearer {tok}"}


def run(name):
    r = c.post(f"/api/samples/{name}/run", headers={**H, "Idempotency-Key": str(uuid.uuid4())})
    r.raise_for_status()
    return r.json()["session_id"]


def wait(sid, limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = c.get(f"/api/sessions/{sid}", headers=H).json()
        if not s["busy"]:
            return s
        time.sleep(2)
    raise TimeoutError(sid)


def show(title, s):
    m = s.get("measurement") or {}
    print(f"\n=== {title}: state={s['state']} outcome={s.get('outcome')} mode={s['mode']}")
    print("  pending:", (s.get("pending") or {}).get("instruction"))
    if m:
        print(f"  f1x={m.get('f1x_hz')} Hz class={m.get('result_class')} v_band={m.get('v_band_rms_mm_s')} snr={m.get('snr_1x')}")
    if s.get("diagnosis"):
        print("  iso:", s["diagnosis"]["iso"]["label"]); print("  fault:", s["diagnosis"]["fault"]["pattern"] or s["diagnosis"]["fault"]["withheld_reason"])
    if s.get("comparison"):
        print("  comparison:", json.dumps({k: s["comparison"].get(k) for k in ("comparable", "change_pct", "significant_increase", "criterion")}))
    print("  trace:", " -> ".join(f"{t['chosen']}" for t in s["trace"]))


def answer_rpm(s, rpm=1458):
    if (s.get("pending") or {}).get("kind") == "ask":
        c.post(f"/api/sessions/{s['session_id']}/evidence", headers={**H, "Idempotency-Key": str(uuid.uuid4())},
               json={"type": "answer", "answer": {"rpm": rpm}}).raise_for_status()
        time.sleep(2)
        return wait(s["session_id"])
    return s


t_all = time.time()
s1 = answer_rpm(wait(run("healthy-fan"))); show("healthy baseline (after rpm answer)", s1)
s2 = answer_rpm(wait(run("fan-added-mass"))); show("added mass (after rpm answer)", s2)
s3 = wait(run("bad-capture")); show("bad capture", s3)
s4 = wait(run("timing-problem")); show("timing problem", s4)
assert s1["state"] == "COMPLETED" and abs(s1["measurement"]["f1x_hz"] - 24.3) < 0.02
assert s2["state"] == "HUMAN_APPROVAL_REQUIRED" and s2["comparison"]["significant_increase"]
assert s3["pending"]["reason_code"] == "marker_too_small"
assert s4["pending"]["reason_code"] == "timing_unreliable"
assert not any(t["chosen"] == "measure_vibration" for t in s4["trace"])

# agent asked for a recapture on the bad capture -> provide better evidence (the good recording) and continue
if (s3.get("pending") or {}).get("kind") == "recapture":
    up = c.post(f"/api/samples/fan-added-mass/run", headers={**H, "Idempotency-Key": str(uuid.uuid4())})  # creates an upload in this workspace
    # find that upload id via its session, then re-use it as evidence for s3
    sid_tmp = up.json()["session_id"]; wait(sid_tmp)
    upload_id = c.get(f"/api/sessions/{sid_tmp}", headers=H).json()["evidence_used"][0]
    k = str(uuid.uuid4())
    c.post(f"/api/sessions/{s3['session_id']}/evidence", headers={**H, "Idempotency-Key": k},
           json={"type": "video", "upload_id": upload_id}).raise_for_status()
    dup = c.post(f"/api/sessions/{s3['session_id']}/evidence", headers={**H, "Idempotency-Key": k},
                 json={"type": "video", "upload_id": upload_id}).json()
    print("\nduplicate evidence request replayed:", dup.get("replayed"))
    assert dup.get("replayed") is True
    time.sleep(2)
    s3b = wait(s3["session_id"]); show("bad capture after new evidence", s3b)

# approval flow for the work order (if one was drafted)
if s2.get("work_order_id"):
    out = c.get("/api/dev/outbox", headers=H).json()
    link = [o for o in out if o["wo_id"] == s2["work_order_id"]][0]["link"]
    token = link.split("#t=")[1]
    pv = c.post("/api/approvals/preview", json={"token": token}).json()
    print("\napproval preview:", pv["status"], pv["summary"]["evidence"][:2])
    d = c.post("/api/approvals/decide", json={"token": token, "decision": "approve", "approver_name": "Demo Supervisor"})
    print("decision:", d.json())
    assert d.json()["status"] == "APPROVED"
    d2 = c.post("/api/approvals/decide", json={"token": token, "decision": "reject", "approver_name": "Someone else"})
    print("second decision rejected:", d2.status_code, d2.json().get("detail"))
    assert d2.status_code == 409
    print("session after approval:", c.get(f"/api/sessions/{s2['session_id']}", headers=H).json()["outcome"])
print(f"\nTOTAL {time.time()-t_all:.0f} s")

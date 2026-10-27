"""API security / idempotency / approval tests (workflow.md Â§B7). Worker disabled; LocalStore in a temp dir."""
import importlib
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VL_WORKER", "0")
    from vibralens import config, store
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BACKEND", "local")
    store._store = None
    import vibralens.api as api
    importlib.reload(api)
    with TestClient(api.app) as c:
        yield c, store.get_store()
    store._store = None


def ws(c):
    t = c.post("/api/workspaces").json()["workspace_token"]
    return {"Authorization": "Bearer " + t}


def upload(c, h, data=b"\0" * 4096):
    u = c.post("/api/uploads", json={"kind": "video", "content_type": "video/mp4", "size": len(data)}, headers=h).json()
    r = c.put(u["url"], content=data, headers={"Content-Type": "video/mp4"})
    assert r.status_code == 200, r.text
    return u["upload_id"]


def test_auth_required(client):
    c, _ = client
    assert c.get("/api/assets").status_code == 401
    assert c.get("/api/assets", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_photo_cannot_be_analyzed_as_video(client):
    c, _ = client
    h = ws(c)
    a = c.post("/api/assets", json={"name": "M1"}, headers=h).json()
    u = c.post("/api/uploads", json={"kind": "photo", "content_type": "image/png", "size": 4096}, headers=h).json()
    assert c.put(u["url"], content=b"0" * 4096, headers={"Content-Type": "image/png"}).status_code == 200
    r = c.post("/api/sessions", json={"asset_id": a["asset_id"], "upload_id": u["upload_id"], "marker_mm": 40},
               headers={**h, "Idempotency-Key": "photo-session-123"})
    assert r.status_code == 415


def test_history_reports_validation_mode(client):
    c, _ = client
    h = ws(c)
    a = c.post("/api/assets", json={"name": "M1"}, headers=h).json()
    from vibralens import config
    assert c.get(f"/api/assets/{a['asset_id']}", headers=h).json()["display_mode"] == (
        "absolute" if config.AMPLITUDE_VALIDATED else "trend")


def test_aws_upload_target_uses_region(monkeypatch):
    import boto3
    from vibralens import config, store
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setattr(config, "AWS_REGION", "ap-southeast-2")
    monkeypatch.setattr(config, "BUCKET", "vibralens-upload-test")
    target = store.AwsStore().upload_target("raw/w/u.mp4", "video/mp4", 100000)
    assert "s3.ap-southeast-2.amazonaws.com" in target["url"]


def test_workspace_isolation(client):
    c, _ = client
    h1, h2 = ws(c), ws(c)
    a = c.post("/api/assets", json={"name": "M1"}, headers=h1).json()
    assert c.get(f"/api/assets/{a['asset_id']}", headers=h2).status_code == 404
    assert c.get("/api/assets", headers=h2).json() == []
    uid = upload(c, h1)
    r = c.post("/api/sessions", json={"asset_id": a["asset_id"], "upload_id": uid, "marker_mm": 40},
               headers={**h2, "Idempotency-Key": "k-12345678"})
    assert r.status_code == 404


def test_upload_limits_and_signature(client):
    c, _ = client
    h = ws(c)
    assert c.post("/api/uploads", json={"kind": "video", "content_type": "text/html", "size": 5000}, headers=h).status_code == 415
    assert c.post("/api/uploads", json={"kind": "video", "content_type": "video/mp4", "size": 400 * 2**20}, headers=h).status_code == 413
    u = c.post("/api/uploads", json={"kind": "video", "content_type": "video/mp4", "size": 5000}, headers=h).json()
    bad = u["url"].replace("sig=", "sig=0")
    assert c.put(bad, content=b"\0" * 5000, headers={"Content-Type": "video/mp4"}).status_code == 403


def test_session_idempotent(client):
    c, st = client
    h = ws(c)
    a = c.post("/api/assets", json={"name": "M1"}, headers=h).json()
    uid = upload(c, h)
    body = {"asset_id": a["asset_id"], "upload_id": uid, "marker_mm": 40}
    r1 = c.post("/api/sessions", json=body, headers={**h, "Idempotency-Key": "same-key-123"}).json()
    r2 = c.post("/api/sessions", json=body, headers={**h, "Idempotency-Key": "same-key-123"}).json()
    assert r1["session_id"] == r2["session_id"] and r2["replayed"]
    assert len(st.list("jobs", session_id=r1["session_id"])) == 1
    report = c.get(f"/api/sessions/{r1['session_id']}/report", headers=h)
    assert report.status_code == 200
    assert report.json()["runtime"]["opencv"].startswith("5.")
    assert "workspace_token" not in report.text and "token_hash" not in report.text
    assert c.get(f"/api/sessions/{r1['session_id']}/report", headers=ws(c)).status_code == 404


def test_incomplete_upload_rejected(client):
    c, _ = client
    h = ws(c)
    a = c.post("/api/assets", json={"name": "M1"}, headers=h).json()
    u = c.post("/api/uploads", json={"kind": "video", "content_type": "video/mp4", "size": 5000}, headers=h).json()
    r = c.post("/api/sessions", json={"asset_id": a["asset_id"], "upload_id": u["upload_id"], "marker_mm": 40},
               headers={**h, "Idempotency-Key": "k-abcdefgh"})
    assert r.status_code == 409


def test_approval_single_use_post_only(client):
    c, st = client
    import hashlib
    tok = "t" * 43
    st.put_new("sessions", "s1", {"session_id": "s1", "workspace_id": "w", "state": "HUMAN_APPROVAL_REQUIRED"})
    st.put_new("workorders", "s1-wo", {"wo_id": "s1-wo", "session_id": "s1", "workspace_id": "w", "status": "PENDING",
                                       "created": time.time(), "expires_at": time.time() + 3600,
                                       "token_hash": hashlib.sha256(tok.encode()).hexdigest(),
                                       "summary": {"evidence": ["x"], "recommended_action": "y"}, "audit": []})
    assert c.get("/api/approvals/decide").status_code in (404, 405)            # GET never changes state
    assert c.post("/api/approvals/preview", json={"token": tok}).json()["status"] == "PENDING"
    r = c.post("/api/approvals/decide", json={"token": tok, "decision": "approve", "approver_name": "Supervisor"})
    assert r.json()["status"] == "APPROVED"
    r2 = c.post("/api/approvals/decide", json={"token": tok, "decision": "reject", "approver_name": "Someone"})
    assert r2.status_code == 409                                               # single use
    wo = st.get("workorders", "s1-wo")
    assert len(wo["audit"]) == 1 and wo["audit"][0]["approver_name"] == "Supervisor"
    assert st.get("sessions", "s1")["state"] == "COMPLETED"
    assert c.post("/api/approvals/preview", json={"token": "x" * 43}).status_code == 404


def test_expired_approval(client):
    c, st = client
    import hashlib
    tok = "e" * 43
    st.put_new("sessions", "s2", {"session_id": "s2", "workspace_id": "w"})
    st.put_new("workorders", "s2-wo", {"wo_id": "s2-wo", "session_id": "s2", "workspace_id": "w", "status": "PENDING",
                                       "created": 0, "expires_at": time.time() - 1,
                                       "token_hash": hashlib.sha256(tok.encode()).hexdigest(),
                                       "summary": {"evidence": [], "recommended_action": ""}, "audit": []})
    r = c.post("/api/approvals/decide", json={"token": tok, "decision": "approve", "approver_name": "Sup"})
    assert r.status_code == 409 and "expired" in r.json()["detail"]


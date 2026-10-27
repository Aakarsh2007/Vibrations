"""FastAPI app (workflow.md Ã‚Â§B5.11, Ã‚Â§B7). Run: uvicorn vibralens.api:app --port 8000"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal
from contextlib import asynccontextmanager

import cv2 as cv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, config, jobs, markers, policy
from .store import Conflict, get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
@asynccontextmanager
async def lifespan(app):
    stop = jobs.start_worker_thread() if os.environ.get("VL_WORKER", "1") == "1" else None
    try:
        yield
    finally:
        if stop is not None:
            stop.set()


app = FastAPI(title="VibraLens", version="0.1.0", lifespan=lifespan)
WEB = config.ROOT / "web"
SAMPLES = config.ROOT / "samples"
DEMO_WS = "demo"
_stop = None


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    if config.ORIGIN_SECRET and request.headers.get("x-origin-secret") != config.ORIGIN_SECRET \
            and request.url.path != "/healthz":
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                                               "script-src 'self' 'unsafe-inline'; connect-src 'self' https://*.amazonaws.com; "
                                               "frame-ancestors 'none'")
    return resp


# ---------------- auth: capability-token workspaces (workflow.md Ã‚Â§B7.4) ----------------
def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def workspace(authorization: str = Header(default="")) -> str:
    tok = authorization.removeprefix("Bearer ").strip()
    if not tok:
        raise HTTPException(401, "missing workspace token")
    ws = get_store().get("workspaces", _h(tok))
    if not ws:
        raise HTTPException(401, "unknown workspace token")
    return ws["workspace_id"]


@app.post("/api/workspaces")
def create_workspace():
    tok = secrets.token_urlsafe(32)
    wid = uuid.uuid4().hex
    get_store().put_new("workspaces", _h(tok), {"workspace_id": wid, "created": time.time()})
    return {"workspace_token": tok, "workspace_id": wid}


# ---------------- assets ----------------
MACHINE_TYPES = ["electric_motor", "fan_blower", "compressor", "conveyor", "rotordynamic_pump",
                 "reciprocating_engine", "submerged_pump", "screw_compressor", "other", "unknown"]


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    machine_type: str = "unknown"
    coupling: str = "unknown"
    rated_kw: float | None = Field(default=None, ge=0, le=100000)
    rated_rpm: float | None = Field(default=None, ge=60, le=30000)
    support: str = "unknown"


@app.get("/api/assets")
def list_assets(ws: str = Depends(workspace)):
    return sorted(get_store().list("assets", workspace_id=ws), key=lambda a: a["created"])


@app.post("/api/assets")
def create_asset(a: AssetIn, ws: str = Depends(workspace)):
    if a.machine_type not in MACHINE_TYPES or a.coupling not in ("flexible", "rigid", "close-coupled", "unknown") \
            or a.support not in ("rigid", "flexible", "unknown"):
        raise HTTPException(422, "invalid machine_type / coupling / support")
    aid = uuid.uuid4().hex[:12]
    item = {"asset_id": aid, "workspace_id": ws, "created": time.time(), **a.model_dump()}
    get_store().put_new("assets", aid, item)
    return item


def _own(coll, id_, ws):
    it = get_store().get(coll, id_)
    if not it or it.get("workspace_id") != ws:
        raise HTTPException(404, f"{coll[:-1]} not found")
    return it


@app.get("/api/assets/{aid}")
def get_asset(aid: str, ws: str = Depends(workspace)):
    a = _own("assets", aid, ws)
    rd = sorted(get_store().list("readings", asset_id=aid, workspace_id=ws), key=lambda r: r["ts"])
    for r in rd:
        r["measurement"] = {k: v for k, v in r["measurement"].items() if k != "spectrum"}
    return {"asset": a, "readings": rd,
            "display_mode": "absolute" if config.AMPLITUDE_VALIDATED else "trend"}


@app.get("/api/assets/{aid}/compare")
def compare_two(aid: str, a: str, b: str, ws: str = Depends(workspace)):
    from . import compare
    _own("assets", aid, ws)
    ra, rb = _own("readings", a, ws), _own("readings", b, ws)
    if ra["asset_id"] != aid or rb["asset_id"] != aid:
        raise HTTPException(404, "reading not found")
    if ra["ts"] > rb["ts"]:
        ra, rb = rb, ra
    return compare.compare_readings(ra, rb, get_store().get("assets", aid))


# ---------------- uploads (presigned; workflow.md Ã‚Â§B7.3) ----------------
class UploadIn(BaseModel):
    kind: Literal["video", "photo"] = "video"
    content_type: str
    size: int = Field(gt=1024)


@app.post("/api/uploads")
def create_upload(u: UploadIn, ws: str = Depends(workspace)):
    allowed = config.ALLOWED_VIDEO_TYPES if u.kind == "video" else config.ALLOWED_PHOTO_TYPES
    limit = config.MAX_VIDEO_BYTES if u.kind == "video" else config.MAX_PHOTO_BYTES
    if u.content_type not in allowed:
        raise HTTPException(415, f"content type must be one of {sorted(allowed)}")
    if u.size > limit:
        raise HTTPException(413, f"file larger than {limit // 2**20} MB")
    uid = uuid.uuid4().hex
    ext = {"video/mp4": "mp4", "video/quicktime": "mov", "image/jpeg": "jpg", "image/png": "png"}[u.content_type]
    key = f"raw/{ws}/{uid}.{ext}"
    st = get_store()
    st.put_new("uploads", uid, {"upload_id": uid, "workspace_id": ws, "key": key, "content_type": u.content_type,
                                "max_bytes": limit, "created": time.time()})
    return {"upload_id": uid, **st.upload_target(key, u.content_type, limit)}


@app.put("/api/local-upload")
async def local_upload(request: Request, key: str, ct: str, max: int, exp: int, sig: str):
    st = get_store()
    if config.BACKEND != "local" or not st.verify(f"put:{key}:{ct}:{max}:{exp}", sig, exp):
        raise HTTPException(403, "invalid or expired upload URL")
    if request.headers.get("content-type", "").split(";")[0] != ct:
        raise HTTPException(415, "content type does not match the upload URL")
    tmp = Path(st.blob_local_path(key) + ".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(tmp, "wb") as f:
        async for chunk in request.stream():
            n += len(chunk)
            if n > max:
                f.close(); tmp.unlink(missing_ok=True)
                raise HTTPException(413, "file too large")
            f.write(chunk)
    if n < 1024:
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "file too small")
    os.replace(tmp, st.blob_local_path(key))   # the object appears only when complete (like S3)
    return {"ok": True, "bytes": n}


@app.get("/api/blob")
def blob(key: str, exp: int, sig: str):
    st = get_store()
    if config.BACKEND != "local" or not st.verify(f"get:{key}:{exp}", sig, exp):
        raise HTTPException(403, "invalid or expired link")
    return FileResponse(st.blob_local_path(key))


def _checked_upload(upload_id: str, ws: str) -> dict:
    st = get_store()
    up = st.get("uploads", upload_id)
    if not up or up["workspace_id"] != ws:
        raise HTTPException(404, "upload not found")
    if up["content_type"] not in config.ALLOWED_VIDEO_TYPES:
        raise HTTPException(415, "a video upload is required for analysis")
    size = st.blob_exists(up["key"])
    if not size:
        raise HTTPException(409, "upload not complete; please retry the upload")
    if size > up["max_bytes"]:
        raise HTTPException(413, "file too large")
    return up


def _rate_limit(ws: str):
    recent = [j for j in get_store().list("jobs", workspace_id=ws) if j["created"] > time.time() - 3600]
    if len(recent) >= config.JOBS_PER_HOUR and ws != DEMO_WS:
        raise HTTPException(429, "too many analyses this hour; try again later")


# ---------------- sessions ----------------
class SessionIn(BaseModel):
    asset_id: str
    upload_id: str
    point_id: str = Field(default="P1", max_length=40)
    view: str = "radial"
    marker_mm: float = Field(ge=10, le=200)


@app.post("/api/sessions")
def create_session(s: SessionIn, ws: str = Depends(workspace), idempotency_key: str = Header(min_length=8, max_length=80)):
    st = get_store()
    sid = _h(f"{ws}:{idempotency_key}")[:24]
    existing = st.get("sessions", sid)
    if existing:
        return {"session_id": sid, "replayed": True}
    asset = _own("assets", s.asset_id, ws)
    _checked_upload(s.upload_id, ws)
    if s.view not in ("radial", "axial", "ninety_deg"):
        raise HTTPException(422, "invalid view")
    _rate_limit(ws)
    sess = policy.new_session(sid, ws, asset, s.point_id, s.view, s.marker_mm, s.upload_id)
    if st.put_new("sessions", sid, sess):
        jobs.enqueue(st, f"{sid}-0", sid, ws)
    return {"session_id": sid, "replayed": False}


class EvidenceIn(BaseModel):
    type: str
    upload_id: str | None = None
    answer: dict | None = None


@app.post("/api/sessions/{sid}/evidence")
def add_evidence(sid: str, e: EvidenceIn, ws: str = Depends(workspace),
                 idempotency_key: str = Header(min_length=8, max_length=80)):
    st = get_store()
    sess = _own("sessions", sid, ws)
    job_id = f"{sid}-{_h(idempotency_key)[:12]}"
    if st.get("jobs", job_id):
        return {"session_id": sid, "replayed": True}
    if e.upload_id:
        _checked_upload(e.upload_id, ws)
    _rate_limit(ws)
    try:
        def fn(s):
            if not s.get("pending") or s["pending"]["kind"] == "approval":
                raise ValueError("this session is not waiting for evidence")
            return agent.resume_with_evidence(s, e.type, e.upload_id, e.answer)
        st.update("sessions", sid, fn, expect_version=sess["version"])
    except Conflict:
        raise HTTPException(409, "session changed; refresh and retry")
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    jobs.enqueue(st, job_id, sid, ws)
    return {"session_id": sid, "replayed": False}


def _public_session(sess: dict) -> dict:
    st = get_store()
    out = {k: sess.get(k) for k in ("session_id", "asset_id", "point_id", "view", "state", "stage", "pending",
                                    "outcome", "recaptures", "mode", "error", "work_order_id", "rpm")}
    out["probe"] = sess.get("probe")
    out["quality"] = sess.get("quality")
    out["measurement"] = sess.get("measurement")
    out["diagnosis"] = sess.get("diagnosis")
    out["comparison"] = sess.get("comparison")
    out["trace"] = [{k: t.get(k) for k in ("step", "state_before", "state_after", "allowed", "rule_choice",
                                            "chosen", "input", "mode", "agreed", "note", "error", "latency_ms")}
                    for t in sess.get("trace", [])]
    out["evidence_used"] = sess.get("uploads", [])
    out["display_mode"] = "absolute" if config.AMPLITUDE_VALIDATED else "trend"
    if sess.get("work_order_id"):
        wo = st.get("workorders", sess["work_order_id"]) or {}
        out["work_order"] = {k: wo.get(k) for k in ("status", "summary", "created", "expires_at", "audit")}
    jobs_ = [j for j in st.list("jobs", session_id=sess["session_id"])]
    out["busy"] = any(j["status"] in ("QUEUED", "RUNNING") for j in jobs_)
    return out


@app.get("/api/sessions/{sid}")
def get_session(sid: str, ws: str = Depends(workspace)):
    return _public_session(_own("sessions", sid, ws))


@app.get("/api/sessions/{sid}/report")
def session_report(sid: str, ws: str = Depends(workspace)):
    """Portable evidence with no workspace credentials or approval token."""
    session = _public_session(_own("sessions", sid, ws))
    report = {"project": "VibraLens", "schema_version": 1, "generated_at": time.time(),
              "runtime": {"opencv": cv.__version__, "backend": config.BACKEND},
              "validation": {"amplitude_validated": config.AMPLITUDE_VALIDATED,
                             "notice": "Synthetic evaluation only; field accuracy has not been established. "
                                       "Internal amplitude estimates are uncalibrated unless independently validated."},
              "session": session}
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="vibralens-{sid}.json"',
                                         "Cache-Control": "no-store"})


@app.get("/api/sessions")
def list_sessions(ws: str = Depends(workspace)):
    ss = get_store().list("sessions", workspace_id=ws)
    return [{k: s.get(k) for k in ("session_id", "asset_id", "state", "outcome")} for s in ss]


# ---------------- approvals (POST only; token single-use, hashed, expiring) ----------------
class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class DecisionIn(TokenIn):
    decision: str
    approver_name: str = Field(min_length=2, max_length=80)
    comment: str = Field(default="", max_length=500)


def _wo_by_token(tok: str):
    h = _h(tok)
    for w in get_store().list("workorders", token_hash=h):
        return w
    raise HTTPException(404, "invalid link")


@app.post("/api/approvals/preview")
def approval_preview(t: TokenIn):
    w = _wo_by_token(t.token)
    expired = w["expires_at"] < time.time()
    return {"status": "EXPIRED" if (expired and w["status"] == "PENDING") else w["status"],
            "summary": w["summary"], "created": w["created"], "expires_at": w["expires_at"]}


@app.post("/api/approvals/decide")
def approval_decide(d: DecisionIn, request: Request):
    if d.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve or reject")
    w = _wo_by_token(d.token)
    st = get_store()
    now = time.time()

    def fn(x):
        if x["status"] != "PENDING":
            raise ValueError("this work order was already decided")
        if x["expires_at"] < now:
            raise ValueError("this approval link has expired")
        x["status"] = "APPROVED" if d.decision == "approve" else "REJECTED"
        x["audit"] = x.get("audit", []) + [{"ts": now, "decision": x["status"], "approver_name": d.approver_name,
                                            "comment": d.comment,
                                            "ip_hash": _h(request.client.host if request.client else "")[:16],
                                            "user_agent": request.headers.get("user-agent", "")[:120]}]
        return x
    try:
        w = st.update("workorders", w["wo_id"], fn)
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    st.update("sessions", w["session_id"], lambda s: {**s, "state": policy.COMPLETED, "pending": None,
                                                      "outcome": f"work order {w['status'].lower()}"})
    logging.getLogger("vibralens.audit").info(json.dumps({"wo": w["wo_id"], "decision": w["status"]}))
    return {"status": w["status"]}


@app.get("/api/dev/outbox")
def dev_outbox(ws: str = Depends(workspace)):
    if os.environ.get("VL_DEV") != "1":
        raise HTTPException(404, "not found")
    return get_store().list("outbox", workspace_id=ws)


# ---------------- samples, markers, health ----------------
@app.get("/api/samples")
def samples():
    meta = SAMPLES / "samples.json"
    return json.loads(meta.read_text(encoding="utf-8-sig")) if meta.exists() else []


@app.post("/api/samples/{name}/run")
def run_sample(name: str, ws: str = Depends(workspace), idempotency_key: str = Header(min_length=8, max_length=80)):
    items = {s["name"]: s for s in samples()}
    if name not in items:
        raise HTTPException(404, "unknown sample")
    s = items[name]
    st = get_store()
    aid = f"sample-{ws[:8]}-{s['asset']['name'].lower().replace(' ', '-')}"[:60]
    if not st.get("assets", aid):
        st.put_new("assets", aid, {"asset_id": aid, "workspace_id": ws, "created": time.time(), **s["asset"]})
    uid = _h(f"{ws}:{name}:{idempotency_key}")[:24]
    key = f"raw/{ws}/{uid}.mp4"
    if not st.blob_exists(key):
        st.blob_put_file(key, SAMPLES / s["file"])
    st.put_new("uploads", uid, {"upload_id": uid, "workspace_id": ws, "key": key, "content_type": "video/mp4",
                                "max_bytes": config.MAX_VIDEO_BYTES, "created": time.time(), "sample": name})
    return create_session(SessionIn(asset_id=aid, upload_id=uid, point_id=s.get("point_id", "P1"),
                                    view=s.get("view", "radial"), marker_mm=s["marker_mm"]), ws, idempotency_key)


@app.get("/api/markers.png")
def markers_png():
    ok, buf = cv.imencode(".png", markers.marker_pdf_png())
    return Response(buf.tobytes(), media_type="image/png",
                    headers={"Content-Disposition": "attachment; filename=vibralens-markers-A4-300dpi.png"})


@app.get("/healthz")
def healthz():
    info = cv.getBuildInformation()
    hal = [l.strip() for l in info.splitlines() if "HAL" in l or "Parallel framework" in l][:6]
    return {"ok": True, "opencv": cv.__version__, "opencv_file": cv.__file__, "hal": hal, "backend": config.BACKEND,
            "agent_model": config.BEDROCK_MODEL_ID or "rule planner", "amplitude_validated": config.AMPLITUDE_VALIDATED}


@app.exception_handler(Exception)
async def _err(request: Request, exc: Exception):
    logging.getLogger("vibralens.api").exception("unhandled")
    return JSONResponse({"detail": "internal error"}, status_code=500)


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")



"""Persisted jobs with leases (workflow.md §B7.1). A job advances one session until it pauses or completes.
The job record is written BEFORE processing; a worker claims it with a lease; heartbeats extend the lease;
a crashed worker's job is re-claimed after the lease expires; attempts are bounded."""
from __future__ import annotations

import logging
import os
import threading
import time
import traceback
import uuid

from . import agent, config, metrics, notify, policy
from .store import Conflict, get_store

log = logging.getLogger("vibralens.jobs")
LEASE_S, HEARTBEAT_S, MAX_ATTEMPTS = 120, 30, 3
WORKER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:6]}"


def enqueue(store, job_id, session_id, workspace_id) -> bool:
    """Idempotent: the same job_id is only created once."""
    return store.put_new("jobs", job_id, {"job_id": job_id, "session_id": session_id, "workspace_id": workspace_id,
                                          "status": "QUEUED", "attempts": 0, "lease_owner": None, "lease_until": 0,
                                          "created": time.time(), "updated": time.time(), "error": None})


def _claim(store, job):
    now = time.time()

    def fn(j):
        claimable = j["status"] == "QUEUED" or (j["status"] == "RUNNING" and j["lease_until"] < now)
        if not claimable:
            return None
        if j["attempts"] >= MAX_ATTEMPTS:
            j.update(status="FAILED", error=j.get("error") or "too many attempts", updated=now)
            return j
        j.update(status="RUNNING", lease_owner=WORKER_ID, lease_until=now + LEASE_S, attempts=j["attempts"] + 1,
                 updated=now)
        return j
    try:
        j = store.update("jobs", job["job_id"], fn, expect_version=job.get("version", 0))
    except Conflict:
        return None
    return j if j.get("status") == "RUNNING" and j.get("lease_owner") == WORKER_ID else None


def _heartbeat(store, job_id, stop: threading.Event):
    while not stop.wait(HEARTBEAT_S):
        try:
            store.update("jobs", job_id, lambda j: {**j, "lease_until": time.time() + LEASE_S}
                         if j.get("lease_owner") == WORKER_ID and j["status"] == "RUNNING" else None)
        except Exception:
            pass


def run_job(store, job):
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(store, job["job_id"], stop), daemon=True).start()
    try:
        sess = store.get("sessions", job["session_id"])
        sess = agent.step(store, sess)
        token = sess.pop("_new_token", None)
        store.update("sessions", sess["session_id"], lambda _: sess)
        if token:
            notify.work_order_created(store, sess, token)
        status = "DONE"
        err = None
        metrics.put("AgentSteps", len(sess.get("trace", [])))
        metrics.put("Recaptures", sess.get("recaptures", 0))
        if any(t.get("error", "") and str(t.get("error")).startswith("fallback") for t in sess.get("trace", [])):
            metrics.put("FallbackActivations")
    except Exception as e:  # retried (bounded) by re-claim after lease expiry / attempts
        log.error("job %s failed: %s", job["job_id"], traceback.format_exc())
        metrics.put("JobFailures")
        status, err = "QUEUED", f"{type(e).__name__}: {e}"
    finally:
        stop.set()

    def fin(j):
        if status == "QUEUED" and j["attempts"] >= MAX_ATTEMPTS:
            j.update(status="FAILED", error=err)
            store.update("sessions", j["session_id"],
                         lambda s: {**s, "state": policy.COMPLETED, "outcome": "inconclusive", "pending": None,
                                    "error": "processing failed repeatedly; please try a new recording"})
        else:
            j.update(status=status, error=err, lease_owner=None, lease_until=0)
        j["updated"] = time.time()
        return j
    store.update("jobs", job["job_id"], fin)


def worker_loop(stop: threading.Event, poll_s: float = 1.0):
    store = get_store()
    log.info("worker %s started", WORKER_ID)
    while not stop.is_set():
        now = time.time()
        todo = [j for j in store.list("jobs") if j["status"] == "QUEUED"
                or (j["status"] == "RUNNING" and j["lease_until"] < now)]
        todo.sort(key=lambda j: j["created"])
        for j in todo:
            got = _claim(store, j)
            if got:
                run_job(store, got)
                break
        else:
            stop.wait(poll_s)


def start_worker_thread() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=worker_loop, args=(stop,), daemon=True, name="vl-worker").start()
    return stop

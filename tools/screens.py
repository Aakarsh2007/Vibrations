"""Create demo sessions over HTTP and screenshot the UI with headless Edge (for checking the UI and for the report).
python tools/screens.py OUT_DIR"""
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screens")
out.mkdir(parents=True, exist_ok=True)
c = httpx.Client(base_url=BASE, timeout=60)
tok = c.post("/api/workspaces").json()["workspace_token"]
H = {"Authorization": f"Bearer {tok}"}


def wait(sid):
    while c.get(f"/api/sessions/{sid}", headers=H).json()["busy"]:
        time.sleep(2)
    return c.get(f"/api/sessions/{sid}", headers=H).json()


def run(name):
    return c.post(f"/api/samples/{name}/run", headers={**H, "Idempotency-Key": str(uuid.uuid4())}).json()["session_id"]


def rpm(sid):
    c.post(f"/api/sessions/{sid}/evidence", headers={**H, "Idempotency-Key": str(uuid.uuid4())}, json={"type": "answer", "answer": {"rpm": 1458}})
    time.sleep(2)
    return wait(sid)


a =wait(run("healthy-fan")); a = rpm(a["session_id"])
b = wait(run("fan-added-mass")); b = rpm(b["session_id"])
bad = wait(run("bad-capture"))


def shot(name, frag, w=1280, h=2200):
    url = f"{BASE}/#/ws/{tok}/{frag}"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                    "--virtual-time-budget=8000", f"--screenshot={out.resolve() / name}", url],
                   capture_output=True, timeout=120)
    print("saved", out / name)


shot("home.png", "", h=1100)
shot("session_bad_capture.png", f"session/{bad['session_id']}", h=1500)
shot("session_fault_vs_baseline.png", f"session/{b['session_id']}")
shot("mobile_session.png", f"session/{b['session_id']}", w=390, h=2600)
print("sessions:", a["session_id"], b["session_id"], bad["session_id"])

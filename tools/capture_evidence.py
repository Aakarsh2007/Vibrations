"""Export sanitized local session traces; no capability or approval tokens are included."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibralens import config
import cv2

items = config.DATA_DIR / "items"
sessions = []
for p in sorted((items / "sessions").glob("*.json")):
    s = json.loads(p.read_text(encoding="utf-8"))
    sessions.append({k: s.get(k) for k in (
        "state", "outcome", "mode", "probe", "quality", "measurement", "comparison", "trace")})
orders = [json.loads(p.read_text(encoding="utf-8")) for p in (items / "workorders").glob("*.json")]
report = {"opencv": cv2.__version__, "backend": config.BACKEND,
          "validation": "synthetic inputs only; not field-validated", "sessions": sessions,
          "approval_results": [{"status": w["status"], "decisions": len(w.get("audit", []))} for w in orders]}
out = config.ROOT / "eval" / "results" / "agent_demo.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Saved {len(sessions)} sessions and {len(orders)} approval results to {out}")

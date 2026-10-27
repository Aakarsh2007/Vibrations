"""Run analysis on every synthetic scenario and print a compact table vs ground truth."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibralens import analysis  # noqa: E402

d = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/synthetic")
rows = []
for mp4 in sorted(d.glob("*.mp4")):
    truth = json.loads(mp4.with_suffix(".truth.json").read_text())
    t0 = time.time()
    r = analysis.analyze(str(mp4), truth["marker_mm"])
    p, q, m = r["probe"], r["quality"] or {}, r["measurement"] or {}
    row = {"name": mp4.stem, "timing": p["timing_status"], "fps": p.get("capture_fps"),
           "q_flags": q.get("flags"), "class": m.get("result_class"),
           "f1x": m.get("f1x_hz"), "f_true": truth["f_vib"],
           "amp1x_mm": (m.get("amp_mm") or {}).get("1"), "amp_true": truth["amp_mm"],
           "v_band": m.get("v_band_rms_mm_s"), "v_true": round(truth["v_rms_true_mm_s"], 3),
           "dl": m.get("dl_mm_s"), "snr": m.get("snr_1x"), "unc%": m.get("uncertainty_pct"),
           "sharp": (q.get("metrics") or {}).get("sharpness"), "secs": round(time.time() - t0, 1)}
    rows.append(row)
    print(json.dumps(row), flush=True)
Path(d / "results.json").write_text(json.dumps(rows, indent=1))

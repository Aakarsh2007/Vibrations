# VibraLens

Phone-camera vibration screening for machines that have no sensors. It uses **OpenCV 5** and runs on **AWS**.
Entry for the OpenCV AI Competition 2026 (main track + Agentic Vision path).

[GitHub source](https://github.com/Aakarsh2007/Vibrations) · [Live application](https://dhfpmgo5xkqhh.cloudfront.net/) · [Judge guide and demo](https://dhfpmgo5xkqhh.cloudfront.net/judge.html)

**Solo entrant: Aakarsh Saxena.** Start with the [submission checklist](docs/SUBMISSION.md),
[technical report](docs/TECHNICAL_REPORT.md), [architecture](docs/ARCHITECTURE.md), and
[demo script](docs/DEMO_SCRIPT.md). **[Open the deployed app](https://dhfpmgo5xkqhh.cloudfront.net/)** or
the **[judge guide, video and downloadable submission](https://dhfpmgo5xkqhh.cloudfront.net/judge.html)**.
All four synthetic workflows passed on AWS; see [deployment evidence](docs/AWS_DEPLOYMENT.md).
No real-machine accuracy has been established. A narrated demonstration is also available locally in
`video/VibraLens-demo.mp4`; SNS supervisor email confirmation remains an operational step.

A technician sticks a printed ArUco marker on a machine's stationary housing, records 10 s of slow motion and uploads it. VibraLens then:
1. **checks the timing**, i.e. establishes the real capture frame rate (a 240 fps clip saved with 30 fps timing would otherwise read 8× too low);
2. **checks capture quality**: marker size, blur, light, camera shake, reference marker, duplicated frames;
3. **measures**:
   - sub-pixel ArUco corners;
   - similarity-transform camera-motion compensation;
   - metric scale from the marker homography;
   - 1× shaft frequency and harmonics;
   - band velocity RMS (Welch);
   - detection limit;
   - a **result class**: `RELIABLE` / `LOWER_BOUND` / `BELOW_DETECTION_LIMIT` / `INCONCLUSIVE`;
4. **interprets**:
   - ISO 20816-3 applicability (scope rules read from the standard's official preview);
   - an estimated zone, only where the standard applies;
   - the spectrum shape;
   - comparison with earlier comparable readings;
5. **acts through an agent**:
   - a deterministic evidence-state policy decides which actions are allowed;
   - an LLM on Amazon Bedrock (or the rule planner) picks the next action: re-capture with a precise instruction, ask for the rpm, compare, draft a work order, or finish as inconclusive;
   - work orders need a human approval (single-use, expiring token, POST-only, audited).

Until the amplitude has been validated against an accelerometer (gate G3 in `workflow.md`), the app runs in **frequency + relative-trend mode**: it shows no absolute mm/s values and no ISO zones.

## Quick start (local, no AWS)
```bash
python -m venv .venv && .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements-lock.txt
python -m pytest -q tests
uvicorn vibralens.api:app --port 8000                  # open http://localhost:8000 → "Try a sample"
```
- Synthetic test videos with known vibration: `python tools/make_synthetic.py OUT_DIR`.
- Batch check against ground truth: `python tools/run_scenarios.py OUT_DIR`.
- Full demo flow over HTTP (needs `VL_DEV=1` on the server): `python tools/e2e_demo.py`.
- Four bundled videos: `python tools/run_scenarios.py samples` writes `samples/results.json`.
- Download a session's portable JSON evidence from **Download evidence report** on its analysis page.
- Build a clean judge archive: `python tools/package_submission.py` → `dist/VibraLens-submission.zip`.
- Devpost's 35 MB attachment: `python tools/package_judges.py` → `dist/VibraLens-Judges.zip` (about 6.1 MB). This includes the report, code, evaluation and demo, with the four large input videos available separately in this repository.
- Optional container: `docker build -t vibralens .` then `docker run --rm -p 8000:8000 -v vibralens-data:/data vibralens`.
  The Docker build and ARM64 installation still need verification on the target host.

## Real-world validation tools
- **Timing (gate G1):** open `/timing.html` on a laptop, film it in slow motion, then run `python eval/timing_check_video.py VIDEO --display-hz 60 --make … --model …`.
- **Accelerometer comparison (gates G2/G3):** record with phyphox at the same time, then run `python eval/compare_accel.py VIDEO phyphox.csv --marker-mm 40.0`. Results are appended to `eval/results/accel_compare.csv`.

## Deploy (AWS; verify account credits and service costs)
See [infra/deploy.md](infra/deploy.md). It uses CloudFormation ([infra/stack.yaml](infra/stack.yaml)) for S3, DynamoDB, SNS, IAM, logs, CloudFront and an alarm, plus one Graviton (ARM64) EC2 instance running `opencv-python-headless==5.0.0.93`.

## Layout
| Path | Contents |
|---|---|
| `vibralens/video.py` | Timing |
| `vibralens/markers.py` | Detection + compensation |
| `vibralens/signal.py` | Spectral maths |
| `vibralens/analysis.py` | Quality + measurement |
| `vibralens/diagnose.py` | ISO / pattern rules |
| `vibralens/compare.py` | Comparison |
| `vibralens/policy.py` | Evidence states |
| `vibralens/agent.py` | Bedrock / rules |
| `vibralens/tools.py` | Agent tools |
| `vibralens/jobs.py` | Leased jobs |
| `vibralens/store.py` | Local / AWS storage |
| `vibralens/api.py` | FastAPI |
| `web/` | UI, approval page, timing test page |
| `tests/` | Unit + API tests |
| `tools/`, `eval/` | Generators, evaluation |
| `feasibility/` | The original feasibility studies |

## Honest status
See `workflow.md`, §0 Build status. Everything measured so far is on **synthetic** recordings. Real-phone and accelerometer results will appear in `eval/results/` only after the team records them.

# VibraLens — evidence-driven vibration screening

**Author:** Aakarsh Saxena (solo entrant)  
**Competition:** OpenCV AI Competition 2026, powered by AWS  
**Intended paths:** Main competition and Agentic Vision. No COOL award claim.

## Problem and intended users

Small workshops and maintenance teams often lack permanently installed vibration sensors. VibraLens explores whether an existing slow-motion phone camera can provide an initial, non-contact screening signal and guide a technician toward a useful follow-up measurement. It does not establish remaining equipment life, certify safety, or replace a vibration analyzer.

The useful output is an evidence-supported next step: request a better capture, request nameplate speed, compare with a compatible baseline, or draft a human-approved inspection work order. The prototype has not been evaluated in a workshop; cost savings and predictive-maintenance accuracy have not been measured.

## Implementation and OpenCV 5 contribution

OpenCV 5 performs substantive analysis, rather than serving as an image loader. `video.py` decodes and inspects frame timestamps. `markers.py` detects ArUco machine marker 1 and independent reference marker 7 with subpixel corner refinement, rejects invalid quadrilaterals, estimates a plane homography, and removes common camera translation, rotation and scale using a similarity transform. Metric scaling uses the physically measured marker side length.

`analysis.py` evaluates marker visibility, size, sharpness, exposure, frame duplication, reference movement, camera movement and out-of-plane risk. The compensated displacement is resampled onto capture-time slots. Short gaps are interpolated; long gaps split usable segments. `signal.py` estimates tonal frequency and harmonics, computes Welch band velocity and a noise-equivalent correction, and reports detection limits. At 240 fps the reporting band ends at 96 Hz, far below many machinery vibration standards' full bandwidth.

Slow-motion playback is a critical failure mode: a 240 fps capture saved at 30 fps can produce an eightfold frequency error. Original capture metadata or a verified phone timing profile is needed to resolve such retiming. Untagged low-fps recordings are rejected. Metadata-supported timing is labeled PROBABLE unless corroborated by a phone profile; metadata is not proof of genuine sensor capture.

The dominant spectral peak is only a candidate shaft frequency until corroborated by rpm. Fault interpretation is withheld when that identification is unsupported. Quality failures block the agent from proceeding to diagnosis, and direct analysis marks blocking-quality results INCONCLUSIVE.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md). The browser uses a capability-token workspace. FastAPI handles uploads and session state; a single worker claims persisted jobs with leases and bounded retries. Local development uses JSON documents and files. The AWS backend uses S3 for recordings, DynamoDB for sessions/jobs/readings, SNS for supervisor requests, CloudWatch for metrics, and an EC2 host behind CloudFront. Bedrock is an optional constrained planner; deterministic policy remains authoritative.

AWS infrastructure is supplied in `infra/stack.yaml` and automated by `infra/deploy_free.py`. **The app is deployed at https://dhfpmgo5xkqhh.cloudfront.net/** on an Ubuntu x86-64 t3.small instance in ap-southeast-2. The public health endpoint reports OpenCV 5.0.0 and the AWS backend. All four bundled workflows passed through the hosted S3/DynamoDB-backed application; exact state traces and timings are preserved in `eval/results/aws_demo.json`. See `docs/AWS_DEPLOYMENT.md` for deployment details. SNS is configured, but its email subscription was pending confirmation at the last check; no end-to-end email delivery is claimed.

## Perception, decision and action

The agent has a bounded, multi-step tool loop. After probing timing it chooses quality assessment or recapture. Poor marker size produces a move-closer instruction, ambiguous capture timing produces an original-file request, and an assumed shaft peak can trigger an rpm question. With adequate evidence it measures, interprets and compares only compatible readings. A significant increase can draft a work order. Approval is POST-only with a hashed, expiring token and a single-use decision; no machinery is controlled.

Each trace records allowed actions, actual choice, previous/next state, planner mode, fallback and latency. Bedrock can choose only a policy-permitted action and validated arguments. Errors fall back to the deterministic planner. A rule-planner demonstration must be labeled as such; Bedrock execution must not be claimed without a trace showing it.

## Evaluation and evidence

Reproduce unit/API checks with `python -m pytest -q tests`. Run `python tools/run_scenarios.py samples` for the four supplied compressed synthetic videos. Their adjacent `.truth.json` files describe known input motion. The resulting `samples/results.json` reports frequency, amplitude bias, uncertainty, capture flags and runtime. `eval/results/synthetic_scenarios.json` is an older 12-scenario development report; those development inputs are not all bundled and its timings must not be represented as a fresh benchmark.

The provided baseline and stronger-vibration examples use a true frequency of 24.3 Hz. Both the local and hosted AWS runs reported 24.305 and 24.301 Hz respectively. Small-motion amplitude was underestimated substantially (0.007999 versus 0.012 mm), which is a material limitation. The stronger-motion estimate was 0.075691 versus 0.08 mm. These are synthetic input comparisons, not physical accuracy claims. The hosted workflows took 74.6 s and 78.0 s including user-evidence simulation, processing, storage and polling; the two rejection cases took 29.0 s and 13.9 s. This is a single-run demonstration, not a latency distribution.

Failure cases include unknown slow-motion retiming, tiny or missing markers, motion blur, poor lighting, repeated/interpolated frames, moving reference structures, out-of-plane motion, incompatible baselines and insufficient continuous tracking. Tests cover signal recovery with noise/dropouts, camera compensation, timing decisions, bounded agent behavior, workspace isolation, upload validation, idempotency, and approval expiry/replay.

## Validation gates and responsible operation

Only frequency and relative trends are exposed in the default interface. Absolute mm/s and ISO zones remain disabled (`VL_AMPLITUDE_VALIDATED=false`) until simultaneous contact-sensor validation passes. Internal analysis artifacts retain candidate numerical values for research, but those values are not calibrated field measurements. The uncertainty expression is a team model, not a calibrated confidence interval; a LOWER_BOUND label does not prove a mathematical bound under every camera artifact.

No real-machine recordings, accelerometer comparison or verified phone profiles are available for this entry at preparation time. Next validation should use simultaneous phone and contact-sensor data at multiple speeds and amplitudes, frozen thresholds, held-out recordings, repeated captures and a camera-motion ablation. Report detection failure rates as well as successful frequency estimates.

Markers must be placed with equipment off and only on stationary housings. The operator must remain clear of moving equipment. The system never recommends a machine is safe to continue running. A work order requests inspection and contact measurement before major maintenance. Users should avoid recording people and private facility information. AWS raw uploads have a seven-day S3 lifecycle; local files and DynamoDB documents require separate operational retention/deletion management. DynamoDB TTL is configured, but item expiry is not currently populated automatically. Public service abuse controls are basic; workspace creation and deployment access require operational monitoring.

## Reproduction and final artifacts

Pinned primary dependencies are in `requirements.txt`; the complete tested dependency snapshot is in `requirements-lock.txt` when generated. Deployment is documented in `infra/deploy.md`. The judge walkthrough and recording plan are in `docs/DEMO_SCRIPT.md`; submission copy and unresolved requirements are in `docs/SUBMISSION.md`. No cloud acceleration, real-world reliability, certified diagnosis, or unperformed validation is claimed.

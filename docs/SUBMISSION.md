# Submission copy and release checklist

## Project title
VibraLens — see the vibration, verify the next step

## Tagline
Phone-camera vibration screening with OpenCV 5: verify the capture, measure the signal, and guide a human-reviewed maintenance response.

## Team
Aakarsh Saxena — solo developer. Do not add unverified biography, affiliations or prior awards.

## Inspiration
Many small maintenance teams have a phone but no permanently installed vibration sensors. A camera can reveal periodic motion, but a plausible spectrum alone is not enough: camera movement, slow-motion retiming and weak image detail can all mislead. VibraLens makes evidence quality part of the workflow.

## What it does
A technician uploads an original slow-motion recording containing a marker on a stationary machine housing and an independent reference marker. VibraLens validates timing and capture quality, tracks motion with OpenCV 5, estimates frequency and compares compatible recordings. Its agent requests specific new evidence when needed and drafts an inspection work order when a meaningful trend increase is observed. A human approves every work order.

## How it is built
Python, OpenCV 5, NumPy/SciPy and FastAPI form the analysis service. A plain JavaScript interface supports uploads, evidence requests, spectra and decision traces. The AWS deployment architecture uses EC2, S3, DynamoDB, CloudFront, SNS and CloudWatch. Amazon Bedrock is an optional planner constrained by a deterministic policy. Describe these as deployed only after verifying them in AWS.

## Challenges and learning
An original 240 fps capture can be saved at 30 fps playback timing, producing an eightfold frequency error. We reject ambiguous timing. Subpixel vibration is also vulnerable to compression and camera movement; independent reference tracking and explicit quality gates help make those limits visible. Synthetic small-motion tests show substantial amplitude bias, so calibrated vibration severity is withheld.

## Accomplishments
Implemented a working evidence-driven loop from video analysis to targeted recapture, rpm requests, compatible-baseline comparison and human approval. Included known-motion synthetic inputs, failure demonstrations, regression tests and reproducible deployment instructions. No field performance or COOL acceleration is claimed.

## What's next
Collect simultaneous phone/contact-sensor measurements, validate phone timing profiles, freeze thresholds on a development split, evaluate on held-out machines, and calibrate amplitude uncertainty before enabling absolute severity reporting.

## Before pressing Submit

| Requirement | Artifact / remaining action |
|---|---|
| Substantive OpenCV 5 analysis | `vibralens/markers.py`, `video.py`, `analysis.py`; preserve runtime version evidence |
| Meaningful AWS execution | Verified EC2/OpenCV + S3/DynamoDB deployment; `docs/AWS_DEPLOYMENT.md`, `eval/results/aws_demo.json` |
| Technical report | `docs/TECHNICAL_REPORT.md` |
| Architecture / agent workflow | `docs/ARCHITECTURE.md` |
| Judge-accessible code | https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-submission.zip |
| Build/deploy/test instructions | README, requirements and infrastructure guide |
| Endpoint or arranged live demo | https://dhfpmgo5xkqhh.cloudfront.net/ |
| Video ≤5 minutes, team visible | https://www.youtube.com/watch?v=dArWXwFDViY — synthetic examples, actual AWS application, Aakarsh's team credit, disclosed generated narration |
| Evaluation and limitations | `samples/results.json`, tests, report, e2e evidence |
| Agentic Vision evidence | Recorded state transitions / trace; label rule or Bedrock mode accurately |
| COOL award | Not claimed; no COOL workload or comparison exists |

The pasted event page lists October 27, 2026 at 12:15 pm India time while its prose says 11:59 pm Pacific on October 26. The public rules page also exposes an 11:45 pm Pacific deadline. These differ: **check the live Devpost countdown and use the earlier cutoff**, rather than assuming the later prose timestamp. Sources: https://opencv26.devpost.com/ and https://opencv26.devpost.com/rules.

Judge entry point: https://dhfpmgo5xkqhh.cloudfront.net/judge.html. Copy the description above and the accessible endpoint, archive and video links into Devpost. The project has not been submitted to Devpost by this preparation process. Keep the free-plan deployment available during judging; confirm the SNS supervisor subscription for approval emails. Field validation remains absent and must not be claimed.

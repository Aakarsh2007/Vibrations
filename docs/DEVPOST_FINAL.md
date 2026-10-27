# VibraLens — See the vibration. Verify the next step.

## Elevator pitch
Phone-camera vibration screening with OpenCV 5 on AWS. An evidence-driven agent checks the capture, measures the signal, and requests better evidence or human-reviewed maintenance action.

## Submission links

- Working app: https://dhfpmgo5xkqhh.cloudfront.net/
- Judge guide: https://dhfpmgo5xkqhh.cloudfront.net/judge.html
- YouTube demo video (4:22): https://www.youtube.com/watch?v=dArWXwFDViY
- Direct MP4 backup: https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-demo.mp4
- Judge-accessible source/report archive: https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-submission.zip
- GitHub source repository: https://github.com/Aakarsh2007/Vibrations
- Technical report: https://dhfpmgo5xkqhh.cloudfront.net/TECHNICAL_REPORT.md
- Hosted evaluation evidence: https://dhfpmgo5xkqhh.cloudfront.net/aws_demo.json

## Inspiration
Small maintenance teams often have a phone but no permanently installed vibration sensors. A video spectrum can look convincing while being wrong: camera movement, compressed subpixel motion and slow-motion playback timing can all distort the answer. We wanted the system to assess the evidence before recommending a next step.

## What it does
A technician records an original slow-motion video with one ArUco marker on a stationary machine housing and another on an independent reference structure. VibraLens checks timing and image quality, compensates camera motion and estimates periodic vibration. Its agent can request a closer recording, ask for nameplate rpm, compare compatible baselines, or draft an inspection work order requiring supervisor approval. It never controls machinery.

## How we built it
OpenCV 5 performs ArUco detection, subpixel corner tracking, similarity-transform camera compensation and homography-based scaling. NumPy and SciPy estimate frequency, harmonics, noise and band-limited motion. A FastAPI service and a plain JavaScript interface expose the workflow. The deployed AWS system uses EC2 for OpenCV processing, private S3 for recordings, DynamoDB for sessions and leased jobs, SNS for approval requests, and CloudFront for HTTPS. A deterministic policy constrains allowed agent actions. The verified runs use the rule planner; Bedrock is an optional integration.

## What makes the agent useful
Visual evidence changes the next action. A tiny marker triggers a move-closer request. An untagged 240 fps clip saved at 30 fps is refused because physical timing cannot be established. An assumed shaft peak prompts an rpm question. A compatible reading with a large relative increase triggers a human-reviewed work order. Every step has an inspectable trace.

## Results
All four bundled workflows passed on the public AWS deployment. The synthetic 24.3 Hz baseline and stronger-motion inputs were recovered as 24.305 Hz and 24.301 Hz. The comparable pair produced a 1055.7% relative increase and a work-order draft. Tiny-marker and ambiguous-timing inputs produced the appropriate recapture requests. The final local unit/API suite passed 42 tests. The local approval security demonstration accepted one decision and rejected reuse with HTTP 409.

## Challenges and limits
Slow-motion retiming can cause an eightfold frequency error. Small-motion compression also caused substantial amplitude underestimation in the synthetic baseline. These results do not establish physical accuracy: no real-machine or contact-sensor validation has been performed. Absolute mm/s and ISO zones therefore remain disabled. Fault patterns are screening heuristics. The hosted workflow timings are single-run observations, not a performance benchmark. SNS supervisor email delivery requires confirmation of its subscription.

## What is next
Simultaneous phone and contact-sensor recordings, verified phone timing profiles, frozen thresholds and held-out machine evaluations. We will calibrate amplitude and uncertainty before enabling absolute vibration severity. The current contribution is a working, observable evidence-to-action workflow with explicit refusal and human control.

## Team and technology tags
Aakarsh Saxena — solo developer.

Python, OpenCV 5, NumPy, SciPy, FastAPI, JavaScript, AWS EC2, Amazon S3, Amazon DynamoDB, Amazon SNS, Amazon CloudFront, Amazon CloudWatch.

Tracks: main competition and Agentic Vision. Do not claim COOL, Graviton execution, Bedrock execution, field accuracy, certified diagnosis, or cost savings. This preparation does not submit the project to Devpost; paste the copy and links into your entry and check the live deadline.

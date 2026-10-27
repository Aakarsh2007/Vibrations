# Five-minute submission video

**Published demonstration (4:22): [Watch on YouTube](https://www.youtube.com/watch?v=dArWXwFDViY).** The plan below is the original recording outline; the published video includes AWS execution evidence and disclosed computer-generated narration.

Target length: **4:40**. Presenter: **Aakarsh Saxena**, solo developer. Show a camera introduction and screen recording; keep recordings synthetic labels visible. Use a real AWS endpoint after deployment. Pre-run analyses to avoid long waits, then start one new sample live to prove interaction.

| Time | Show | Suggested narration |
|---|---|---|
| 0:00–0:25 | Presenter and home screen | “I'm Aakarsh Saxena. VibraLens turns a slow-motion phone recording into evidence for a maintenance screening decision. This prototype is evaluated on synthetic videos.” |
| 0:25–0:50 | Marker sheet and capture instructions | Explain housing marker, independent reference, safe placement with equipment off, and original slow-motion upload. |
| 0:50–1:30 | Healthy baseline session; enter 1458 rpm if requested | “OpenCV checks timing, tracks subpixel ArUco corners, removes camera motion, and estimates the spectrum. This synthetic input is 24.3 Hz.” Show actual reported estimate and lower-bound classification. |
| 1:30–2:10 | Added-mass session after baseline | Show compatibility checks, percentage change, and work-order draft. “The new visual evidence changes the next action. It requests human review.” |
| 2:10–2:45 | Tiny-marker and timing-problem sessions | Show the move-closer instruction and refused timing. “An untagged slowed clip could give an eightfold error, so the agent asks for better evidence.” |
| 2:45–3:15 | Supervisor approval and trace | Approve the synthetic work order. Show audit entry and single-use token behavior. Do not expose a real approval token in public video. |
| 3:15–3:50 | Architecture diagram and deployed health endpoint | Explain OpenCV 5, EC2, S3, DynamoDB, SNS, CloudWatch, and optional Bedrock. State whether the actual trace uses rules or Bedrock. |
| 3:50–4:20 | Fresh evaluation report and tests | Report successful frequency estimates, runtime and rejected captures from actual artifacts. Explain small-motion amplitude bias and synthetic-only evidence. |
| 4:20–4:40 | Presenter and result page | “The next step is simultaneous contact-sensor validation. Until then we show frequency and relative trends, with absolute values and ISO zones disabled.” |

## Rehearsal

1. Start the local development server with `VL_DEV=1` only for the scripted local approval demo. Production must leave it unset.
2. Run `python tools/e2e_demo.py http://127.0.0.1:8000`. The local outbox contains the synthetic approval link; `/api/dev/outbox` requires workspace authorization. The script automatically approves a synthetic work order and verifies replay rejection.
3. In the browser, run “Healthy fan” first and answer 1458 rpm. Run “Same fan with added mass” next in the same browser/workspace. Show “Assistant decisions” and the spectrum.
4. Open the two failure examples. Show how each leads to a different recapture instruction.
5. Record team introduction and narration with your own voice. Export under five minutes, upload public or unlisted, and test playback without your login.

Do not present a local server as AWS delivery. If AWS is unavailable, arrange a live screen-share as permitted by the competition, while still satisfying its separate meaningful-AWS-component requirement.

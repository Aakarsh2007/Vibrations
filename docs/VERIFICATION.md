# Verification — October 27, 2026

Environment: Windows x64, Python 3.12, OpenCV 5.0.0.93. Primary pins installed successfully. Full tested dependency snapshot: `requirements-lock.txt`.

## Automated checks

- 42 unit/API tests passed after the final regional S3 upload fix (11.55 seconds). One dependency warning remains: Starlette deprecates its httpx-based test client. Tests cover evidence export authorization, absence of credential fields, and regional upload targets. The narrated video retains the earlier 41-test checkpoint; the final source includes the additional upload regression test.
- `node --check web/app.js` passed.
- Fresh analysis of all four bundled videos completed. See `samples/results.json`.
- Live HTTP end-to-end demonstration completed on localhost in 167 seconds. The two usable recordings recovered 24.305 Hz and 24.301 Hz from a 24.3 Hz input. The added-mass recording triggered a comparable trend increase and work-order draft. Tiny-marker evidence requested recapture, untagged slowed playback requested original timing evidence, repeated evidence submission replayed idempotently, approval succeeded and a second decision returned 409.
- Planner mode in this run: **rules**. Backend: **local**. This is not a Bedrock or AWS execution claim.
- Sanitized traces and final approval state are saved in `eval/results/agent_demo.json`. Internal amplitude values in these research artifacts are uncalibrated.
- The home screen loaded in the local browser preview and its narrow-screen visual layout was inspected. JavaScript syntax and HTTP workflows were checked separately; this is not a comprehensive browser/device compatibility test.

## Material gaps

The AWS x86-64 deployment is now verified: all four workflows passed at the public HTTPS endpoint with S3/DynamoDB persistence. See `AWS_DEPLOYMENT.md` for exact timing and limitations. A narrated video and the submission archive are hosted through the judge page. The SNS email subscription remains pending confirmation at the last check. ARM64 installation and Docker build are not claimed. No field recordings or contact-sensor validation exist, and the entry has not been submitted to Devpost automatically.

The older 12-scenario development evaluation and older screenshots remain historical artifacts. Use the fresh four-video results and new traces for current behavior, especially the stricter INCONCLUSIVE classification on blocking quality failures.

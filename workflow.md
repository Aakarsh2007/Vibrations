# VibraLens: complete hackathon workflow (v3, audited)

**Competition:** OpenCV AI Competition 2026, powered by AWS (Devpost: opencv26.devpost.com)
**Hard deadline:** Mon 27 Oct 2026, 12:15 PM IST (= Sun 26 Oct, 11:59 PM PT). **Internal target:** submitted by **Mon 27 Oct, 10:00 AM IST**.
**Tracks:** Main prize ($5k / $3k / $2k) + **Agentic Vision Award** ($1k). The COOL path is dropped under the zero-budget decision below.

> **The idea in one line:** A technician records 10 s of slow-motion video of a running motor or pump with a printed marker stuck on its housing. VibraLens measures the vibration with OpenCV 5. It reports the **vibration frequency**, a **band-limited vibration velocity (mm/s RMS) with uncertainty**, an **estimated ISO 20816-3 zone when the standard applies**, a **suspected fault pattern**, and a **motion-magnified video**. An agent uses the visual evidence to decide what to capture next, refuses to diagnose from weak evidence, and asks a human before raising any work order.

---

## ⚠️ Zero-budget decision (23 Oct, overrides anything below that conflicts)

**Constraint from the team: no money can be spent.**

| Topic | Decision |
|---|---|
| AWS account | **AWS Free Plan** (new account, $100 sign-up credits + up to $100 more for activities 📄). On the Free Plan, AWS **closes the account instead of charging** when credits run out or after 6 months 📄, so spend is capped at ₹0. Sign-up still asks for a card for verification; a small temporary authorisation hold may appear 📄. **Never click "Upgrade to Paid plan"; never join AWS Organizations** (that converts the account) 📄. |
| COOL award | **Dropped.** COOL is a Marketplace AMI, and Marketplace is blocked on the Free Plan 📄. We still run on **AWS Graviton (ARM)**: the OpenCV 5 wheel exists for Linux aarch64 ✅ (`opencv_python_headless-5.0.0.93-cp37-abi3-manylinux2014_aarch64`). The report mentions COOL as future work. Everything in §B10 becomes P2 (only if a free path appears). |
| Compute | **EC2 t4g.small or t4g.medium** (Graviton2, ~$0.017–0.034/h 📄, paid from credits). Default to t4g.medium for the 4 GB RAM. Stop it when not needed before judging. |
| Agent model | **Amazon Nova (first-party Bedrock model)** paid from credits, if the Free Plan allows it (⏳ check in the console). Claude on Bedrock is Marketplace-billed → not used. If Bedrock is unavailable, the **rule planner** runs the same policy (§B6), and the report says so. |
| Other services | S3, DynamoDB, CloudWatch, SNS, CloudFront: all small usage, paid from credits / always-free allowances 📄. |
| Phones, fan, accelerometer | Team's own devices (free phyphox app). |
| Tracks on Devpost | Main competition + **Agentic Vision** path. COOL path not ticked. |

## 0. Build status (23 Oct, evening): what exists and what it was tested on

**Code:** `vibralens/` (Python package), `web/` (UI), `tests/`, `tools/`, `eval/`, `infra/`. Run it locally with the README quick start.

| Area | Status | Evidence |
|---|---|---|
| Timing (`video.py`) | ✅ built | Unit tests; synthetic 240→30 fps file **without** tag → `UNRELIABLE`; **with** tag → 24.300 Hz recovered |
| Measurement (`markers.py`, `signal.py`, `analysis.py`) | ✅ built | 34/34 tests pass. Synthetic scenarios: frequency within **0.035 Hz** in all 10 measurable cases (`eval/results/synthetic_scenarios.json`) |
| Capture-quality flags | ✅ built | All 12 synthetic scenarios raise the expected flag (blur, tiny marker, missing/vibrating reference, camera shake, dark, duplicated frames, compression, timing) |
| Diagnosis (`diagnose.py`) | ✅ built | ISO applicability rules from the official preview (unit tests); trend mode active (`AMPLITUDE_VALIDATED=false`) |
| Agent (`policy.py`, `agent.py`, `tools.py`) | ✅ built (rule planner tested end to end) | `tools/e2e_demo.py` on the live local server, sequence below |
| Bedrock path | ⏳ code built, **not run** | Needs the team's AWS account + Nova access |
| Backend (jobs/leases, idempotency, workspaces, approvals) | ✅ built | API tests (isolation, signed uploads, idempotent sessions, single-use POST approval, expiry); duplicate evidence replay checked end to end |
| UI | ✅ built | Screenshots in `docs/screens/` (desktop); real-phone layout ⏳ |
| AWS deployment | ⏳ templates written (`infra/stack.yaml`, `infra/deploy.md`), **not deployed** | Needs the AWS Free Plan account |
| Real phone timing (G1), accelerometer (G2/G3) | ⏳ tools ready (`web/timing.html`, `eval/timing_check_video.py`, `eval/compare_accel.py`) | Needs the team's phone, fan and phyphox |

**End-to-end run (local server, rule planner, synthetic samples):**
1. Healthy baseline: measured → asked for the rpm → answered → "Spectrum shape: imbalance-type" (not called a fault) → completed.
2. Same fan with added mass: comparable with the baseline (+1056%, team-heuristic criterion) → "Suspected mixed pattern" → work order drafted.
3. Approval link: preview (POST) → approved once → a second decision is refused (409) → session completed with an audit entry.
4. Bad capture: "The marker is 50 px wide; it needs at least 80 px. Move closer…" → a new recording is accepted → measurement continues.
5. Timing problem: "upload the ORIGINAL file" (no measurement attempted).

**Synthetic-only caveat:** the amplitude numbers are 2–10% low at 0.3 px and about 33% low at 0.045 px on synthetic H.264. That is why amplitudes stay `LOWER_BOUND` until G3.

**Bugs found and fixed while building:**
- Clipping check counted black marker cells as over-exposure.
- The broadband detection limit was compared with a tonal signal.
- Bitrate threshold changed from Mbps to bits/pixel.
- The OpenCV `estimateAffinePartial2D` (LMEDS, 4 points) residual of 0.43 px was replaced by an exact Umeyama fit with a medoid reference.
- A healthy machine was labelled "suspected imbalance".
- Trend mode leaked absolute mm/s into texts.
- Samples JSON had a BOM.

**Implementation choices that differ from Part B (the code is authoritative):**
- One DynamoDB table instead of six.
- The LLM is consulted only when the policy allows more than one action. It sees a fresh evidence summary each turn, not a long chat history, which keeps it simple and robust.
- One process runs API + worker (leases still protect against crashes).
- Bedrock model = Amazon Nova (zero budget).


## How to read this document

### Evidence labels (used everywhere)
| Label | Meaning |
|---|---|
| ✅ **Tested here** | We ran it; a script in `feasibility/` reproduces it. |
| 🧪 **Synthetic only** | Tested on generated data only. **Not** proof that it works on real phones or machines. |
| 📄 **Source-reported** | From documentation or secondary sources. Not checked by us; must be confirmed where marked. |
| ⏳ **Not yet done** | No evidence yet. Must not be claimed in the submission until done. |

### Priority labels (every feature has one)
| Label | Meaning |
|---|---|
| **P0** | Must work. The submission fails without it. |
| **P1** | Important. Start only after your own P0 items pass. |
| **P2** | Stretch goal. Start only after **all** P0 items pass. |

### Structure
- **Part A: idea, verification and edge cases.** Why this idea; what we tested; the science and its limits; 42 edge cases.
- **Part B: implementation and submission playbook.** Architecture; module specs with code; agent state machine; backend reliability and security; UI; AWS commands; COOL benchmark; evaluation (measurement + agent); priority schedule; Devpost, report, video and checklist; risks; consistency audit.
- **Scripts in `feasibility/`:**

  | Script | What it checks | Status |
  |---|---|---|
  | `sim.py` | Sub-pixel marker tracking + codec attenuation | 🧪 |
  | `alias.py` | Aliasing + interpolated-frame detection | 🧪 |
  | `signal_check.py` | Signal maths against known answers | ✅ |
  | `timing_check.py` | Slow-mo timestamp behaviour on generated files | ✅ (generated files only) |
  | `interp_check.py` | Fake slow-mo detection against motion-compensated, blended and duplicated 60→240 fps | 🧪 |

### Contents
**Part A:** A0 Verdict · A1 Real and unique? · A2 What we tested · A3 Facts from sources · A4 Product · A5 Measurement science and limits · A6 Edge cases · A7 AWS summary · A8 Go/no-go and fallbacks · A9 Responsible use and safety

**Part B:** B1 What we submit · B2 How we win · B3 System design · B4 Repo layout · B5 Module specs · B6 Agent design · B7 Backend reliability and security · B8 Web app · B9 AWS setup · B10 COOL benchmark · B11 Measurement evaluation · B12 Agent evaluation · B13 Priority schedule · B14 Submission package · B15 Risks · B16 Definition of done · B17 Consistency audit and open items

### Start right now (first 3 hours)
1. **Cloud lead (P0):** do the account setup in §B9 step 1: Paid plan, $20 budget alarm, Bedrock model access (Claude + Nova), COOL subscription, a c8g instance, and record `cv2.__version__` + `getBuildInformation()`.
2. **Data/eval lead (P0):**
   - Print the markers. **Measure the printed side with a ruler.**
   - Install phyphox on an Android phone.
   - Run the **timing test** (§B11.2, G1).
   - Record the fan with **no mass** first.
3. **Vision lead (P0):** implement `video.py`, `markers.py` and `signal.py` from §B5 (the signal maths is already tested in `feasibility/signal_check.py`). Run them on the first real recordings.
4. **Tonight:** gates **G1** (timing) and **G2-early** (frequency vs accelerometer) from §A8.

---

# Part A: Idea, verification and edge cases

## A0. Verdict

**Build this, with measurement claims gated by real-world validation.**

**Status of the evidence:**
- The core measurement chain has been checked on **synthetic** data only (§A2).
- The signal maths is checked against known answers ✅.
- Real-phone and real-machine evidence does **not exist yet** ⏳. Gates G1–G3 (§A8) decide what we are allowed to claim.

**Corrections made in earlier versions:**

| Earlier assumption | Problem found | Fix |
|---|---|---|
| Tell real vs aliased frequency by recording again at 120 fps | Phone frame rates (30/60/120/240) are multiples of each other, so the aliases are identical. A true 197.5 Hz looks like 42.5 Hz at both 240 and 120 fps ✅ (`alias.py`). | Expected 1× comes from **rpm** (user entry; OCR of the nameplate is P2). The video's **audio track** is supporting evidence (P1). |
| Free-tier credits cover everything | AWS **Free Plan accounts cannot buy from Marketplace** 📄. That blocks the COOL AMI, and probably Claude on Bedrock (Marketplace-billed). | Upgrade one account to the Paid plan, with a $20 budget alarm. Amazon Nova (first-party) as the fallback model. |

**Corrections made in this version (v3 audit):**

| Earlier assumption | Problem | Fix |
|---|---|---|
| `CAP_PROP_POS_MSEC` / PTS give real time | For a 240 fps capture stored with 30 fps playback timing, both OpenCV and the timestamps give **3.04 Hz instead of 24.3 Hz** ✅ (`timing_check.py`, generated file). | Timing is established from multiple sources, with an explicit status `CONFIRMED / PROBABLE / UNRELIABLE`. `UNRELIABLE` → no measurement (§B5.1). |
| Linear interpolation to a uniform grid | Under-reads a 49.6 Hz tone by **~5%** ✅ (`signal_check.py`, before the fix). | Treat near-regular timestamps as uniform; fill missing samples with a cubic spline; split on long gaps. After the fix: all four test cases within 1% amplitude ✅. |
| Velocity RMS via windowed FFT → differentiate → inverse FFT | Window/derivative interaction is not a valid way to get RMS. | **Welch PSD** (density scaling) × (2πf)², integrated over the band ✅. Tone amplitudes use a **flat-top window** ✅. |
| Default to ISO Group 2 rigid | Unjustified. ISO 20816-3 covers only machines **> 15 kW** and **excludes rotordynamic pumps and reciprocating machines** ✅ (official preview). Our fan, pump and motorbike are all outside its scope. | No default group. Machine type + coupling + power required. Zone only when the standard applies; otherwise "not applicable (reason)" or "not assessed" (§B5.5). |
| Noise-variance detector catches fake slow-mo | False alarm on real 240 fps and misses all fakes after H.264 encoding ✅ (`interp_check.py`) | Phone-mode verification (G1) is the safeguard; a frame-difference check is used as a warning only |
| "mm/s" always shown | Real-world amplitude accuracy is unproven ⏳; compression under-reads small motion 🧪. | Four result classes: `RELIABLE / LOWER_BOUND / BELOW_DETECTION_LIMIT / INCONCLUSIVE`. If gate G3 fails, **frequency + relative-trend mode** (no absolute mm/s). |
| Machine marker minus reference marker cancels camera motion | Wrong under camera roll, zoom/focus breathing, depth differences (parallax) and rolling shutter. | Similarity-transform compensation from the 4 reference corners, plus consistency checks, plus a placement rule (same image rows, similar depth) (§B5.2). |
| A GET link approves a work order | Unsafe: link scanners and prefetchers can click it. | Email link → confirmation page → authenticated POST. The token is random, hashed, expiring and single-use, with an audit trail (§B7.4). |
| In-memory thread pool | Jobs are lost on restart, and retries can duplicate work. | Jobs persisted in DynamoDB with leases, heartbeats, bounded attempts and idempotency keys (§B7). |

## A1. Is it real and unique? (honest answer)

- **Real:** camera-based vibration measurement is an established industrial method 📄.
  - Commercial systems: RDI Technologies (Iris M / aiOne), Erbessd (Dragon Vision).
  - Research: published papers classify motor faults from video. One reports 96.7% with motion magnification + Random Forest, on its own dataset.
  - We are not inventing physics; we are making a proven method cheap.
- **Unique:** in our searches we found no hackathon project, app or open-source tool that combines:
  - phone slow-mo,
  - a printed ArUco marker for metric scale,
  - a reference marker for camera-motion compensation,
  - explicit timing/quality/uncertainty states,
  - and an agent that directs the next capture.

  This is a search result, not proof of absence.
- **Who needs it:** MSMEs, flour and rice mills, farm and hostel pumps, college workshops. These are machines with motors but without ₹10k–₹80k-per-point sensors 📄 or an analyst.
- **Scope we can defend:**
  - **condition monitoring and screening:** frequency, trend, and an estimated band-limited level;
  - **not** certified ISO compliance testing;
  - **not** bearing diagnostics (needs > 1 kHz).

## A2. What we tested (synthetic) and what it means

**Environment:** Windows, Python 3.11, `opencv-contrib-python-headless==5.0.0.93` and `opencv-python-headless==5.0.0.93` (both report 5.0.0), numpy 2.4.6, scipy 1.17.1.

**Synthetic video setup (`sim.py`):**
- 240 fps, 1280×720.
- Gaussian sensor noise σ = 2.5 DN.
- Random-walk drift + 3.1 Hz camera tremor (~0.3 px).
- 4% brightness flicker at 100 Hz.
- 140 px ArUco marker (40 mm → 0.286 mm/px) plus a static reference marker.
- Machine vibration at 24.3 Hz with a 2× harmonic.
- Sub-pixel motion rendered by bilinear warp at 2× supersampling.

**Not modelled:** optics, lens distortion, motion blur, rolling shutter, OIS/EIS, real phone codecs and denoising. 🧪

| Test | Result | Label |
|---|---|---|
| ArUco (`CORNER_REFINE_SUBPIX`), machine − reference, uncompressed | 0.02 px true → 0.0182 px measured (−9%), SNR ≈ 31; 2× harmonic recovered (0.0064 vs 0.0070 px). 0.0182 px ≈ 0.56 mm/s RMS at 24.3 Hz at this scale. | 🧪 |
| Same after H.264 (libx264) | Frequency found every time (24.25 Hz on the 0.1 Hz-resolution grid of the test). Amplitude shrinks for tiny motion; see the table below. | 🧪 |
| Naive whole-ROI `cv.phaseCorrelate` | Failed (3.3 px garbage) with background texture and drift in the ROI. **ArUco corners are the primary tracker.** | 🧪 |
| Fake slow-mo detector v1 (noise-variance cadence, static patch) | On uncompressed data: real 1.01 vs linear-blend 2.01. **After H.264 encoding (`interp_check.py`) it fails:** real 240 fps gave 1.43 (false alarm); motion-compensated (ffmpeg `minterpolate` mci), blended and duplicated 60→240 gave 1.05 / 1.07 / 1.00 (all missed). The codec copies static-region noise between frames. | ✅ **Rejected** |
| Fake slow-mo detector v2 (frame-difference cadence in the moving marker ROI + near-zero-difference fraction) | Real 240: ratio 1.17, 0.4% near-zero. Duplicated: 968, 32% near-zero (**detected**). Motion-compensated: 2.23 (**detected at threshold 1.6**). Blended: 1.13 (**missed**). | 🧪 **Partial: warning only, not a gate** |
| Alias check, 240 vs 120 fps | Useless, as explained in §A0. | ✅ |
| Signal maths (`signal_check.py`): 4 tones, timestamp jitter, 1% dropped frames, drift, noise | Frequency error < 0.001 Hz; tone amplitude error ≤ 0.75%; band velocity RMS error ≤ 3.4% (after the resampling fix). | ✅ |
| Timing (`timing_check.py`): a generated 240-frame/s motion stored at 30 fps playback | OpenCV `CAP_PROP_FPS` = 30, `POS_MSEC` Δt = 33.3 ms, so the peak reads **3.04 Hz** (true 24.3). With the `com.android.capture.fps=240` tag the correct 24.31 Hz is recovered. **Without a tag, the true rate cannot be known from the file.** | ✅ (generated files only) |
| OpenCV 5 APIs used by this plan | Present in both 5.0.0 wheels: `aruco.ArucoDetector`, `CORNER_REFINE_SUBPIX`, `findHomography`, `perspectiveTransform`, `estimateAffinePartial2D`, `phaseCorrelate`, `calcOpticalFlowPyrLK`, `Laplacian`, `pyrDown/pyrUp`, `FaceDetectorYN`, `dnn.TextDetectionModel_DB`, `dnn.TextRecognitionModel`, `dnn.ENGINE_NEW`, `CAP_PROP_POS_MSEC`. (`buildPyramid` is not exposed in Python; loop `pyrDown`.) | ✅ |

**Compression attenuation (synthetic, libx264).** Each cell is the measured amplitude error vs the true amplitude, with SNR in brackets.

| True 1× amplitude | crf 12 (≈100 Mbps on this content) | crf 23 (≈3.6 Mbps) | crf 30 (≈1 Mbps) |
|---|---|---|---|
| 0.03 px | −31% (14) | −42% (9) | −59% (6) |
| 0.1 px | −12% (42) | −32% (30) | −47% (20) |
| 0.3 px | not run | −5% (80) | −24% (54) |

**Interpretation (a hypothesis to validate on real phones ⏳):**
- H.264 motion compensation works in ¼-pixel steps and drops residuals at low bitrate, so sub-pixel motion is partly lost.
- Consequences for the design:
  1. Frequency detection is far more robust than amplitude.
  2. Amplitude is trusted only above a pixel-amplitude and bitrate threshold (initial values: ≥ 0.3 px, ≥ 0.05 bits/pixel/frame; a fixed Mbps value would depend on resolution); below that it is reported as a lower bound.
  3. Real phones use HEVC/H.264 with their own rate control. These numbers do **not** transfer automatically; gate G3 measures the real behaviour.

## A3. Facts from sources (to confirm where marked)

| Claim | Status |
|---|---|
| OpenCV 5.0 on PyPI | ✅ `opencv-python(-headless) 5.0.0.93` installed and imported here. |
| COOL is OpenCV 5 | 📄 Conflicting. The Marketplace listing (COOL v3.1) says "built on OpenCV 5.0"; GitHub issue #30373 (older AMI) showed `4.14.0-pre`. **Confirm on the instance** (§B9, step 1.6). |
| COOL deployment | 📄 Graviton4 AMI (c8g/m8g/r8g), Ubuntu 24.04, Python venvs at `/opt/cool/venvs/python_3.1x`. Software fee $0.01/h (c8g.large/xlarge) up to $0.80/h; 7-day free trial. |
| COOL vs pip performance | 📄 Issue #30373: single-thread within ~3% of the pip wheel; differences came mainly from threading; some filter/morphology paths ran on one core. **Do not claim a speedup until §B10 measures it.** |
| Graviton4 in Mumbai | 📄 c8g.large listed in ap-south-1 (~$0.054/h on an aggregator site). Confirm in the console. |
| Claude on Bedrock from Mumbai | 📄 Mainly via global cross-region inference profiles. Confirm in the console. |
| Bedrock Converse `toolChoice` | 📄 `auto` (default), `any` (must call a tool) and `tool` (named; Anthropic Claude 3+ and Amazon Nova). |
| ISO 20816-3:2022 (replaces ISO 10816-3:2009) | **Scope, covered/excluded machine types and measurement band: ✅ read in the official iTeh preview of the standard (clause 1 and 4.3).** Zone values, groups and the change criterion are **not** in the preview: 📄 secondary sources. Details in the list below. |
| Small machines (< 15 kW) | 📄 Outside ISO 20816-3. Legacy ISO 10816-1 "Class I" values (0.71 / 1.8 / 4.5 mm/s) appear only in secondary sources. **We do not use them for verdicts.** |
| Android capture rate | 📄 The `com.android.capture.fps` tag carries the capture rate on many devices, and `r_frame_rate` can be wrong. Presence varies by OEM. |
| iPhone slow-mo files | 📄 Slow-motion segments are applied as time-remapping; exported or shared copies may be re-timed to 30 fps. **Behaviour of the browser upload path is unknown ⏳ and must be tested (G1).** |
| phyphox accelerometer rate | 📄 Device-dependent: iPhone ~100 Hz, many Androids 400–500 Hz; sample timing not guaranteed. |

**ISO 20816-3:2022 details:**
- ✅ **Scope (clause 1, official preview):** coupled industrial machines with power **above 15 kW** and operating speeds **120–30,000 r/min**, measured in situ on shafts, bearings, pedestals or housings, under steady-state operation within the nominal speed range.
  - It covers only vibration **produced by the machine set itself**.
  - It does **not** address diagnostic evaluation of gears or bearings.
- ✅ **Covered types:** steam turbines/generators (with limits); rotary compressors; industrial gas turbines ≤ 3 MW; turbofans; **electric motors of any type if the coupling is flexible**; rolls and mills; conveyors; variable-speed couplings; **blowers or fans**.
  - **Note 3 on fans:** the criteria are "generally only applicable to fans with power ratings greater than 300 kW or fans which are not flexibly supported".
- ✅ **Excluded types:**
  - **rotordynamic pumps** and close-coupled motor-pumps (→ ISO 10816-7);
  - **reciprocating machines** and machines solidly coupled to them (→ ISO 10816-6), e.g. a motorbike engine;
  - submerged motor-pumps; screw compressors; reciprocating compressor systems; hydro sets; wind turbines; large turbines/generators (other parts).
- ✅ **Measurement band (clause 4.3):** flat response from **10 Hz to 1000 Hz**; for speeds approaching or below 600 r/min, the lower limit must be **≤ 2 Hz**.
- **Consequence for us:**
  - Our likely test machines are a table fan, a hostel water pump and a motorbike. **None of them is in ISO 20816-3 scope.**
  - The app needs **machine type and coupling** as inputs.
  - ISO zones will only appear for flexibly coupled electric motors, compressors, conveyors and similar machines above 15 kW.
- **Group 1** (> 300 kW, or electrical machines with shaft height ≥ 315 mm):

  | Support | A/B | B/C | C/D (mm/s) |
  |---|---|---|---|
  | Rigid | 2.3 | 4.5 | 7.1 |
  | Flexible | 3.5 | 7.1 | 11.0 |

- **Group 2** (15–300 kW, or shaft height 160–315 mm):

  | Support | A/B | B/C | C/D (mm/s) |
  |---|---|---|---|
  | Rigid | 1.4 | 2.8 | 4.5 |
  | Flexible | 2.3 | 4.5 | 7.1 |

- **"Rigid":** the lowest natural frequency of the machine and support in the measurement direction is ≥ 25% above the main excitation frequency.
- **Change criterion:** a change greater than **25% of the zone B upper boundary** is significant (stated for 10816-3; whether it carries into 20816-3 is unconfirmed).

**Action:** scope and band are confirmed from the preview. For the **zone values** (Annex A) and the **change criterion** (clause 6.3), check whether any team member has library/BIS/IEEE access to the full text. Otherwise cite the secondary sources and say so in the report.

## A4. Product

### A4.1 Capture protocol (guided by the app)
1. **Markers (P0):**
   - Print the app's PDF: two ArUco markers, DICT_4X4_50, ID 1 (machine) and ID 7 (reference), nominal 40 mm, plus a **100 mm ruler bar** to check print scaling.
   - **Measure the printed marker side with a ruler and enter it in the app.** Printers often scale pages.
2. **Safety first (P0):**
   - Place markers **only while the machine is switched off and isolated**, and only on **stationary** surfaces (bearing housing / motor frame).
   - Never on shafts, couplings, belts, fan blades or other moving parts.
   - Keep guards in place.
3. **Reference marker:**
   - On a **separate static structure** (wall, pillar, stand clamped to a wall), not on the machine's base or the same table.
   - Put it **beside** the machine marker: the same image rows (within 10% of frame height) and similar distance from the camera.
4. **Camera:**
   - Tripod or wedged on a stable surface **not standing on the machine's base**.
   - Frame about **12–25 cm wide** (the app computes a target from the marker's pixel size after a test clip).
   - Stabilisation off if the phone allows it. Lock focus/exposure (tap-and-hold). Highest quality. Good light.
5. **Record:** **10 s** in the phone's **real** slow-motion mode (240 fps preferred, 120 fps acceptable).
6. **Upload the original file**, not a messaging-app copy. Messaging apps recompress and can change timing.
   - **Android:** upload from the browser file picker or Files.
   - **iPhone:** the path is validated in G1 ⏳; the app shows the method that passed.
7. **Machine info** (asked if unknown):
   - **machine type** (electric motor / fan or blower / compressor / conveyor / rotordynamic pump / reciprocating engine / other);
   - **coupling** (flexible / rigid / close-coupled / unknown);
   - rated power (kW) or "unknown";
   - rated speed (rpm) or "unknown";
   - support (rigid/flexible/unknown);
   - measurement point ID (e.g. "NDE bearing, horizontal").
8. **Optional:** a photo of the nameplate (P2 OCR; P0 fallback: type the rpm).

### A4.2 OpenCV 5 tools (shared by the API, the agent and the evaluation)
| Tool | What it does | Main OpenCV 5 functions | Priority |
|---|---|---|---|
| `probe_video` | Capture-rate determination with timing status; dropped-frame and jitter stats; bitrate; interpolated-footage check | `VideoCapture` (+ ffprobe metadata/PTS) | P0 |
| `check_capture_quality` | Marker visibility and size, blur, exposure, flicker, tilt, camera motion, reference motion, pixel amplitude | `aruco`, `Laplacian`, `meanStdDev`, `estimateAffinePartial2D` | P0 |
| `measure_vibration` | Sub-pixel corners → validity checks → camera-motion compensation → mm via homography → uniform timebase → spectrum, 1×/2×/3×, band velocity RMS, noise floor, detection limit, result class | `ArucoDetector` (SUBPIX), `findHomography`, `perspectiveTransform`, `estimateAffinePartial2D` | P0 |
| `diagnose` | ISO applicability and estimated zone (if allowed); suspected fault pattern; confidence; limitations | deterministic Python | P0 |
| `compare_readings` | Comparability check + spectra overlay + change metrics | deterministic Python | P1 |
| `magnify` | Eulerian motion magnification around 1× → MP4 | `pyrDown`/`pyrUp` + temporal bandpass | P1 |
| `audio_peaks` | Audio spectrum → candidate shaft/blade-pass frequencies (supporting evidence only) | ffmpeg + numpy | P1 (basic) / P2 (beyond) |
| `read_nameplate` | OCR of rpm/kW from a photo | `dnn.TextDetectionModel_DB` + `TextRecognitionModel` | P2 (fallback: user types values) |
| `markerless_track` | Natural-feature tracking when no marker can be placed | `goodFeaturesToTrack` + `calcOpticalFlowPyrLK`; XFeat via OpenCV 5 DNN | P2 |
| `anonymize` | Blur faces before storing outputs | `FaceDetectorYN` (YuNet) | P1 |

### A4.3 What the user gets
The verdict separates **observed measurements** (frequency, band velocity, quality, uncertainty) from **interpretations** (estimated zone, suspected fault).

**Example labels:**
- `Estimated Zone B: partial-band (10–96 Hz) measurement · Moderate confidence`
- `At least Zone C (lower bound): partial-band, compression may under-read · Moderate confidence`
- `ISO 20816-3 not applicable (machine ≤ 15 kW): showing frequency, level and trend only`
- `ISO 20816-3 not applicable (rotordynamic pump → ISO 10816-7, not implemented)`
- `ISO zone not assessed: machine group/support unknown`
- `Below detection limit (< 0.4 mm/s in 10–96 Hz)`
- `Inconclusive: capture timing could not be established`

### A4.4 Agentic loop (summary; full design in §B6)
The evidence states, in order:

`CAPTURE_ASSESSED` → `RECAPTURE_REQUIRED` | `ADDITIONAL_EVIDENCE_REQUIRED` | `VALID_MEASUREMENT` | `INCONCLUSIVE` → `DIAGNOSIS_READY` → `HUMAN_APPROVAL_REQUIRED` → `COMPLETED`

- A **deterministic policy** decides which actions are allowed in each state.
- The **LLM** (Bedrock) chooses among the allowed actions and explains them in plain language.
- A **rule planner** with the same policy takes over if Bedrock fails.
- Numbers and safety thresholds are never produced by the LLM.

## A5. Measurement science and limits (what makes the numbers defensible)

### A5.1 Timebase
- Frequency is only as good as the capture rate. A wrong rate scales every frequency (×8 for 240 vs 30) ✅ (generated files).
- Timing status rules are in §B5.1.
- **No timing → no measurement.**

### A5.2 Detectable band
- Nyquist = fs/2 (120 Hz at 240 fps). We integrate velocity over **10 Hz to min(0.4·fs, 1000) Hz** (= 10–96 Hz at 240 fps; 10–48 Hz at 120 fps).
- Video has **no anti-alias filter**: motion above Nyquist folds into the band. Exposure-time averaging only weakly suppresses it. So the band value can include aliased energy. The harmonic-consistency check flags peaks that are not near n·1×.
- Bearing defect frequencies (typically > 100 Hz) are out of scope.

### A5.3 Relation to ISO values
- ISO uses 10–1000 Hz. Our band is narrower, so for real in-band energy our value is ≤ the full-band value: a **partial-band estimate**.
- Aliased content can push it up. This is why ISO output is always labelled "estimated, partial-band" and its confidence is capped at **Moderate**.

### A5.4 Units and formulas
- Displacement x(t) in mm (marker plane). For one tone, peak amplitude A (mm) at frequency f (Hz):
  - peak velocity = 2πfA
  - RMS velocity = 2πfA/√2 (mm/s)
  - Example: 2.8 mm/s RMS at 25 Hz → peak displacement 25.2 µm ✅.
- Band velocity RMS:
  - v_rms = sqrt(∫_{f_lo}^{f_hi} (2πf)² · P_xx(f) df)
  - P_xx is the one-sided Welch PSD of displacement (mm²/Hz, Hann window, density scaling, linear detrend, 2 s segments, 50% overlap), after a zero-phase 4th-order high-pass at f_lo/2 ✅.
- Tone amplitude: flat-top window (scalloping < 0.1 dB); frequency from zero-padded Hann with parabolic peak interpolation ✅.
- Exposure averaging attenuates a tone by sinc(π f T_e): about 1.8% at 25 Hz with T_e = 1/240 s. Negligible against other errors; listed in the uncertainty budget.

### A5.5 Detection limit and uncertainty (initial model; replace with measured values after §B11)
- **Noise floor:**
  - Displacement PSD median in 5–(0.4·fs) Hz, excluding ±1 Hz around harmonics of 1× and flicker lines.
  - **Noise-equivalent velocity** (NEV) = band RMS computed from that floor.
  - **Detection limit** DL = 3 × NEV.
- **Uncertainty budget** (combined as root-sum-square, reported as ±):

  | Source | Size |
  |---|---|
  | Scale | Ruler reading ±0.5 mm on 40 mm = ±1.3%, plus tilt correction residual |
  | Noise | NEV / v_rms |
  | Compression | Asymmetric (under-read only), from G3 calibration; until then the result class is `LOWER_BOUND` |
  | Camera-motion compensation residual | From the reference rigid-fit residual |
  | Exposure averaging | ≤ 2% |

- **Result classes** (all thresholds are **initial values**, tuned on real recordings in §B11 and then frozen before the final evaluation):

  | Class | Conditions | Display |
  |---|---|---|
  | `INCONCLUSIVE` | timing `UNRELIABLE`; duplicated frames detected; < 90% valid machine-marker frames or no continuous ≥ 4 s segment; invalid homography or tilt > 30°; reference compensation residual > 0.1 px median; **no reference marker** (amplitude only; frequency may still be reported) | Reason + what to do |
  | `BELOW_DETECTION_LIMIT` | 1× peak SNR < 3 | "< DL mm/s" |
  | `LOWER_BOUND` | SNR ≥ 3 and any of: px amplitude at 1× < 0.3 px, compression < 0.05 bits/pixel/frame, SNR < 10 | "≥ value (lower bound)" |
  | `RELIABLE` | SNR ≥ 10, px amplitude ≥ 0.3, ≥ 0.05 bits/pixel/frame, timing ≥ `PROBABLE`, reference OK, **and gate G3 passed** | value ± uncertainty |

- **Why `LOWER_BOUND` points downward:** compression and partial band both bias low 🧪/📄. Noise can add ≤ ~5% at SNR ≥ 3. This assumption is checked in G3.
- **If G3 fails:** the global flag `AMPLITUDE_VALIDATED=false` switches the app to **frequency + relative-trend mode**:
  - shown: frequency, harmonic pattern, relative change between comparable recordings;
  - **not shown:** mm/s and ISO zones.

### A5.6 Camera-motion compensation (why subtraction alone is not enough)
- Camera roll, zoom/focus breathing and translation move the two markers differently. We fit a **similarity transform** (rotation + scale + translation) to the reference marker's 4 corners each frame and map the machine marker through it.
- **Residual error that remains:**
  - **Parallax:** image shift = f·t/Z, so different depths Z₁ ≠ Z₂ leave f·t·|1/Z₁ − 1/Z₂|. Mitigation: similar depth.
  - **Rolling shutter:** rows are exposed at different times. For camera motion at frequency f and row-time offset Δt, the residual ≈ 2πfΔt × camera motion. Δt is up to a few ms; at 24 Hz with Δt = 2 ms that is ~30% of any camera motion **at 1×**. Mitigation: same image rows; tripod not on the machine's base; a check that reports camera motion at 1× (§B5.3).
  - **Lens distortion** near frame edges. Mitigation: keep both markers in the central 60% of the frame.

## A6. Edge cases and how we handle them

| # | Edge case | Risk | Handling | Priority |
|---|---|---|---|---|
| 1 | Slow-mo saved with playback timing (30 fps) | Frequencies off ×4–×8 | Timing status from capture tag + PTS + phone profile; `UNRELIABLE` → recapture/inconclusive (§B5.1) | P0 |
| 2 | Variable frame rate / timestamp jitter | Smeared or biased peaks | Frame-slot assignment; jitter > 10% of dt → `UNRELIABLE`; no linear resampling | P0 |
| 3 | Dropped frames | Phase jumps | Gaps ≤ 3 frames filled by cubic spline; longer gaps split segments; > 5% dropped → `UNRELIABLE` | P0 |
| 4 | Interpolated or duplicated "slow-mo" | Invented motion | **Primary safeguard:** phone-mode verification in G1 (`phone_profiles.json`); unknown phones are capped at `PROBABLE`. **Secondary:** frame-difference cadence check 🧪 catches duplicates and some motion-compensated interpolation, misses blending → warning only, never proof of real capture | P0 (profiles) / P1 (check) |
| 5 | Handheld / tripod shake | False vibration | Similarity compensation from the reference; camera motion RMS > 2 px → recapture | P0 |
| 6 | OIS/EIS stabilisation | Non-rigid warps | Instruct stabilisation off; reference rigid-fit residual check | P0 |
| 7 | Floor or tripod vibrates at 1× | Reference moves at 1× → under/over-read | `ref_or_camera_moving_at_1x` flag → move tripod/reference to another structure | P0 |
| 8 | 100 Hz light flicker (50 Hz mains), LED PWM | False peaks | Brightness spectrum checked separately; flicker lines excluded from peak search; ArUco corners largely insensitive to uniform brightness 🧪 | P0 |
| 9 | Motion above Nyquist aliases | Wrong peaks | Harmonic-consistency check with rpm; label partial-band; bearing frequencies out of scope | P0 |
| 10 | Motor > 3600 rpm at 240 fps | 2× near/above the band | Reduced confidence; fault pattern limited to 1× | P0 |
| 11 | Slow machines (< 600 rpm) | ISO band is 2–1000 Hz | Integrate from 2 Hz only with a valid reference; < 120 rpm → ISO not applicable | P1 |
| 12 | VFD / speed change during recording | Smeared 1× | 1× peak width check (short-time spectra); ask to hold speed steady | P1 |
| 13 | Vibration along the camera axis | Invisible to the camera | Marker side-length oscillation at 1× → ask for a 90° view | P1 |
| 14 | Marker tilted | Scale error | Homography; tilt > 30° (side ratio < 0.87) → recapture | P0 |
| 15 | Low light | Noise | Exposure check + SNR; ask for more light | P0 |
| 16 | H.264/HEVC compression | Under-read amplitude | Result class rules (§A5.5); suggest highest quality | P0 |
| 17 | Rolling shutter | Compensation residual | Same-row placement rule + camera-motion-at-1× check | P0 |
| 18 | Hot (> 70 °C), oily, curved housing | Marker detaches or bends | Laminated marker on magnet or heat-resistant tape; reject if the side ratio is unstable | P1 |
| 19 | Two machines at similar speeds (beats) | Fluctuating amplitude | Close double peaks flagged; ask to isolate | P1 |
| 20 | Healthy machine below the noise floor | False number | `BELOW_DETECTION_LIMIT` with the DL value | P0 |
| 21 | Partial band vs ISO 10–1000 Hz | Over-stated compliance | "Estimated, partial-band", confidence capped at Moderate | P0 |
| 22 | LLM invents numbers or diagnoses | Wrong advice | Numbers only from tools; LLM text checked for digits not in the evidence; the verdict card shows tool values only | P0 |
| 23 | Bedrock throttled or down | Agent stops | Bounded retries, then the rule planner (same policy) | P0 |
| 24 | Large uploads (40–150 MB) | Timeouts | Direct-to-S3 presigned POST; async job; size limits | P0 |
| 25 | Faces in the video | Privacy | YuNet blur on stored outputs; raw video private, 7-day expiry | P1 |
| 26 | User near rotating machinery | Injury | Safety checklist; markers placed only while isolated; stationary parts only | P0 |
| 27 | Wrong marker dictionary or ID | No detection | App PDF only; clear "marker not found" reason | P0 |
| 28 | Close-up framing leaves no room for a reference | No compensation | Reference on a small stand clamped to a wall; without it, amplitude `INCONCLUSIVE`, frequency still reported | P0 |
| 29 | Printer scaled the markers | Scale error | User-entered measured side + ruler bar | P0 |
| 30 | File sent via a messaging app | Recompressed, re-timed | Low bitrate / timing flags → ask for the original file | P0 |
| 31 | iPhone browser picker may transcode or re-time slow-mo ⏳ | Wrong timing | Test in G1; document the working path; probe catches it | P0 |
| 32 | Machine ≤ 15 kW, or an excluded type (rotordynamic/close-coupled pump, reciprocating engine, submerged pump, flexibly supported fan ≤ 300 kW) ✅ scope from the official preview | ISO 20816-3 not applicable | Report "not applicable" with the reason and the relevant other part (e.g. ISO 10816-7); trend + frequency + level only | P0 |
| 33 | Machine info unknown | Wrong group | No zone ("not assessed"); ask once | P0 |
| 34 | Duplicate API requests / double-clicks | Duplicate readings, emails | Idempotency keys + conditional writes (§B7) | P1 |
| 35 | Worker crash mid-job | Lost or duplicated jobs | Leases, heartbeats, ≤ 3 attempts, then `FAILED` with a reason (§B7) | P1 |
| 36 | Approval link forwarded, reused or expired | Wrong approval | Hashed, single-use, 72 h token; POST confirmation; audit (§B7.4) | P1 |
| 37 | Cross-user access | Data leak | Workspace token; every key scoped to the workspace; presigned GETs only for own objects | P0 |
| 38 | Missing marker frames | Biased spectra | NaN handling + segmenting rules (#3) | P0 |
| 39 | Reference at a different depth | Parallax residual | Placement rule; residual included in the uncertainty | P0 |
| 40 | Lens distortion at frame edges | Scale and motion errors | Markers in the central 60% of the frame | P1 |
| 41 | Autofocus hunting / zoom breathing | Scale oscillation | Focus lock; the similarity transform absorbs uniform scale; flag large scale variance | P1 |
| 42 | Exposure-time averaging | Small amplitude loss | ≤ 2% at 25 Hz; in the uncertainty budget | P0 |

## A7. AWS summary
See §B3 and §B9 for details.

| Component | Role |
|---|---|
| **EC2 c8g** (Graviton4, COOL AMI) | FastAPI + job worker + OpenCV pipeline |
| **S3** | Raw uploads (7-day expiry) and results |
| **DynamoDB** | Workspaces, assets, jobs, sessions, readings, work orders |
| **Bedrock** | Agent orchestration (Claude or Nova) |
| **SNS** | Approval notification email |
| **CloudWatch** | Logs, metrics, dashboard, alarms |
| **CloudFront** | HTTPS front door |
| **CloudFormation** | Infrastructure as code |
| **Budgets** | $20 alarm |

## A8. Go/no-go gates and fallbacks

| Gate | When | Pass criterion | If it fails |
|---|---|---|---|
| **G1 Timing** | Thu night | Screen-flip test (§B11.2) shows the capture rate within ±1% of nominal (240 or 120) **through our upload path**, for at least one team phone; `probe_video` reports `PROBABLE` or `CONFIRMED` | Try another phone or transfer path; use 120 fps; if no path works, the product is blocked → escalate immediately |
| **G2 Frequency** | Fri 12:00 | Camera 1× vs accelerometer 1× within **max(0.2 Hz, 1%)** on ≥ 5 fan recordings at ≥ 2 speeds | Debug timing → axis → peak picking for ≤ 4 h. If still failing by Fri 18:00, switch to the backup idea only if a teammate has already prototyped it; otherwise submit a scoped "visual frequency analyser" with documented failure |
| **G3 Amplitude** | Sat 12:00 | For recordings with px amplitude ≥ 0.3 and accelerometer 1× SNR ≥ 10: median absolute velocity error ≤ 25% (camera band velocity vs accelerometer band velocity, same band), and velocity increases monotonically with added mass (Spearman ρ ≥ 0.8) | `AMPLITUDE_VALIDATED=false` → frequency + relative-trend mode; the report shows the amplitude results as a negative finding |
| **G4 Demo readiness** | Sun 12:00 | All P0 items in §B16 pass on the public URL from a phone on mobile data | Cut P1/P2 work and fix P0 |

**Backup idea (only under G2 failure):** a camera smoke-opacity meter for brick kilns and chimneys, in the style of US EPA ALT-082 / ASTM D7520 (📄 digital camera opacity method).

**Cut order if short on time** (from first cut to last): P2 features (markerless, OCR, advanced audio, animations) → x86 benchmark config → SNS email (use in-app approval) → magnification → COOL benchmark.

**Never cut:** timing checks, the measurement pipeline, quality checks, uncertainty-aware diagnosis, the agent loop, the endpoint, real-world evaluation, the video.

## A9. Responsible use and safety
- **Advisory only.** No machine control. A human approves every work order. The agent never claims certified ISO compliance.
- **Honest output.** Every reading shows its band, result class, uncertainty or detection limit, and confidence. "Inconclusive" is a valid outcome.
- **Privacy.**
  - Faces blurred on stored outputs (P1).
  - Private bucket; raw uploads expire after 7 days; results after 30 days.
  - Workspaces isolated.
- **Experiment safety (mandatory for the team):**
  - Attach markers and test masses **only with the machine switched off and unplugged/isolated**. Nobody touches the machine while it runs.
  - Test masses on the fan rig: ≤ 10 g, fully wrapped in strong tape, attached while unplugged. Guard re-installed before power-on. Start at the lowest speed.
  - Nobody stands in the plane of rotation. Eye protection. Stop immediately on any rattle or loosening.
  - Real machines (pump, workshop motor) **only with the owner's or in-charge's permission**, markers on stationary housings only, no masses added.
  - Motorbike: on its stand, ignition off while placing markers, markers away from hot exhaust parts.
- **Claims discipline.** Controlled test-rig faults (added mass, loosened screw) are **not** industrial faults. We do not claim industrial fault-classification accuracy.

---

# Part B: Implementation and submission playbook

## B1. What we submit

| Item | Value |
|---|---|
| **Project name** | VibraLens: phone-camera vibration screening for machines that have no sensors |
| **Tagline** | Film a running motor for 10 s. Get its vibration frequency, an uncertainty-aware level and an agent that tells you what evidence to capture next. |
| **Tracks** | Main competition · **Agentic Vision path** · **COOL path** (tick both) |
| **Problem** | Small factories, mills, pumps and workshops run motors until they fail. Vibration sensors cost ₹10k–₹80k per point 📄, and camera vibration systems cost far more. |
| **Solution** | Phone slow-mo + printed ArUco markers, processed with OpenCV 5: timing validation, sub-pixel tracking, camera-motion compensation, metric scale, spectral analysis. Output: frequency, band velocity with result class and uncertainty, estimated ISO 20816-3 zone **when applicable**, suspected fault pattern, motion-magnified video, comparison with past readings. An evidence-driven Bedrock agent requests better evidence and routes work orders to a human. |
| **Runs on** | AWS Graviton4 (c8g) with COOL; S3, DynamoDB, Bedrock, SNS, CloudWatch, CloudFront, CloudFormation |
| **Proof we will provide** | Accelerometer comparison on real recordings; timing validation; codec study (synthetic + real); agent evaluation of 20 scenarios (Bedrock vs rule planner); COOL vs pip vs x86 benchmark. **All numbers come from `eval/results/` and `bench/results/`.** |

## B2. How we win: each judging criterion → what we do

The judges include **Gary Bradski (OpenCV founder)**: correct, deep, honest computer vision wins.

| Criterion (weight) | What wins it | Our deliverable |
|---|---|---|
| **Technical execution (30%)** | Deep, correct OpenCV 5 use | Timing validation; sub-pixel ArUco with validity checks; homography scale; similarity-transform camera compensation; correct spectral maths (flat-top, Welch); detection limits; result classes; Eulerian magnification; codec-attenuation study |
| **Innovation (20%)** | Something new | A phone as a screening vibrometer, with an agent that manages evidence quality like an analyst |
| **Real-world impact (20%)** | Evidence | Real recordings vs accelerometer; repeatability; detection limit; cost per measurement; technician persona; honest scope |
| **User experience (10%)** | Simple and clear | Guided capture, quality feedback, clear result classes, before/after comparison, "Try a sample" |
| **Documentation and presentation (10%)** | Clarity | Report (§B14.2), architecture + agent diagrams, README, ≤ 5-min video |
| **Cloud, reproducibility, responsible ops (10%)** | Real operations | CloudFormation, pinned dependencies, leases/idempotency, CloudWatch dashboard and alarms, least-privilege IAM, secure approvals, data lifecycle, budget alarm |

**Special awards:**
- **Agentic Vision:**
  - workflow diagram (perception → decision → action);
  - at least 4 traces in which OpenCV output changes the next tool call or action;
  - the 20-scenario evaluation with failure handling, observability and human control (§B12).
- **COOL:**
  - COOL version + instance configuration;
  - proof that COOL executed the workload (`cv2.__file__`, build info);
  - a reproducible benchmark with baselines and raw outputs (§B10).

---

## B3. System design

### B3.1 Architecture

```
          ┌───────────── Browser (phone or laptop), workspace token in localStorage ─────────────┐
          │ Guided capture · Upload · Session (states, agent decisions) · Verdict · Compare · Trace │
          └───────┬──────────────────────────────────────────────────────────┬──────────────────┘
                  │ HTTPS: CloudFront (adds secret origin header)            │ presigned POST (size/type limited)
                  ▼                                                           ▼
┌──────── EC2 c8g (Graviton4, COOL AMI, OpenCV 5) ────────┐        S3  vibralens-<acct>
│ uvicorn/FastAPI (API only, no heavy work)               │         ├─ raw/{ws}/{upload_id}.{ext}   (7-day expiry)
│ worker process: claims jobs via DynamoDB lease          │         ├─ results/{ws}/{job}/...      (30-day expiry)
│   └─ subprocess per job (timeout, memory cap)           │         └─ traces/{ws}/{session}.json
│        └─ OpenCV tools (§B5)                            │
│ agent runner: policy + Bedrock Converse | rule planner  │
└──────┬───────────────┬──────────────┬───────────────────┘
       ▼               ▼              ▼
   DynamoDB          SNS          CloudWatch
   1 table (vl_items) approval     logs (JSON), metrics, dashboard, alarms
                     email
```

### B3.2 Data flow for one session
1. **Workspace.** The browser creates or reuses a workspace (`POST /api/workspaces` → random token, stored in the browser). Everything is scoped to it.
2. **Asset.** The user creates or picks an asset and a measurement point. The capture guide is shown.
3. **Upload.** `POST /api/uploads` returns a presigned POST. The browser uploads the file straight to S3.
4. **Session.** `POST /api/sessions` (with an `Idempotency-Key`) creates a **job** record `QUEUED`, persisted **before** any processing.
5. **Processing.** The worker claims the job (lease). In a subprocess it runs `probe_video` → `check_capture_quality` → (if allowed) `measure_vibration` → `diagnose`. Each result is persisted.
6. **Agent step.** The agent runner advances the **session state machine** (§B6) and picks the next action:
   - a tool,
   - `request_recapture`,
   - `ask_user`,
   - `draft_work_order`,
   - `finish`.
7. **User evidence.** Pausing actions set the session to wait for the user. `POST /api/sessions/{id}/evidence` (idempotent) adds evidence and enqueues a new job.
8. **Approval.** `draft_work_order` creates a work order `PENDING`, then sends an SNS email (exactly once per work order). The supervisor confirms on the approval page (POST), and the session is completed.
9. **Persistence.** Readings are written once per job (conditional write). Comparison uses the asset's history.

### B3.3 DynamoDB data model (on-demand)

**As built:** one table `vl_items`, partition key `pk = "<collection>#<id>"`, with conditional writes for create-if-absent and a `version` attribute for optimistic locking (`vibralens/store.py`). This replaces the six-table design to reduce setup. The collections below keep the same fields. Listing uses a filtered scan, which is fine at demo scale; a GSI on `coll` is the production fix.

| Collection | Keys | Main attributes | Used by |
|---|---|---|---|
| `vl_workspaces` | PK `token_hash` | `workspace_id`, `created_at`, `rate_counter` | auth middleware |
| `vl_assets` | PK `workspace_id`, SK `asset_id` | name, machine_type (enum), coupling (flexible/rigid/close-coupled/unknown), rated_kw (nullable), rated_rpm (nullable), support (rigid/flexible/unknown), group (derived or null), measurement_points[] | assets API, diagnose |
| `vl_jobs` | PK `job_id`; GSI `status-updated` (`status`, `updated_at`) | workspace_id, session_id, kind (analyze/evidence), input_keys, status, attempts, lease_owner, lease_expires, error, idem_key | worker, recovery |
| `vl_sessions` | PK `session_id` | workspace_id, asset_id, point_id, state, pending_action, recapture_count, evidence_requests, llm_steps, mode (bedrock/rules), version (optimistic lock), expires_at (TTL) | agent runner, UI |
| `vl_readings` | PK `asset_id`, SK `ts#job_id` | workspace_id, point_id, view, axis, fs, band, f1x, amp_1x_mm, px_amp_1x, v_band_rms, uncertainty, dl, result_class, timing_status, bitrate, mm_per_px, quality_flags, spectrum_key | history, compare |
| `vl_workorders` | PK `wo_id` (= `session_id#wo`); GSI `token_hash` | workspace_id, asset_id, status (PENDING/APPROVED/REJECTED/EXPIRED), severity, evidence, recommended_action, token_hash, expires_at, notify_state, audit[] | approvals |

---

## B4. Repo layout

```
vibralens/
├─ README.md                  # what, quickstart, deploy, test, evaluation results (from eval/results only)
├─ requirements.txt           # server deps pinned from `pip freeze` in the COOL venv (NO opencv here)
├─ requirements-local.txt     # opencv-python-headless==5.0.0.93 + the same pins, for laptops/CI
├─ phone_profiles.json        # phone models validated by the timing test (G1)
├─ vibralens/
│  ├─ config.py               # env: BUCKET, TABLE_*, BEDROCK_MODEL_ID, REGION, SNS_TOPIC, AMPLITUDE_VALIDATED, thresholds
│  ├─ video.py                # P0 probe_video: timing status, dropped frames, bitrate, interpolation check (P1)
│  ├─ markers.py              # P0 detection, validity, homography, camera compensation
│  ├─ quality.py              # P0 check_capture_quality
│  ├─ signal.py               # P0 slots/resampling, tone, Welch velocity, noise floor, DL, result class
│  ├─ diagnose.py             # P0 ISO applicability/zone, fault patterns, confidence, labels
│  ├─ compare.py              # P1 comparability + change metrics
│  ├─ magnify.py              # P1 Eulerian magnification
│  ├─ audio.py                # P1 basic audio peaks
│  ├─ nameplate.py            # P2 OCR
│  ├─ privacy.py              # P1 YuNet face blur
│  ├─ tools.py                # tool registry: name → fn, JSON schema, priority
│  ├─ policy.py               # P0 evidence state machine + allowed actions + rule planner
│  ├─ agent.py                # P0 Bedrock loop with guard and fallback
│  ├─ jobs.py                 # P0 job records; P1 leases/heartbeats/recovery
│  ├─ store.py                # S3/DynamoDB/SNS helpers, conditional writes
│  ├─ auth.py                 # P0 workspace tokens, scoping
│  ├─ approvals.py            # P1 token create/verify, decide, audit
│  └─ api.py                  # FastAPI routes
├─ worker.py                  # job loop (separate systemd service)
├─ web/                       # index.html, app.js, styles.css, approve.html (no build step)
├─ models/                    # YuNet ONNX (P1), OCR ONNX (P2) + licenses
├─ infra/
│  ├─ stack.yaml              # CloudFormation (§B9)
│  ├─ deploy.sh
│  ├─ vibralens-api.service
│  └─ vibralens-worker.service
├─ bench/
│  ├─ bench_cool.py           # §B10
│  └─ results/                # raw CSV/JSON + env captures per config
├─ eval/
│  ├─ protocol.md             # §B11 (copy)
│  ├─ timing_test.html        # screen-flip page for G1
│  ├─ phyphox_to_velocity.py
│  ├─ run_eval.py             # measurement evaluation → eval/results/
│  ├─ agent_scenarios.yaml    # §B12 scenarios
│  ├─ run_agent_eval.py       # → eval/results/agent_eval_{bedrock,rules}.csv + traces
│  └─ results/
├─ tests/
│  ├─ test_signal.py          # from feasibility/signal_check.py
│  ├─ test_timing.py          # from feasibility/timing_check.py (+ VFR, drops, missing tag)
│  ├─ test_markers.py         # synthetic rotation/zoom/translation compensation, invalid homography, NaN
│  ├─ test_sim.py             # from feasibility/sim.py (short version)
│  ├─ test_diagnose.py        # applicability, labels, no default group
│  ├─ test_policy.py          # state transitions, limits, guard
│  └─ test_api.py             # idempotency, scoping, approval single-use
├─ samples/                   # demo videos (faces checked/blurred) + cached results marked as cached
└─ docs/
   ├─ report.pdf
   ├─ architecture.png
   └─ agent_workflow.png
```

---

## B5. Module specs

> **Rules:**
> 1. Every tool returns a JSON-serialisable dict with `status`, `flags[]`, `reasons[]` and values. The API, agent and evaluation share the same functions.
> 2. Never return a number that the checks did not support. Use the result classes.
> 3. All thresholds live in `config.py` and are listed in the report.

### B5.1 `video.py`: `probe_video(path) -> dict` (P0)

**Sources of timing evidence:**
1. **Capture tag:** any metadata key ending in `capture.fps` (e.g. Android `com.android.capture.fps`) → `fps_tag`.
2. **Presentation timestamps:** `ffprobe -select_streams v:0 -show_entries frame=best_effort_timestamp_time -of csv=p=0` → `pts[]` → `fps_pts = 1/median(diff(pts))`.
3. **Edit lists (MOV/MP4):** repeat (2) with `ffprobe -ignore_editlist 1`. Different results mean time-remapping is present → log both.
4. **Phone profile:** make/model from metadata if present (`com.android.manufacturer/model`, `com.apple.quicktime.make/model`) → `phone_profiles.json` entry created by the G1 timing test. It stores the verified capture fps per mode and the observed file behaviour.
5. **Physical check (optional, supporting only):** if mains flicker is visible, a brightness line at 100 Hz (Indian grid 50 Hz → 100 Hz; the grid is near 50 Hz but not exact) must appear where the chosen timebase predicts it.
6. **Frame count:** `VideoCapture` decoded frame count must equal `len(pts)`. Otherwise `UNRELIABLE` (frame/timestamp misalignment).

**Decision:**
```python
def timing_status(fps_tag, fps_pts, profile, flicker_ok):
    if fps_tag:
        ratio = fps_tag / fps_pts
        if abs(ratio - 1) < 0.02:          # stored at real time, tag agrees
            capture_fps, scale = fps_tag, 1.0
        elif abs(ratio - round(ratio)) < 0.02 and round(ratio) in (2, 4, 8, 16, 32):
            capture_fps, scale = fps_tag, 1 / round(ratio)   # slowed playback: real_t = pts * scale
        else:
            return "UNRELIABLE", None, None
        status = "CONFIRMED" if (profile_agrees(profile, capture_fps) or flicker_ok) else "PROBABLE"
    elif fps_pts >= 100:                    # no tag: assume stored at capture rate
        capture_fps, scale = fps_pts, 1.0
        status = "CONFIRMED" if (profile_agrees(profile, capture_fps) or flicker_ok) else "PROBABLE"
    else:                                   # low stored rate and no tag: cannot know if slowed
        if profile and profile.get("slowmo_stored_as") == round(fps_pts):
            capture_fps = profile["capture_fps"]; scale = fps_pts / capture_fps; status = "PROBABLE"
        else:
            return "UNRELIABLE", None, None
    return status, capture_fps, scale
```

**Other checks:**
- **Jitter and drops:** assign each frame a slot k = round(t/dt).
  - Residual std > 10% of dt, or duplicate slots → `UNRELIABLE`.
  - Missing slots: ≤ 1% → OK; 1–5% → flag `dropped_frames` (confidence down); > 5% → `UNRELIABLE`.
- **Interpolated/duplicated footage:**
  - **Primary (P0):** the phone profile from G1. Only modes verified with the screen-flip test count as real capture. Unknown phones are capped at `PROBABLE`.
  - **Secondary (P1, 🧪, warning only):**
    - mean absolute frame difference in the moving marker ROI, averaged by phase for periods 2, 3, 4, 5 and 8;
    - `max/min > 1.6` → `interpolated_suspected`;
    - > 10% near-zero differences (< 5% of the median) → `duplicated_frames` (blocking: recapture).
  - **Measured in `interp_check.py` (synthetic, H.264):** duplicates detected; motion-compensated interpolation detected (2.23 vs real 1.17); **blending missed** (1.13).
  - The noise-variance version was **rejected**: it gave a false alarm on real 240 fps after encoding.
  - Never reported as proof of real capture.
- **Limits** (reject before processing): duration ≤ 30 s, ≤ 8000 frames, ≤ 3840×2160, codec in {h264, hevc}, ffprobe timeout 30 s.
- **Returns:** `{timing_status, capture_fps, time_scale, fps_tag, fps_pts, fps_pts_noeditlist, n_frames, duration_real_s, width, height, codec, bitrate_mbps, jitter_frac, dropped_frac, duplicated_frames, interpolated_suspected (warning), interp_ratio, make, model, flags[], reasons[]}`.
- **Tests (`tests/test_timing.py`):**
  - real-rate file;
  - slowed + tag (must recover 24.3 Hz within 0.5%);
  - slowed without tag (must be `UNRELIABLE`);
  - VFR jitter 5% (OK) and 15% (`UNRELIABLE`);
  - 2% and 8% dropped frames;
  - mismatched frame count.
  - The cases are generated with ffmpeg as in `feasibility/timing_check.py` ✅.

### B5.2 `markers.py`: detection, validity, scale, compensation (P0)

```python
import cv2 as cv, numpy as np
DICT = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50)
MACHINE_ID, REF_ID = 1, 7

def make_detector():
    p = cv.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 7
    p.cornerRefinementMinAccuracy = 0.001
    p.cornerRefinementMaxIterations = 100
    return cv.aruco.ArucoDetector(DICT, p)

def detect_all(video_path, ids=(MACHINE_ID, REF_ID)):
    """Returns {id: (N,4,2) float64 corners in px, NaN where missing or invalid}."""
    det, cap = make_detector(), cv.VideoCapture(video_path)
    out = {i: [] for i in ids}
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        g = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        c, found, _ = det.detectMarkers(g)
        got = {int(i): cc.reshape(4, 2).astype(np.float64)
               for i, cc in zip(found.ravel(), c)} if found is not None else {}
        for i in ids:
            out[i].append(got.get(i, np.full((4, 2), np.nan)))
    C = {i: np.array(v) for i, v in out.items()}
    for i in ids:
        C[i][~valid_quads(C[i])] = np.nan
    return C

def valid_quads(Q):
    """Per-frame validity: convex, side ratio >= 0.7, area within ±20% of the median area."""
    ok = ~np.isnan(Q).any(axis=(1, 2))
    side = np.linalg.norm(np.roll(Q, -1, axis=1) - Q, axis=2)                  # (N,4)
    area = 0.5 * np.abs(np.einsum('ni,ni->n', Q[:, :, 0], np.roll(Q[:, :, 1], -1, 1))
                        - np.einsum('ni,ni->n', Q[:, :, 1], np.roll(Q[:, :, 0], -1, 1)))
    med = np.nanmedian(area[ok]) if ok.any() else np.nan
    conv = np.array([cv.isContourConvex(q.astype(np.float32)) if k else False for q, k in zip(Q, ok)])
    with np.errstate(invalid="ignore"):
        ratio = side.min(1) / side.max(1)
        return ok & conv & (ratio >= 0.7) & (np.abs(area / med - 1) <= 0.2)

def plane_homography(Cm, marker_mm, fs):
    """Homography image px -> marker plane mm from median corners over the first 0.5 s."""
    ref = np.nanmedian(Cm[: max(1, int(0.5 * fs))], axis=0)
    if np.isnan(ref).any():
        return None, {"reason": "machine marker not visible at start"}
    s = marker_mm
    H, _ = cv.findHomography(ref, np.array([[0, 0], [s, 0], [s, s], [0, s]], float))
    side = np.linalg.norm(np.roll(ref, -1, 0) - ref, axis=1)
    tilt_ratio = side.min() / side.max()          # < 0.87 ≈ tilt > 30° → reject
    if H is None or not np.isfinite(H).all() or tilt_ratio < 0.87:
        return None, {"reason": "invalid homography or marker tilted > 30°", "tilt_ratio": float(tilt_ratio)}
    return H, {"tilt_ratio": float(tilt_ratio), "mm_per_px": float(s / np.median(side))}

def compensate(Cm, Cr):
    """Map the machine-marker centre into the reference frame using a per-frame similarity
    transform fitted to the reference corners. Returns centres (N,2) px and fit residual (N,) px."""
    R0 = np.nanmedian(Cr, axis=0)
    cen = np.full((len(Cm), 2), np.nan)
    res = np.full(len(Cm), np.nan)
    for i in range(len(Cm)):
        if np.isnan(Cr[i]).any() or np.isnan(Cm[i]).any():
            continue
        A, _ = cv.estimateAffinePartial2D(Cr[i], R0, method=cv.LMEDS)
        if A is None:
            continue
        fit = np.c_[Cr[i], np.ones(4)] @ A.T
        res[i] = np.sqrt(np.mean(np.sum((fit - R0) ** 2, axis=1)))
        cen[i] = A @ np.r_[Cm[i].mean(0), 1.0]
    return cen, res

def to_mm(points_px, H):
    p = points_px.reshape(-1, 1, 2).astype(np.float64)
    ok = ~np.isnan(p).any(axis=2).ravel()
    out = np.full((len(points_px), 2), np.nan)
    out[ok] = cv.perspectiveTransform(p[ok], H).reshape(-1, 2)
    return out
```

**Notes and checks:**
- Displacement = `to_mm(compensated centres) − median`. The axes are the marker plane's x/y, reported as "horizontal/vertical on the marker face".
- **Reference consistency:**
  - median rigid-fit residual > 0.1 px → `ref_unreliable`;
  - camera motion (reference corners, uncompensated) RMS > 2 px → `camera_shake`;
  - reference motion amplitude at 1× ≥ 30% of the machine's raw 1× → `ref_or_camera_moving_at_1x`;
  - row difference between markers > 10% of frame height → `rolling_shutter_risk`.
- **No reference** → frequency analysis on the raw machine track allowed; amplitude class `INCONCLUSIVE`.
- **Tests (`tests/test_markers.py`, ⏳):** synthetic frames with known rotation (±0.5°), zoom (±1%), translation and a sinusoidal machine motion. Compensated amplitude within 5% of truth; invalid quads rejected; NaN frames handled.

### B5.3 `quality.py`: `check_capture_quality(...) -> dict` (P0)
All thresholds are initial values, tuned on the first real recordings and then frozen.

| Metric | How | Flag → agent reason code |
|---|---|---|
| `marker_px` | median side length | < 80 → `marker_too_small` (with target frame width) |
| `detect_rate_machine/ref` | valid-frame ratio | machine < 0.9 → `marker_lost`; ref < 0.9 or absent → `ref_missing` |
| `blur` | `cv.Laplacian(roi, cv.CV_64F).var()` on the marker ROI, normalised by the ROI's contrast | below the calibrated threshold → `blurry` |
| `exposure` | ROI mean and clipped fraction | mean < 40 or > 5% clipped → `bad_exposure`/`low_light` |
| `flicker` | ROI mean-brightness spectrum | lines found → `flicker` (info; excluded from the peak search) |
| `tilt_ratio` | from `plane_homography` | < 0.87 → `marker_tilted` |
| `camera_motion_rms_px` | reference uncompensated motion | > 2 → `camera_shake` |
| `ref_fit_residual_px` | from `compensate` | > 0.1 → `ref_unreliable` |
| `ref_or_camera_moving_at_1x` | see §B5.2 | true → `ref_vibrating` |
| `rolling_shutter_risk` | marker row offset | true → instruction to align markers |
| `scale_osc_1x` | side-length oscillation at 1× | > 0.2% → `out_of_plane_suspected` |
| `px_amp_1x` | compensated px amplitude at 1× | < 0.3 → `amplitude_below_reliable` + `recommended_frame_width_mm` |
| `bitrate_mbps` | from probe | < 30 → `low_bitrate` |

`recommended_frame_width_mm` = current frame width × (px_amp_1x / 0.3), bounded to [80, 300] mm. Smaller width = closer.

Worked example: 25.2 µm peak (2.8 mm/s RMS at 25 Hz) needs 0.3 px, so 0.084 mm/px. That is a frame about 108 mm wide at 1280 px, or 161 mm at 1920 px.

### B5.4 `signal.py` (P0; maths tested in `feasibility/signal_check.py` ✅)
- `to_slots(t, x, fs)`:
  - frame-slot assignment (no linear resampling);
  - jitter check;
  - cubic-spline fill for gaps ≤ 3 frames;
  - longer gaps → split; analyse the longest continuous segment ≥ 4 s, else `INCONCLUSIVE`.
- `tone(x, fs, f_hint)`: zero-padded Hann + parabolic frequency; flat-top amplitude.
- `velocity_rms(x_mm, fs, f_lo, f_hi)`: Welch density PSD × (2πf)², integrated over [f_lo, f_hi], after a zero-phase high-pass at f_lo/2. Default band f_lo = 10 Hz; f_hi = min(1000, 0.4·fs).
- `noise_floor` → NEV and DL (§A5.5).
- **1× selection:**
  1. rpm known → search ±5% around rpm/60, and also ±5% around 2·rpm/60 to tolerate 2× dominance; record which.
  2. Otherwise the largest non-flicker peak in 8–60 Hz, labelled `f1x_assumed` (→ the agent may ask for rpm).
- **Harmonic consistency:** peaks above 3× the noise floor that are not within ±2% of n·f1x and not flicker → `unexplained_peaks[]`.
- `result_class(...)` per §A5.5. Also the global `AMPLITUDE_VALIDATED` switch.
- **Returns:** `{fs, band, f1x, f1x_source, amp_1x_mm, amp_2x_mm, amp_3x_mm, amp_half_mm, px_amp_1x, v_band_rms, nev, dl, snr_1x, uncertainty_pct, result_class, unexplained_peaks, spectrum_png_key}`.

### B5.5 `diagnose.py` (P0)

**1. ISO applicability (in this order):**
- `AMPLITUDE_VALIDATED=false` → no zone (trend mode).
- result class not in {`RELIABLE`, `LOWER_BOUND`} → no zone.
- machine type or power unknown → `ISO zone not assessed: machine type/power unknown`.
- **excluded type** (✅ clause 1) → `ISO 20816-3 not applicable (<type> → <other part>)`:
  - rotordynamic or close-coupled pump → ISO 10816-7;
  - reciprocating engine → ISO 10816-6;
  - submerged motor-pump, screw compressor, wind turbine → other parts;
  - electric motor that is **not** flexibly coupled → assess under the driven machine's part.
- fan/blower ≤ 300 kW that is flexibly supported → not applicable (Note 3); classification "to be agreed between manufacturer and customer".
- rated power ≤ 15 kW → `ISO 20816-3 not applicable (≤ 15 kW)`.
- speed unknown or outside 120–30,000 rpm → not applicable / not assessed.
- support unknown → show **both** possibilities: "Estimated zone B (if rigid) / A (if flexible)". Never pick one silently.
- otherwise → the group from power (Group 1 > 300 kW, Group 2 15–300 kW) and the table in §A3.

**2. Label:**
- `RELIABLE` → `Estimated Zone X: partial-band (f_lo–f_hi Hz)`.
- `LOWER_BOUND` → `At least Zone X (lower bound)`.
- Confidence is capped at **Moderate** for any zone.

**3. Suspected fault pattern** (heuristics; always worded "suspected"; confidence Low or Moderate):
- **Imbalance pattern:** 1× ≥ 80% of the harmonic energy, 2× < 0.5·1×, radial view.
- **Misalignment pattern:** 2× ≥ 0.5·1× (radial), or axial 1× ≥ 0.5·radial 1× (needs the axial view).
- **Looseness pattern:** ≥ 3 harmonics > 0.2·1×, or a ½× peak.
- **Unexplained peaks:** "other source / structure / alias".
- **Withheld** when 1× is ambiguous or the audio conflicts (§B6), or the result class is `INCONCLUSIVE`.

**4. Confidence (separate for frequency, level, zone and fault):**
- start at High;
- −1 level for each of: timing `PROBABLE`, `dropped_frames`, `low_bitrate`, `rolling_shutter_risk`, `f1x_assumed`, SNR < 10;
- zone and fault capped at Moderate.

**5. Change criterion (used by `compare_readings`):**
- **ISO-applicable machines:** |Δv| > 0.25 × (zone B upper boundary) 📄.
- **Others:** relative change > 50%. This is a **team heuristic** and is labelled as such in the UI and report.
- Only between **comparable** readings (§B5.6).

**Returns:** `{iso: {applicable, reason, group, support, zone_label, confidence}, fault: {pattern, evidence[], confidence, withheld_reason}, confidence: {...}, limitations[]}`.

### B5.6 `compare.py`: `compare_readings(asset_id, a, b)` (P1)

**Comparable only if all of these hold** (otherwise: "Not comparable" with reasons):
- same measurement point and view (radial/axial) and axis;
- both result classes in {`RELIABLE`, `LOWER_BOUND`};
- same band (fs within 5%);
- f1x within ±5% (similar speed/load);
- mm/px within ±30%;
- same result class (both RELIABLE, or both LOWER_BOUND);
- same marker size.

**Output:**
- overlaid spectra PNG;
- table: f1x before/after, amp_1x, v_band_rms, result class, uncertainty;
- % change **only when comparable**;
- change significant? (per §B5.5);
- setup differences;
- evidence list.

**Alert rule:** only a comparable and significant increase can lead to `HUMAN_APPROVAL_REQUIRED`.

### B5.7 `magnify.py` (P1)
- ROI = 3× the marker size around the machine marker, downscaled to ≤ 480 px.
- 4-level Laplacian pyramid (`pyrDown`/`pyrUp`). Temporal Butterworth bandpass f1x ± 2 Hz (`sosfiltfilt`). α = 20–50 (lower on fine levels). Collapse.
- MP4 at 30 fps playback, side by side with the original.
- Labelled **"visualisation only, not a measurement"**.
- Budget ≤ 30 s CPU for 4 s of video; otherwise use 2 s.

### B5.8 `audio.py` (P1 basic)
- `ffmpeg -i in -vn -ac 1 -ar 8000 out.wav` → FFT peaks 5–1000 Hz. Flag 100 Hz (electrical hum).
- If the audio track is missing or re-timed (duration ≠ real duration ±2%) → `audio_unavailable`.
- Used only to **support or conflict** with f1x. Never overrides vision.

### B5.9 `nameplate.py` (P2)
- OCR via OpenCV Zoo DB detection + CRNN recognition; regex for rpm/kW/HP.
- The P0 path is the user typing rpm/kW.
- Bedrock vision as a fallback, logged.

### B5.10 `privacy.py` (P1)
- YuNet `FaceDetectorYN.create(...)` every 10th frame; blur boxes (held across the frames in between) on stored outputs and samples.
- Raw uploads are never public, and expire after 7 days.

### B5.11 API (FastAPI) (P0 unless marked)

All `/api/*` routes except `/api/workspaces` and `/api/approvals/*` require `Authorization: Bearer <workspace_token>`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/workspaces` | Create a workspace → token (shown once; stored in the browser) |
| GET/POST | `/api/assets` | List/create assets (scoped) |
| GET | `/api/assets/{id}` | Asset + readings (history) |
| POST | `/api/uploads` | `{kind: video\|photo, content_type, size}` → presigned POST `{upload_id, url, fields}` |
| POST | `/api/sessions` | `{asset_id, point_id, view, upload_id, marker_mm}` + `Idempotency-Key` → `{session_id}` |
| POST | `/api/sessions/{id}/evidence` | `{type: video\|photo\|answer, upload_id?, answer?}` + `Idempotency-Key` |
| GET | `/api/sessions/{id}` | state, pending action, verdict, result URLs (presigned GET, 10 min), trace summary |
| GET | `/api/sessions/{id}/trace` | full agent trace (P1) |
| GET | `/api/assets/{id}/compare?a=&b=` | comparison (P1) |
| POST | `/api/approvals/preview` | `{token}` → work-order summary (no state change) (P1) |
| POST | `/api/approvals/decide` | `{token, decision, approver_name, comment}` (P1) |
| GET | `/api/samples` | demo samples (public, read-only) |
| POST | `/api/samples/{id}/run` | replays a sample in the demo workspace (real processing; cached result shown with a "cached on <date>" label until the run finishes) |
| GET | `/healthz` | status, `cv2.__version__`, `cv2.__file__`, COOL HAL lines, model ID |

---

## B6. Agent design

### B6.1 Principles
1. **OpenCV measures; deterministic code decides safety; the LLM orchestrates and explains.**
2. Each turn, the LLM may only call tools that the **policy allows in the current state**. The tool list is filtered per turn.
3. Arguments are validated against JSON schemas. A failed validation or a policy violation → the rule planner's action is used and `policy_override` is logged.
4. Hard limits:
   - ≤ 3 recapture requests;
   - ≤ 2 additional-evidence requests;
   - ≤ 12 LLM turns per job;
   - ≤ 2 retries per tool;
   - user evidence wait ≤ 24 h;
   - approval wait ≤ 72 h.

### B6.2 Evidence states and transitions (implemented in `policy.py`)

```
UPLOAD ─► probe_video + check_capture_quality ─► CAPTURE_ASSESSED
   CAPTURE_ASSESSED:
     timing UNRELIABLE | duplicated_frames | blurry | marker_too_small | marker_lost
     | ref_missing | ref_vibrating | camera_shake | low_light | marker_tilted      ─► RECAPTURE_REQUIRED
     else                                                                          ─► measure_vibration
   after measure_vibration:
     result_class INCONCLUSIVE (fixable by capture)                                ─► RECAPTURE_REQUIRED
     f1x_assumed and no rpm | unexplained dominant peak | audio conflict          ─► ADDITIONAL_EVIDENCE_REQUIRED (rpm / nameplate)
     power or support unknown and rated power could be > 15 kW                     ─► ADDITIONAL_EVIDENCE_REQUIRED (machine info; asked once)
     out_of_plane_suspected                                                        ─► RECAPTURE_REQUIRED (90° view)
     else                                                                          ─► VALID_MEASUREMENT ─► diagnose ─► DIAGNOSIS_READY
   DIAGNOSIS_READY:
     imbalance vs misalignment ambiguous and no axial view                         ─► RECAPTURE_REQUIRED (axial view)
     zone C/D with result_class RELIABLE, or LOWER_BOUND whose value ≥ C boundary,
       or comparable significant increase                                          ─► HUMAN_APPROVAL_REQUIRED
     else                                                                          ─► COMPLETED (magnify + history first, P1)
   HUMAN_APPROVAL_REQUIRED ─► (APPROVED | REJECTED | EXPIRED) ─► COMPLETED
   Limits exceeded | user never responds | unrecoverable error                     ─► INCONCLUSIVE ─► COMPLETED
```

**`BELOW_DETECTION_LIMIT`** → `VALID_MEASUREMENT` with an "< DL" verdict. There is no work order. The user is offered a closer capture if they need a number.

**`LOWER_BOUND` and low bitrate** → `VALID_MEASUREMENT` plus advice. Recapture is forced only if the decision depends on it (e.g. the lower bound sits within one zone of a C boundary).

### B6.3 Tools exposed to the model (Bedrock `toolSpec`; names match `tools.py` and §A4.2)

| Tool | Input schema (summary) | Allowed in states |
|---|---|---|
| `probe_video` | `{upload_id}` | UPLOAD |
| `check_capture_quality` | `{upload_id}` | after probe |
| `measure_vibration` | `{upload_id, rpm?}` | CAPTURE_ASSESSED (no blocking flags) |
| `diagnose` | `{reading_id}` | VALID_MEASUREMENT |
| `compare_readings` | `{asset_id, reading_a, reading_b}` | DIAGNOSIS_READY |
| `get_asset_history` | `{asset_id}` | DIAGNOSIS_READY |
| `audio_peaks` | `{upload_id}` | ADDITIONAL_EVIDENCE_REQUIRED (P1) |
| `read_nameplate` | `{photo_upload_id}` | ADDITIONAL_EVIDENCE_REQUIRED (P2) |
| `magnify` | `{upload_id, f_center}` | DIAGNOSIS_READY (P1) |
| `request_recapture` | `{reason_code (enum), view: radial\|axial\|ninety_deg, target_frame_width_mm?}` | RECAPTURE_REQUIRED (**pauses**) |
| `ask_user` | `{kind: rpm\|machine_info\|nameplate_photo\|choice, question, options?}` | ADDITIONAL_EVIDENCE_REQUIRED (**pauses**) |
| `draft_work_order` | `{severity_label, evidence_ids[], recommended_action}` | HUMAN_APPROVAL_REQUIRED (**pauses**) |
| `finish` | `{outcome: completed\|inconclusive, next_check_days?}` | DIAGNOSIS_READY, INCONCLUSIVE |

User-facing instruction text for `request_recapture` comes from **templates keyed by `reason_code`**, filled with tool values. The LLM adds a short plain-language note.

### B6.4 System prompt (draft)
```
You are VibraLens, a vibration-screening assistant for maintenance technicians.
Each turn, call exactly one of the tools you are given; the list is already filtered to what is
allowed now. Choose the action that best resolves the open evidence problem in the tool results.
Never state, estimate or change numbers: the app shows all values from the tools.
Never claim ISO compliance or a confirmed fault; say "estimated" and "suspected".
If evidence is weak, ask for better evidence or finish as inconclusive. Never control machinery.
Write one short sentence a technician understands, explaining why you chose this action.
```

### B6.5 Loop (Bedrock Converse) with guard and fallback
```python
import boto3, botocore, json
cfg = botocore.config.Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=30)
brt = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=cfg)
PAUSING = {"request_recapture", "ask_user", "draft_work_order", "finish"}

def step_session(sess):
    for _ in range(MAX_LLM_TURNS - sess.llm_turns):
        allowed = policy.allowed_actions(sess)          # deterministic, from evidence state
        rule_choice = policy.rule_planner(sess)          # always computed (fallback + evaluation)
        choice, mode, note = rule_choice, "rules", ""
        if sess.mode == "bedrock":
            try:
                r = brt.converse(modelId=MODEL_ID, system=[{"text": SYSTEM}], messages=sess.messages,
                                 toolConfig={"tools": specs(allowed), "toolChoice": {"any": {}}},
                                 inferenceConfig={"maxTokens": 600, "temperature": 0})
                msg = r["output"]["message"]
                uses = [c["toolUse"] for c in msg["content"] if "toolUse" in c]
                note = " ".join(c.get("text", "") for c in msg["content"]).strip()
                if len(uses) == 1 and uses[0]["name"] in allowed and schema_ok(uses[0]):
                    choice, mode = (uses[0]["name"], uses[0]["input"], uses[0]["toolUseId"]), "bedrock"
                    sess.messages.append(msg)
                else:
                    log_policy_override(sess, uses, rule_choice)
            except Exception as e:                       # throttling, access denied, timeout
                log_fallback(sess, e); sess.mode = "rules"
        note = strip_unsupported_numbers(note, sess.evidence)   # no digits that are not in the evidence
        trace(sess, choice, mode, note)                          # CloudWatch + S3, with latency
        if choice[0] in PAUSING:
            return policy.pause(sess, choice)                    # idempotent state write (version check)
        result = run_tool_once(sess, choice)                     # cached by (session, step, tool, input hash)
        policy.apply(sess, choice, result)                       # updates evidence state
        if mode == "bedrock":
            sess.messages.append({"role": "user", "content": [{"toolResult": {
                "toolUseId": choice[2], "content": [{"json": result}]}}]})
        sess.llm_turns += 1
    return policy.force_inconclusive(sess, "turn limit")
```

**Implementation notes:**
- **Message history.** If the conversation contains rule-mode steps, those tool results are added as a user text summary, so the Converse history stays valid (every `toolUse` is followed by a matching `toolResult`).
- **Resume after a pause.** Append the `toolResult` for the pending pausing call (`{"new_upload_id": ..., "answer": ...}`), then call `step_session`.
- **Model choice.**
  - `MODEL_ID` comes from an environment variable: the Claude inference profile shown in the console, or Amazon Nova Pro.
  - If `toolChoice: any` is rejected by the chosen model, use `auto` and treat a text-only reply as "no valid choice" → rule planner.
- **Observability.**
  - Each trace line is JSON: `{session, job, step, state_before, allowed, chosen, mode, rule_choice, agreed, input, result_summary, note, latency_ms, model}`.
  - Destinations: log group `/vibralens/agent` and `traces/{ws}/{session}.json`.
  - Metrics: `AgentTurns`, `Recaptures`, `PolicyOverrides`, `FallbackActivations`, `ToolLatencyMs` (by tool), `JobFailures`.

### B6.6 Human approval (P1; the state exists in P0)
`HUMAN_APPROVAL_REQUIRED` creates a work order. Without the P1 email flow, the UI shows "Waiting for supervisor approval" with an in-app approve page protected by the same token mechanism (§B7.4). **The system never acts on a machine.**

---

## B7. Backend reliability and security

### B7.1 Job lifecycle (P0 states; P1 recovery)
```
CREATED → QUEUED → RUNNING → (WAITING_USER | WAITING_APPROVAL) → DONE
                       ↘ FAILED (attempts ≥ 3 or non-retryable) ; WAITING_* → EXPIRED (timeout)
```
- **Persist first.** The job record is written (`QUEUED`) **before** any processing.
- **Claiming (P1).** The worker claims a job with a conditional update: `status = QUEUED` OR (`status = RUNNING` AND `lease_expires < now`). It sets the lease owner, `lease_expires = now + 120 s` and `attempts += 1`. A heartbeat extends the lease every 30 s. On worker start, expired leases are re-claimed automatically.
- **Isolation.** Heavy work runs in a **subprocess** with a 300 s timeout and a memory cap (`resource.setrlimit`). A crash marks the attempt failed and the job is retried with backoff (30 s, 120 s). Non-retryable errors (invalid file, timing `UNRELIABLE`) → no retry; the session gets the reason.
- **Agent loop.** Bounded by §B6.1.
- **P0 minimum** (if P1 slips): a single worker; on startup, any `RUNNING` job is set back to `QUEUED` once.

### B7.2 Idempotency (P1)

| Operation | Mechanism |
|---|---|
| `POST /api/sessions`, `POST /evidence` | Require `Idempotency-Key` (UUID from the browser). `job_id = sha256(workspace_id + key)[:32]`. Conditional put `attribute_not_exists(job_id)`; on conflict, return the existing job. |
| Readings | Key `(asset_id, ts#job_id)`, conditional put → one reading per job. |
| Tool calls inside a job | Cached by `(session_id, step, tool, sha256(input))`. |
| Work orders | `wo_id = session_id#wo`, conditional put → at most one per session. |
| Notification | `notify_state` NONE → SENDING (conditional) → publish → SENT. A SENDING state older than 5 min is retried once. At-least-once delivery is documented, and the email says "if you got this twice, the link is the same". |
| Session state | `version` attribute with optimistic locking on every transition. |
| Approval | Conditional update `status = PENDING AND expires_at > now`. |

### B7.3 Uploads and file safety (P0)
- **Presigned POST** (not PUT), so S3 enforces:
  - `content-length-range` 1 KB–300 MB (video) / 15 MB (photo);
  - `Content-Type` ∈ {video/mp4, video/quicktime, image/jpeg, image/png};
  - key fixed by the server: `raw/{workspace_id}/{upload_id}.{ext}`;
  - expiry 15 min.
- **S3 objects appear only when complete.** A partial upload never creates an object; the browser retries the upload. The session API checks `HEAD` (exists, size, type) before creating a job.
- **Validation before analysis:**
  - download to a per-job temp dir (`tempfile.mkdtemp`, deleted after);
  - ffprobe with timeout;
  - limits from §B5.1;
  - photos decoded with `cv.imdecode` after a size check (≤ 50 MP).
  - Reject with a clear reason.
- **Rate limit:** 20 jobs per workspace per hour; Bedrock token budget per session.

### B7.4 Access control and approvals
- **Workspaces (P0):**
  - Token = 32 random bytes (base64url), shown once and stored in the browser.
  - The server stores only its SHA-256.
  - Every DynamoDB query and S3 key is scoped by `workspace_id`; IDs from other workspaces return 404.
  - Results are served through 10-minute presigned GETs, issued only for keys under the caller's workspace prefix.
  - Judges use the public **demo workspace** (read-only samples + sample runs).
  - Documented limitation: this is a capability-token model, not user accounts. Production would use Amazon Cognito.
- **Approval tokens (P1):**
  - 32 random bytes; stored as SHA-256; bound to `wo_id`; expire after 72 h; single use.
  - The email link is `https://<cf-domain>/approve.html#t=<token>`. The fragment is not sent to servers or logs.
  - The page POSTs to `/api/approvals/preview` (shows the work order; no state change). The supervisor types their name and clicks Approve/Reject, which POSTs to `/api/approvals/decide`. **No state change on GET**, so link scanners cannot approve.
  - Verification assumption (documented): possession of the supervisor's inbox. Production: Cognito sign-in.
  - Audit entry appended to the work order: `{ts, decision, approver_name, comment, ip_hash, user_agent}` + a CloudWatch log line.
- **Network:**
  - CloudFront → EC2 origin. The security group allows port 8000 only from the CloudFront origin-facing managed prefix list.
  - The origin requires a secret custom header added by CloudFront.
  - The CloudFront-to-origin leg is HTTP. This is a documented limitation; production would use an ALB with ACM.
- **IAM (least privilege, instance role):**
  - `s3:GetObject/PutObject/DeleteObject` on `bucket/raw/*`, `results/*`, `traces/*` only;
  - DynamoDB item operations on the single table `vl_items`;
  - `bedrock:InvokeModel`/`Converse` on the chosen model/profile ARNs;
  - `sns:Publish` on the topic;
  - CloudWatch `PutMetricData` + logs on the two log groups.
  - No wildcard actions.
- **Secrets:** no tokens in logs (log hashes only); env file readable only by the service user; SSH restricted to the team's IPs.
- **Retention:**
  - S3 lifecycle: `raw/` 7 days, `results/` and `traces/` 30 days;
  - DynamoDB TTL on sessions (30 days);
  - readings kept (they are the asset history);
  - `DELETE /api/assets/{id}` (P2).

---

## B8. Web app (vanilla HTML/JS, served by FastAPI behind CloudFront)

**Design rules:**
- Plain language. High contrast (WCAG AA). Colour plus text/icon for every status. Large tap targets. Works on a phone.
- Every screen has loading, error (with retry) and processing states. Polling every 2 s with backoff on errors.

**Screens:**
1. **Home (P0):**
   - Assets; "New asset".
   - **"Try a sample"** buttons: *Healthy fan · Fan with added mass · Bad capture (marker too small) · Timing problem*.
   - Each sample shows "real recording made on <date>, processed live; cached result shown while it runs".
2. **Capture guide (P0):**
   - The steps of §A4.1 with pictures; the marker PDF with a ruler bar; a "measured marker side (mm)" field; the safety checklist (required tick).
   - Machine info fields with "unknown" options.
   - Upload with a progress bar (`accept="video/*"`).
3. **Session view (P0):**
   - A timeline of evidence states: Uploaded → Capture assessed → Measured → Diagnosed → (Approval) → Completed.
   - **Agent panel:** each decision as a card: action, reason code in plain words, the OpenCV evidence that caused it (e.g. "Marker is 46 px wide; needs ≥ 80 px"), and the assistant's note.
   - When paused, a big instruction card with the exact fix (e.g. "Move closer: frame ≈ 15 cm wide") and an upload/answer button.
   - **Capture-quality checklist** with ✓/✗ per check.
4. **Verdict card (P0):**
   - **Observed (measurements):** 1× frequency (rpm equivalent), band velocity with result class and ± uncertainty or "< DL", band, timing status, quality summary.
   - **Interpreted:** ISO line (estimated/partial-band/confidence, or not applicable/not assessed), suspected fault pattern with evidence bullets and confidence.
   - **Limitations** (always visible): partial band, compression, single-plane view, test-rig vs industrial.
   - **Evidence used:** a list of recordings/photos/answers with timestamps.
   - Spectrum plot (1×/2× markers, DL line); magnified video (P1); "Download report (JSON)".
   - **Inconclusive** verdicts get the same card with the reason and the next step, never an empty or fake number.
5. **Compare (P1):** pick two readings; spectra overlay; before/after table; % change only if comparable; otherwise "Not comparable because…"; the agent's follow-up recommendation.
6. **Trace view (P1):** the full agent trace table (state, allowed actions, chosen, mode, agreed with rules, latency).
7. **Approve page (P1):** work-order summary with evidence; name field; Approve/Reject; confirmation; expired/used states.

---

## B9. AWS setup: step by step

**Regions:** ap-south-1 (Mumbai) for EC2/S3/DynamoDB/SNS/CloudWatch. Bedrock: the inference profile that works for the account (check from Mumbai; otherwise call us-east-1; cross-region API calls are fine).

### Step 1: account and instance (Cloud lead, Thu, P0)
1. Upgrade one account to the **Paid plan**.
2. **Budgets:** $20 monthly, alerts at 50% and 90%.
3. Bedrock → Model access: request Claude (use-case form) and Amazon Nova Pro.
4. Marketplace: subscribe to **"Cloud Optimized OpenCV for AWS Graviton4"** (7-day trial; $0.01/h software fee on c8g.large/xlarge afterwards 📄).
5. Launch **c8g.xlarge** (4 vCPU) from the COOL AMI:
   - 30 GB gp3; instance profile from the stack.
   - Security group: 22 from team IPs; 8000 from the CloudFront prefix list.
   - c8g.xlarge gives the benchmark meaningful multi-thread numbers. If budget is tight, use c8g.large for serving.
6. Verify and **save the output** to `bench/results/env_cool.txt`:
   ```bash
   ls /opt/cool/venvs/
   source /opt/cool/venvs/python_3.12/bin/activate
   python - <<'EOF'
   import cv2, sys, platform
   print(sys.version); print(platform.machine())
   print(cv2.__version__); print(cv2.__file__)
   print(cv2.getBuildInformation())
   EOF
   uname -a; lscpu; pip freeze
   ```
   - **If 5.x:** the app runs in the COOL venv. ✅ Both requirements are met.
   - **If 4.x:** the app runs on pip OpenCV 5 (requirement met); COOL appears only in the benchmark (the pipeline must also run on 4.x: ArUco `ArucoDetector` exists since 4.7). State this honestly.
7. Install: `sudo apt-get install -y ffmpeg` (record `ffmpeg -version`). In the COOL venv: `pip install fastapi uvicorn boto3 scipy jsonschema psutil`. **Do not** install or upgrade `opencv-*` or `numpy` there (it would shadow COOL or break its ABI). Then `pip freeze > requirements.txt`.

### Step 2: `infra/stack.yaml` (CloudFormation)
- **S3 bucket:** block public access; SSE-S3; CORS for POST from the CloudFront domain; lifecycle (`raw/` 7 d, `results/` + `traces/` 30 d).
- **DynamoDB:** one table `vl_items` (pk = `<collection>#<id>`), PAY_PER_REQUEST, TTL attribute `expires_at_ttl` (as built; see §B3.3).
- **SNS:** topic + email subscription (parameter). **Confirm the subscription email on Thu.**
- **IAM:** role + instance profile (§B7.4).
- **Logs:** groups `/vibralens/api`, `/vibralens/agent` (14-day retention). Metric filters + alarms:
  - `JobFailures > 3 in 15 min`;
  - health check failure;
  - budget.
- **CloudFront:** origin = EC2 public DNS:8000 with a secret custom header; viewer HTTPS only; caching disabled for `/api/*`; static `/web/*` cached briefly.
- **Health alarm:** Route 53 health check on `/healthz` (or a 5-minute EventBridge-scheduled check), with a CloudWatch alarm → SNS.

Deploy:
```bash
aws cloudformation deploy --stack-name vibralens --template-file infra/stack.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides AlertEmail=<team-email> Ec2Dns=<dns> OriginSecret=<random>
```

### Step 3: app deploy (`infra/deploy.sh`)
```bash
rsync -az --exclude samples/raw ./ ubuntu@$HOST:/opt/vibralens
ssh ubuntu@$HOST 'source /opt/cool/venvs/python_3.12/bin/activate && \
  pip install -r /opt/vibralens/requirements.txt && \
  sudo cp /opt/vibralens/infra/vibralens-*.service /etc/systemd/system/ && \
  sudo systemctl daemon-reload && sudo systemctl enable --now vibralens-api vibralens-worker'
```
- Both units use `Restart=always` and `EnvironmentFile=/etc/vibralens.env` (mode 600).
- The API runs `uvicorn vibralens.api:app --host 0.0.0.0 --port 8000 --workers 2`; the worker runs `python worker.py`.
- **Reproducibility check (P1):** deploy from scratch on a clean instance using only the README, before Sunday.

### Step 4: cost (judging window Oct 27 → Nov 9, always on) 📄 prices
| Item | Cost |
|---|---|
| c8g.xlarge (~$0.11/h) + COOL $0.01/h, 14 days | ≈ $40 |
| c8g.large instead (~$0.054/h + $0.01/h) | ≈ $21.5 |
| Bedrock | a few dollars (bounded turns, `maxTokens` 600) |
| S3, DynamoDB, CloudFront, SNS, CloudWatch | cents to ~$2 |

**Decision:** after benchmarking, **downsize to c8g.large for the judging window** (same AMI; stop, change type, start). The budget alarm catches anything unusual. **Prices must be confirmed in the console.**

---

## B10. COOL benchmark protocol (`bench/bench_cool.py`) (P1)

**Goal:** a reproducible, honest comparison. **No speedup is claimed unless measured.**

| Config | Instance | OpenCV | What the comparison isolates |
|---|---|---|---|
| A | c8g.xlarge (Graviton4) | **COOL venv** | — |
| B | same instance, same session | fresh venv: `opencv-python-headless==5.0.0.93` (+ same numpy/scipy versions as A if possible) | **A vs B = effect of the COOL build** (same hardware) |
| C | c7i.xlarge (x86, same vCPU count) | pip 5.0.0.93 | **B vs C = effect of hardware/architecture** (not COOL) |

**Inputs:** the same 20 videos (fixed list, SHA-256 recorded) from the evaluation set, plus micro-benchmarks of the operations we use: `cvtColor`, `detectMarkers`, `cornerSubPix`, `findHomography`, `pyrDown`, `pyrUp`, `resize`, `GaussianBlur`, `warpAffine`, on fixed frames.

**Procedure:**
- **Threads:**
  - single-thread: `cv.setNumThreads(1)`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`;
  - multi-thread: OpenCV default; record `cv.getNumThreads()`;
  - numpy/scipy threads fixed to 1 in **both** modes, so OpenCV is what varies.
- **Repetition:** 2 warm-up runs (discarded), then 10 measured runs per video and op.
  - Record wall time (`time.perf_counter`) and process CPU time (`psutil`).
  - CPU utilisation = CPU time / (wall × cores).
- **Throughput:** process all 20 videos with 1 and with N parallel jobs (N = vCPUs) → videos/hour.
- **Cost:** $/1000 videos = (instance $/h + software $/h) / (videos/h) × 1000, using console prices recorded with the date.
- **Report:**
  - median, IQR and p90 per tool and per video;
  - A/B and B/C ratios with 95% bootstrap confidence intervals;
  - which ops changed and which didn't.

**Evidence COOL actually ran:**
- for each config: `cv2.__file__`, `cv2.__version__`, the HAL/parallel lines from `getBuildInformation()`, `uname -a`, `lscpu`, `pip freeze`, instance type (from instance metadata), AMI ID;
- all saved raw in `bench/results/<config>/`.

**Honesty rules:**
- If A ≈ B for some ops, say so. Issue #30373 suggests similar single-thread speed 📄.
- Never attribute B-vs-C differences to COOL.
- Instance C runs ≈ 1 h, then is terminated.

---

## B11. Measurement evaluation (P0; the highest technical priority)

### B11.1 Equipment
- Pedestal or table fan with a guard (3 speeds); 2 g / 5 g / 10 g test masses; strong tape.
- Android phone with phyphox (check that "Acceleration (without g)" runs at ≥ 400 Hz).
- The capture phone(s); tripod; printed markers (40 mm and 25 mm) + ruler.
- A laptop or monitor (60 Hz) for the timing test.
- With permission: a hostel water pump, a workshop motor or lathe; a motorbike.

### B11.2 Timing test (gate G1)
1. Open `eval/timing_test.html` on a 60 Hz monitor or laptop. It alternates full black/white **every display refresh** (a 30 Hz square wave, using `requestAnimationFrame`) and shows a frame counter.
2. Film it for 10 s in each slow-motion mode (240, 120) and upload it **through the real app path** (browser picker; and on iPhone, each transfer method we plan to recommend).
3. `probe_video` + a brightness FFT must give the **30.0 Hz fundamental within ±1%** in physical time, using the timebase from §B5.1. Also check the refresh rate of the display (some laptops run at 59.94 or 120 Hz; detect it with the counter).
4. Record per phone model and mode in `phone_profiles.json`: `{make, model, mode, capture_fps, stored_fps, tag_present, upload_path, verified_on}`.
5. **Fail** → that phone/path is marked unsupported in the app.

### B11.3 Ground truth (accelerometer)
- Tape the phyphox phone firmly to the stationary housing next to the marker, with an axis aligned with the camera's x axis.
- Start both recordings and make a sharp tap on the housing at the start for alignment.
- `eval/phyphox_to_velocity.py`:
  - resample the accelerometer to uniform (it has its own jitter);
  - Welch PSD of acceleration → velocity PSD = P_aa/(2πf)²;
  - integrate over **the same band** as the camera;
  - 1× via the same `tone()`.
- **Velocity comparison is defensible only if:** accelerometer 1× SNR ≥ 10, its sample rate ≥ 4 × f_hi (otherwise compare only in a band below its own 0.4·fs, and say so), and alignment is known.
- **Limitations (in the report):** phone-accelerometer noise and unknown internal filtering; sample-time jitter; mass loading by the phone (it changes the fan's response; compare camera vs accelerometer only on the same recordings); tape-mount resonance; single axis.

### B11.4 Test matrix (target ≥ 45 recordings; every attempt logged, including failures)
| Rig | Conditions | Repeats | Purpose |
|---|---|---|---|
| Fan (guard on) | speeds {1, 2, 3} × mass {0, 2 g, 5 g, 10 g} | 2 | frequency, amplitude, trend |
| Fan | speed 2, mass 5 g, **repeatability** | 5 | variance |
| Fan | loosened base screw (secured, speed 1–2) | 2 | pattern demo (test rig) |
| Fan | distance sweep: frame width 12 / 20 / 35 / 60 cm at 5 g | 1 each | detection limit vs scale |
| Fan | quality settings: highest vs default vs re-encoded copy (crf 30) | 1 each | real codec effect |
| Fan | lighting: daylight vs LED-only (flicker) | 1 each | flicker handling |
| Pump/motor (with permission) | normal operation | 3 | real machine (no fault claims) |
| Motorbike idle | normal | 2 | different frequency range |
| Bad captures (agent scenarios) | see §B12 | 1 each | agent behaviour |

### B11.5 Metrics (all computed by `eval/run_eval.py` into `eval/results/`)
1. **Frequency error:** |f1x_cam − f1x_acc| (Hz and %). Report median, max, and the number of recordings.
2. **Velocity agreement:** Bland–Altman (bias, limits of agreement) of camera vs accelerometer band velocity, split by px amplitude (< 0.1, 0.1–0.3, ≥ 0.3) and by bitrate.
3. **Repeatability:** coefficient of variation over the 5 repeats.
4. **Trend:** Spearman ρ of velocity vs added mass, per speed.
5. **Detection limit:** NEV/DL vs frame width.
6. **Result-class accuracy:** were `RELIABLE` readings actually within the claimed uncertainty? Were `LOWER_BOUND` readings actually ≤ the accelerometer?
7. **Codec effect on real data:** highest quality vs re-encoded copy.
8. **Failure gallery:** every failed or inconclusive recording with its reason.

**Rules:**
- Fan faults are **controlled test-rig conditions**. No industrial fault-classification accuracy is claimed.
- Thresholds are tuned on the first ~10 recordings (a "development" set), then frozen. The remaining recordings form the **reported** set. Both sets are listed.

---

## B12. Agent evaluation (P1; traces are needed for the Agentic award)

**Harness:**
- `eval/agent_scenarios.yaml` defines each scenario.
- `eval/run_agent_eval.py --planner bedrock|rules` runs every scenario through the real API/worker, or through the tool layer with recorded outputs.
- **Fixture types:** **V** = real recording (from §B11); **S** = synthetic file (`feasibility/` generators); **J** = recorded tool output (JSON) replayed; **F** = fault injection.

| # | Scenario | Fixture | Expected tool invocations | Expected decision / state | Failure handling checked |
|---|---|---|---|---|---|
| 1 | Healthy machine, valid recording | V fan 0 g | probe → quality → measure → diagnose → history | `COMPLETED`; no recapture | — |
| 2 | Imbalanced machine, valid recording, healthy baseline exists | V fan 10 g | … → diagnose → compare_readings | `HUMAN_APPROVAL_REQUIRED` → draft_work_order (only if comparable and significant) | non-comparable → no alert |
| 3 | Blurry recording | V defocused | probe → quality | `RECAPTURE_REQUIRED` (`blurry`) | — |
| 4 | Marker too small | V far | probe → quality | `RECAPTURE_REQUIRED` (`marker_too_small`, target width) | — |
| 5 | Missing reference marker | V no ref | probe → quality | `RECAPTURE_REQUIRED` (`ref_missing`); if the limit is reached → frequency-only result, amplitude `INCONCLUSIVE` | — |
| 6 | Vibrating reference | V ref on the fan's table | probe → quality → measure | `RECAPTURE_REQUIRED` (`ref_vibrating`) | — |
| 7 | Ambiguous rotational frequency | J (dominant peak not harmonic-consistent, no rpm) | … → measure | `ADDITIONAL_EVIDENCE_REQUIRED` → ask_user(rpm) → measure(rpm) | wrong rpm entered → still inconsistent → fault withheld |
| 8 | Incorrect/uncertain FPS | S (slowed, no tag) | probe | `RECAPTURE_REQUIRED` (timing; "upload the original file") | no measurement attempted |
| 9 | Interpolated/duplicated slow-mo | S: three variants from `interp_check.py` (duplicated, motion-compensated, blended) + V if a phone mode exists | probe | duplicated → `RECAPTURE_REQUIRED` (`duplicated_frames`); motion-compensated → warning + timing capped at `PROBABLE`; **blended expected to be missed** (documented limitation; only the phone profile protects) | — |
| 10 | Low-bitrate recording | V re-encoded at crf 30 | … → measure | `VALID_MEASUREMENT` with `LOWER_BOUND` + advice (no forced recapture unless decision-relevant) | — |
| 11 | Poor lighting | V dim | probe → quality | `RECAPTURE_REQUIRED` (`low_light`) | — |
| 12 | Camera shake | V handheld | probe → quality | `RECAPTURE_REQUIRED` (`camera_shake`) | — |
| 13 | Out-of-plane vibration | J/S (scale oscillation at 1×) | … → measure | `RECAPTURE_REQUIRED` (90° view) | counts toward the limit |
| 14 | Conflicting visual and audio evidence | J | … → audio_peaks | `ADDITIONAL_EVIDENCE_REQUIRED` (rpm/nameplate); if still conflicting → fault withheld, `COMPLETED` (inconclusive fault) | — |
| 15 | Below detection limit | V healthy, wide frame | … → measure → diagnose | `COMPLETED` with "< DL"; no work order | — |
| 16 | High vibration with reliable evidence | V fan 10 g close + baseline | … → compare | `HUMAN_APPROVAL_REQUIRED` | — |
| 17 | Bedrock unavailable/throttled | F (bad model ID; injected `ThrottlingException`) | same as the rule planner | same final state as rules; `FallbackActivations` = 1 | trace shows mode switch |
| 18 | User never provides the requested evidence | F (clock advanced 24 h) | — | `EXPIRED` → `COMPLETED` (inconclusive) | no dangling jobs |
| 19 | Maximum recapture limit reached | F (4 bad uploads in a row) | probe/quality ×4 | after the 3rd request → `INCONCLUSIVE` → `COMPLETED` | no 4th request |
| 20 | Duplicate/retried action | F (same `Idempotency-Key` twice; double approve; worker killed mid-job) | — | one job, one reading, one work order, one email; the second approve → "already decided" | lease recovery completes the job |

**Recorded per scenario and planner (CSV columns):** `scenario, planner, input_evidence, expected_tools, actual_tools, expected_state, actual_state, correct, recaptures, unnecessary_recaptures, invalid_diagnosis, completed, recovered, latency_ms_total, llm_turns, policy_overrides, trace_key, notes`.

**Metrics (Bedrock vs rules):**
- decision accuracy (per decision point);
- unnecessary recaptures;
- task completion rate;
- **invalid diagnoses** (a zone or fault issued where the expected result is inconclusive; target 0, enforced by the policy but still measured);
- failure recovery (17–20);
- median latency.

**Award traces:** pick ≥ 4 traces (e.g. scenarios 4, 6, 7, 16) showing the OpenCV value → state change → different next tool. Export them as annotated tables in the report and show one in the video.

---

## B13. Priority schedule (now → Mon 27 Oct 10:00 IST)

### B13.1 Priority list
| Priority | Items (owner) |
|---|---|
| **P0 (must work)** | 1. Real-camera timing and frequency validation (C + A) · 2. Correct measurement pipeline: `video`, `markers`, `signal` (A) · 3. Capture-quality checks (A) · 4. Uncertainty-aware diagnosis + result classes (A) · 5. Evidence-driven agent loop: `policy`, rule planner, Bedrock with guard (B) · 6. Functional AWS endpoint: EC2 + S3 + DynamoDB + CloudFront, workspaces, basic job persistence (B) · 7. Real-world evaluation (C) · 8. Working judge demo: samples + verdict + agent panel (C) |
| **P1 (important)** | 1. COOL benchmark (B) · 2. Agent evaluation + traces (B + C) · 3. Human approval: SNS + secure approval page (B) · 4. Persistent job recovery: leases, idempotency (B) · 5. Diagnostic history comparison (A) · 6. Technical report + reproducibility: CloudFormation, clean deploy, README (all) · also: magnification, basic audio check, face blur, CloudWatch dashboard |
| **P2 (stretch; only after all P0 pass)** | Markerless tracking (LK/XFeat) · nameplate OCR · audio analysis beyond the basic check · extra animations and UI polish · asset deletion endpoint · x86 config of the benchmark (moves to P1 if time allows) |

**Rule:** a person starts P1 only when their own P0 items pass. Nobody starts P2 until the whole P0 checklist (§B16 items 1–8) passes on the public URL.

### B13.2 Timeline
**Roles:** A = Vision lead, B = Cloud + Agent lead, C = Data, Eval, UI and Docs lead. (With 2 people, B also takes the UI and A also takes the docs.)

| When (IST) | A (vision) | B (cloud + agent) | C (data, eval, UI) |
|---|---|---|---|
| **Thu 23, evening** | P0-2: `video.py` (timing status), `signal.py` (port the tested functions), `markers.py` detect/validity/homography | P0-6: account steps 1.1–1.7; COOL version check; stack deploy (S3, DynamoDB, SNS, IAM, logs) | P0-1: markers printed and measured; `timing_test.html`; **G1 timing test**; first fan recordings (0 g, 10 g) + phyphox |
| **Thu, late** | Run on C's recordings → **G2-early** check | FastAPI skeleton: workspaces, presigned POST, `/healthz` | `phyphox_to_velocity.py` |
| **Fri 24, morning** | P0-2/3: `compensate`, `quality.py`, tests (`test_signal`, `test_timing`, `test_markers`) | P0-5: `policy.py` (states, allowed actions, rule planner) + `test_policy.py` | P0-7: fan matrix (speeds × masses), repeatability set |
| **Fri 12:00** | **Gate G2** (frequency) | | |
| **Fri, afternoon** | P0-4: `diagnose.py` (applicability, labels, confidence) + `test_diagnose.py` | P0-5: Bedrock loop with guard and fallback; P0-6: jobs table + worker (basic persistence) | P0-8: UI home, capture guide, upload, session view |
| **Fri, evening** | Tune thresholds on the development set; freeze | Deploy end-to-end behind CloudFront | Verdict card (observed vs interpreted, limitations, evidence used) |
| **Fri 23:59 milestone** | **Phone upload via the public URL → timing → quality → measurement → verdict → agent decisions** | | |
| **Sat 25, morning** | P1-5: `compare.py`; P1: `magnify.py` | P1-1: **COOL benchmark** (A/B configs; C if time) | P0-7: distance sweep, quality, lighting, real pump/motor, motorbike; bad captures for §B12 |
| **Sat 12:00** | **Gate G3** (amplitude) → set `AMPLITUDE_VALIDATED` | | |
| **Sat, afternoon** | `run_eval.py` → metrics, plots; fix the worst error sources | P1-4: leases, idempotency, recovery; P1-3: approval flow + SNS | P0-8: samples (4) + "Try a sample"; compare screen; trace view |
| **Sat, evening** | Freeze code (P0 + finished P1) at **23:59** | P1-2: `run_agent_eval.py` both planners; export traces | Architecture + agent workflow diagrams |
| **Sun 26, morning** | Report: method, measurement science, evaluation, limitations | Report: AWS, security, observability, COOL; clean-instance deploy test; CloudWatch dashboard/alarms | Video: shoot the demo sequence (§B14.3) |
| **Sun 12:00** | **Gate G4** (demo readiness) | | |
| **Sun, afternoon** | Code cleanup, tests green, requirements frozen | Final deploy; smoke test from 2 networks + mobile data | Edit the video ≤ 4:50; upload unlisted |
| **Sun, evening** | Proofread report → PDF | Devpost draft saved | §B14.4 checklist review |
| **Mon 27, 07:00–09:00** | — | Final smoke test (URL, samples, approval page, `/healthz`) | Check that the video and repo links open in incognito |
| **Mon 09:00–10:00** | **Submit on Devpost; screenshot the confirmation** | | |
| **Mon 10:00–12:15** | Buffer only. No code changes unless the endpoint is down. | | |
| **Oct 27 → Nov 9** | Keep the endpoint up (downsized instance); check alarms daily | | |

---

## B14. Submission package

### B14.1 Devpost fields (fill numbers **only** from `eval/results/` and `bench/results/`)
- **Inspiration:** "In small mills and pump houses, the first sign of a failing motor is usually the failure itself. Vibration screening would warn weeks earlier, but sensors and analysts are out of reach. Most technicians already carry a slow-motion camera."
- **What it does:** measure (frequency + band level with uncertainty) · grade (estimated ISO zone only when applicable) · explain (suspected pattern + magnified video) · act (the agent requests better evidence, compares history, routes work orders for human approval).
- **How we built it:** OpenCV 5 pipeline (§B5); AWS services (§A7); agent state machine + Bedrock (§B6); COOL on Graviton4 (§B10).
- **Challenges:**
  - slow-mo timing (the 3.04 Hz vs 24.3 Hz trap);
  - codec attenuation of sub-pixel motion;
  - why re-recording at another frame rate cannot resolve aliasing;
  - camera-motion compensation (parallax, rolling shutter);
  - honest ISO scope.
- **Accomplishments:** `[from eval/results: frequency error, velocity agreement, repeatability, detection limit, agent decision accuracy, COOL results]`. Leave out any metric that was not measured.
- **What we learned / next:** rolling-shutter-based super-sampling; markerless tracking; on-device capture app; pilots with local workshops; an accelerometer-validated calibration per phone model.
- **Built with:** opencv, python, fastapi, amazon-ec2, aws-graviton, cool, amazon-bedrock, claude / amazon-nova, amazon-s3, amazon-dynamodb, amazon-sns, amazon-cloudwatch, amazon-cloudfront, aws-cloudformation.
- **Links:**
  - live URL (CloudFront) + "live screen-share demo available on request";
  - repo: private GitHub with organisers added, or public, or a zip attached;
  - video (YouTube unlisted);
  - report PDF.
- **Paths:** both (COOL + Agentic Vision).

### B14.2 Technical report outline (8–10 pages, `docs/report.pdf`)
1. **Summary:** problem, solution, headline measured results (or explicit "not achieved").
2. **Problem and users:** technician persona; cost of failure and of the alternatives.
3. **OpenCV 5 method:** timing determination; ArUco + validity; homography; camera compensation; spectral maths with equations (§A5.4); figures.
4. **Measurement science:** timebase; band and aliasing; partial-band vs ISO; detection limit and uncertainty; result classes; codec study (synthetic + real); rolling shutter and parallax.
5. **Diagnosis and ISO scope:** applicability rules; secondary-source caveat; labels; confidence; change criterion.
6. **Agentic workflow:** state diagram; tools; policy and guard; fallback; annotated traces; human approval.
7. **AWS deployment:** architecture diagram; reliability (jobs, leases, idempotency); security (workspaces, approvals, IAM, network, retention); observability (dashboard screenshot); cost.
8. **COOL on Graviton4:** environment evidence; protocol; results; interpretation and honesty notes.
9. **Evaluation:** timing test; measurement metrics; agent evaluation (Bedrock vs rules); failure gallery.
10. **Limitations:** from §A5 and §A6 (band, aliasing, compression, single plane, test rig vs industrial, accelerometer reference limits, capability-token auth).
11. **Responsible use and safety:** §A9.
12. **Reproducibility:** repo, pinned dependencies, deploy steps, how to rerun tests, evaluation and benchmark.
13. **Team.**

### B14.3 Demo sequence and video script (≤ 5:00; aim for 4:50)
| Time | Step (required demo sequence) | Content |
|---|---|---|
| 0:00–0:20 | Team | Names, college, one-line problem |
| 0:20–0:45 | **1. The real-world problem** | Pump house / workshop footage; cost of sensors and failures |
| 0:45–1:20 | **2–3. Healthy recording** | Upload the fan with no mass → verdict: frequency, band level with class/uncertainty, "ISO not applicable (≤ 15 kW)", limitations visible |
| 1:20–1:50 | **4–5. Poor recording** | Upload a capture with a tiny marker → the agent card: "Marker 46 px; needs ≥ 80 px → move closer, frame ≈ 15 cm" |
| 1:50–2:15 | **6–7. New evidence** | Re-capture → the agent continues → valid measurement |
| 2:15–2:55 | **8. Controlled fault** | Fan with a secured 10 g mass (state "attached while unplugged, guard on") → comparable increase vs baseline → spectra overlay; magnified video |
| 2:55–3:20 | **9. Work order** | Draft → supervisor email → approval page → approve → audit entry |
| 3:20–4:20 | **10. Evidence** | Architecture diagram; an agent trace (OpenCV value → next action); camera vs accelerometer plot; COOL benchmark table (only measured values) |
| 4:20–4:45 | Limitations and responsible use | Partial band, test rig vs industrial, human approval, privacy |
| 4:45–4:50 | Close | "A vibration screening assistant in every technician's pocket" |

### B14.4 Final checklist (each box needs evidence)
- [ ] OpenCV 5 used for substantive analysis (`/healthz` shows the version; the report shows the pipeline)
- [ ] Meaningful AWS execution (EC2 Graviton runs the pipeline; S3, DynamoDB, Bedrock, SNS, CloudWatch, CloudFront)
- [ ] Technical report covering the problem, users, architecture, OpenCV 5 implementation, AWS deployment, evaluation, limitations and responsible use
- [ ] Judge-accessible repository or archive
- [ ] Pinned dependencies (`requirements*.txt`, `ffmpeg -version`, AMI ID) + build, deploy and test instructions, **tested on a clean instance**
- [ ] Architecture diagram (OpenCV 5 + AWS + COOL + agent)
- [ ] Agent workflow diagram (states, perception → decision → action, human approval)
- [ ] Working endpoint + "Try a sample" + live screen-share offer
- [ ] Demo samples (faces checked)
- [ ] Video ≤ 5:00, public/unlisted, showing the team, the app working, the architecture and the results
- [ ] Reproducible evaluation (`eval/run_eval.py`, `eval/run_agent_eval.py`) with failure cases
- [ ] **Agentic Vision evidence:** diagram, ≥ 4 traces, 20-scenario results, failure handling, observability, human control
- [ ] **COOL evidence:** version, instance and AMI, environment captures, method, inputs, baselines, raw results
- [ ] Limitations and responsible-use sections
- [ ] No unsupported claims: every number in Devpost/report/video traced to a results file
- [ ] All team members on the Devpost submission
- [ ] Submitted before 10:00 IST Mon 27; confirmation screenshot saved

---

## B15. Risk register

| Risk | Probability | Impact | Mitigation / fallback |
|---|---|---|---|
| Phone/upload path gives unreliable timing | Med | Fatal | G1 Thu night; phone profiles; recommend the working path; probe rejects bad files |
| Real-phone frequency disagrees with the accelerometer | Med | Fatal | G2; debug order: timing → axis → peak picking; backup plan per §A8 |
| Real amplitude disagrees | Med–High | High | G3 → frequency + relative-trend mode; negative result reported honestly |
| COOL AMI is OpenCV 4.x | Med | COOL-award fit only | App on pip OpenCV 5; COOL in the benchmark; stated honestly |
| Paid-plan / Marketplace delay | Low–Med | Delays | Start on pip OpenCV 5 on any Graviton instance + Nova; switch later |
| Bedrock access denied or slow | Med | Agent quality | Nova; the rule planner always works (same policy) |
| ISO values wrong (secondary sources) | Low–Med | Credibility | Cite sources; "estimated"; seek the primary text; zone only when applicable |
| Magnification too slow | Med | UX | Downscale, shorter clip, async; P1 |
| No access to a real industrial machine | Med | Impact evidence | Hostel pump, workshop, motorbike; clearly labelled |
| Endpoint down during judging | Low | High | systemd restart; health alarm → SNS; screen-share offer |
| Duplicate emails or work orders | Low | Med | Idempotency (§B7.2) |
| Running out of time | High | Med | Priority rules (§B13.1); cut order (§A8) |
| Overspending | Low | Med | Budget alarm; downsize after the benchmark; terminate config C |
| Unsafe experiment | Low | Severe | §A9 safety rules are mandatory; stop on any doubt |

---

## B16. Definition of done (rank-#1 bar)
1. **Timing:** G1 passed for at least one phone/path; probe rejects bad timing (tests green).
2. **Measurement:** the pipeline gives correct frequencies on real recordings (G2), with result classes and uncertainty; amplitude per G3 outcome.
3. **Quality checks** produce the right flags on the bad-capture recordings.
4. **Diagnosis** never shows a zone when the standard is not applicable or the inputs are unknown; labels as in §A4.3.
5. **Agent:** states and policy work; Bedrock + rule planner; limits enforced; traces logged.
6. **Endpoint:** a public URL works from a phone on mobile data; workspaces isolated.
7. **Evaluation:** `eval/results/` contains the measurement metrics and failure gallery.
8. **Demo:** "Try a sample" works in ≤ 30 s, plus the live flow of §B14.3.
9. (P1) COOL benchmark results with environment evidence; agent evaluation of 20 scenarios; secure approval; recovery and idempotency tests; comparison screen; report + clean-deploy check.
10. Every box in §B14.4 ticked; submitted by 10:00 IST Monday.

---

## B17. Consistency audit and open items

### B17.1 Audit performed on this version
| Check | Result |
|---|---|
| Formulas and units | v_rms = 2πfA/√2 (mm/s, A in mm); Welch density PSD × (2πf)² integrated over the band; 25.2 µm example; frame-width example (0.3 px ↔ 0.084 mm/px ↔ ~11–16 cm at 1280–1920 px). Code tested in `signal_check.py` ✅ |
| Thresholds | ISO values 📄 with sources and caveats; every pipeline threshold marked "initial, tuned on the development set, then frozen"; the non-ISO change threshold labelled as a team heuristic |
| Module interfaces | Tool names identical in §A4.2, §B5, §B6.3 and `tools.py`; `measure_vibration` replaces the older `measure_displacement` + `spectrum` pair |
| Agent schemas vs implementation | §B6.3 inputs use `upload_id`/`reading_id`, matching the API (§B5.11) and the tables (§B3.3) |
| API vs frontend | Every UI screen in §B8 maps to an endpoint in §B5.11 (samples, sessions, evidence, compare, trace, approvals) |
| DynamoDB vs operations | Scoping (`workspace_id`), job claiming (GSI on status), single reading per job (SK contains `job_id`), single work order per session, token lookup (GSI), TTL |
| AWS responsibilities | One role per component (§A7) |
| Failure states | Every job/session state has a timeout or recovery path (§B6.1, §B7.1) |
| Tests vs requirements | Timing, signal, markers, diagnose, policy, API idempotency/scoping/approval each have a test file (§B4) |
| Priorities | Every feature in §A4.2, §A6, §B5 and §B8 has P0/P1/P2 |
| Dependencies | COOL venv: no opencv/numpy changes; local: `opencv-python-headless==5.0.0.93` (non-contrib, matches APIs used ✅); Python 3.12 (COOL) vs 3.11 (local) both supported by the packages used; ffmpeg from apt |
| Security assumptions | Capability tokens, email-inbox possession for approval, CloudFront→origin HTTP: all documented as limitations |
| Award requirements | Agentic (§B2, §B6, §B12), COOL (§B9, §B10), general (§B14.4) |
| Deadlines | IST/PT conversion checked; internal target 10:00 IST; buffer kept |
| Contradictions removed | No default ISO group; no unconditional mm/s; no GET approvals; no in-memory-only jobs; no "verified" claims without evidence |

### B17.2 Open items (must be resolved or stated as limitations)
- ⏳ COOL OpenCV version on the instance (§B9, step 1.6). Needs the team's AWS account; no AWS CLI or credentials exist on the dev laptop.
- ✅ ISO 20816-3 scope, exclusions and band (official preview, 23 Oct). 📄 Zone values and the 25% change criterion are still secondary; the full text is needed.
- ⏳ Phone timing and the iPhone upload path (G1). No phone slow-mo files exist on the dev laptop (25 local videos checked by metadata only: all 30 fps screen recordings).
- 🧪 Interpolation check: v1 rejected; v2 partial (§A2). Real phone footage still untested.
- ⏳ Real codec attenuation and amplitude accuracy (G3).
- ⏳ Bedrock model access, and `toolChoice: any` support for the chosen model.
- ⏳ All evaluation and benchmark numbers. **Nothing in Devpost, the report or the video may quote a number that is not in `eval/results/` or `bench/results/`.**

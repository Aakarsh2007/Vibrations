# Narrated competition demo

`VibraLens-demo.mp4` is an under-five-minute video with 1280×720 H.264 video and AAC audio. It credits Aakarsh Saxena, displays actual synthetic inputs and a current AWS application screenshot, explains verified measurements and agent decisions, and shows the deployed architecture. The installed Microsoft Zira voice provides explicitly labeled computer-generated narration; it does not impersonate the entrant.

The video demonstrates the deployed AWS prototype with synthetic inputs. It is not a recording of a real machine. It contains a team name credit, not an on-camera recording of Aakarsh. Public viewing: https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-demo.mp4 ; judge guide: https://dhfpmgo5xkqhh.cloudfront.net/judge.html .

## Upload metadata

**Title:** VibraLens | OpenCV 5 Evidence-Driven Vibration Screening | Aakarsh Saxena

**Description:** VibraLens screens synthetic slow-motion machine vibration videos using OpenCV 5 on AWS EC2 with S3 and DynamoDB persistence. It checks capture timing and marker quality, compensates camera motion, estimates the spectrum, compares compatible baselines, and requests human approval for an inspection work order. Solo developer: Aakarsh Saxena. All four bundled workflows passed on the hosted application. No field accuracy or calibrated vibration severity is claimed. Narration is computer generated. Built for the OpenCV AI Competition 2026, powered by AWS.

Upload as **unlisted or public**, then verify playback without signing in. Paste that accessible link into the competition submission. Do not upload private account setup or approval tokens.

## Rebuild

Windows, with `pip install -r video/requirements.txt`:

1. `powershell -File tools/narrate_video.ps1`
2. `python tools/make_video.py`

Narration text and scene content are in `scenes.json`; the plain transcript is `transcript.txt`. `live-ui.png` is the current app capture used in the failure-handling segment. Intermediate audio and segment files stay in `video/build/` and are excluded from the judge archive.

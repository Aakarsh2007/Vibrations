"""Create the Devpost attachment below its 35 MB limit; full video inputs remain in GitHub."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile
import shutil

ROOT=Path(__file__).resolve().parent.parent
git=shutil.which('git') or r'C:\Users\aakar\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe'
names=subprocess.check_output([git,'ls-files','-z'],cwd=ROOT).decode().split('\0')
paths=[ROOT/n for n in names if n and not (n.startswith('samples/') and n.endswith('.mp4'))]
out=ROOT/'dist/VibraLens-Judges.zip'
note='''# VibraLens — judge attachment

Solo developer: Aakarsh Saxena

This attachment fits Devpost's 35 MB limit. It includes the source, report, architecture,
tests, evaluation traces, ground-truth metadata and the 4:22 narrated demo video.
Only the four large synthetic input MP4 files are omitted. They are committed in the full
GitHub repository and included in the full downloadable archive below.

- Working application: https://dhfpmgo5xkqhh.cloudfront.net/
- Judge walkthrough: https://dhfpmgo5xkqhh.cloudfront.net/judge.html
- Full code and sample inputs: https://github.com/Aakarsh2007/Vibrations
- Full archive: https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-submission.zip
- Technical report: docs/TECHNICAL_REPORT.md
- AWS deployment evidence: docs/AWS_DEPLOYMENT.md and eval/results/aws_demo.json
- Narrated video: video/VibraLens-demo.mp4

Use the live application without installing anything. For local sample demonstrations,
clone the full repository so the four videos are present. Install requirements-lock.txt,
run python -m pytest -q tests, then uvicorn vibralens.api:app --port 8000.

Run the healthy baseline first and provide 1458 rpm when requested. Then run the stronger
motion sample in the same browser workspace. It should compare and draft a work order,
pausing for supervisor approval. Tiny-marker and timing-problem inputs request better
recordings. Inspect Assistant decisions and download the evidence report for each session.

Evidence is synthetic only. No real-machine/contact-sensor validation exists. Absolute
vibration severity and ISO zones remain disabled. The verified planner is rules; Bedrock
is optional, and COOL is not used. SNS email requires subscription confirmation.
'''
manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(ROOT))
    z.writestr('START_HERE_FOR_JUDGES.md',note)
    z.writestr('MANIFEST.sha256.json',json.dumps(manifest,indent=2))
assert out.stat().st_size<35_000_000
with zipfile.ZipFile(out) as z:
    assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in manifest.items())
print(f'{out} | {out.stat().st_size/1_000_000:.2f} MB | {len(paths)} project files + judge guide and manifest')

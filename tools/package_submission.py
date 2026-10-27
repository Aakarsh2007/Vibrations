"""Create a judge archive containing source, samples, evidence and documentation only."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "dist"
DEST.mkdir(exist_ok=True)
paths = []
for name in ("vibralens", "web", "samples", "tests", "infra", "docs", "tools", "eval", "feasibility"):
    paths.extend(p for p in (ROOT / name).rglob("*") if p.is_file()
                 and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".part"))
paths.extend(ROOT / n for n in ("README.md", "workflow.md", "requirements.txt", "requirements-lock.txt", ".env.example", "Dockerfile", ".dockerignore") if (ROOT / n).exists())
paths.extend(p for p in (ROOT / "video").glob("*") if p.is_file())
manifest = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}
archive = DEST / "VibraLens-submission.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(paths):
        z.write(p, str(p.relative_to(ROOT)))
    z.writestr("MANIFEST.sha256.json", json.dumps(manifest, indent=2))
print(f"{archive} ({archive.stat().st_size:,} bytes, {len(paths)} files)")

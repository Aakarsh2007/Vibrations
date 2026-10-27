from pathlib import Path
import zipfile
root = Path(__file__).resolve().parent.parent
out = root/'dist/deployment.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for folder in ('vibralens','web','samples','infra'):
        for p in (root/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                z.write(p,p.relative_to(root))
    z.write(root/'requirements-lock.txt','requirements-lock.txt')
print(out, out.stat().st_size)

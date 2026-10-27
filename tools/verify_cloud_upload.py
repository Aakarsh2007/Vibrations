"""Exercise the real presigned S3 phone-upload path without running another analysis."""
import json
from pathlib import Path
import httpx
root = Path(__file__).resolve().parent.parent
w = json.loads((root/'.tools/cloud-workspace.json').read_text())
c = httpx.Client(base_url=w['endpoint'],timeout=120)
h = {'Authorization':'Bearer '+w['workspace_token']}
path = root/'samples/synthetic_good_healthy.mp4'
r = c.post('/api/uploads',headers=h,json={'kind':'video','content_type':'video/mp4','size':path.stat().st_size})
r.raise_for_status()
u = r.json()
assert 'ap-southeast-2' in u['url'], 'Upload was not directed to the regional endpoint'
with path.open('rb') as f:
    result = httpx.post(u['url'],data=u['fields'],files={'file':(path.name,f,'video/mp4')},timeout=180)
result.raise_for_status()
print('Real regional S3 upload passed:',result.status_code, path.stat().st_size,'bytes')

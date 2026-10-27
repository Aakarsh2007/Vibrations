"""Verify the judge endpoint with real AWS-backed sample workflows; save sanitized evidence."""
from pathlib import Path
import json
import sys
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parent.parent
base = sys.argv[1].rstrip('/')
c = httpx.Client(base_url=base, timeout=90)
health = c.get('/healthz')
health.raise_for_status()
health = health.json()
assert health['opencv'].startswith('5.') and health['backend'] == 'aws', health
w = c.post('/api/workspaces').json()
headers = {'Authorization': 'Bearer ' + w['workspace_token']}
(ROOT/'.tools/cloud-workspace.json').write_text(json.dumps({'endpoint':base, **w}),encoding='utf-8')
report = {'endpoint': base, 'health': health, 'evaluation': 'synthetic inputs only', 'sessions': {}}
out = ROOT/'eval/results/aws_demo.json'

def wait(sid):
    deadline = time.time()+900
    while time.time()<deadline:
        r=c.get('/api/sessions/'+sid,headers=headers)
        r.raise_for_status()
        s=r.json()
        if not s['busy']:
            return s
        time.sleep(3)
    raise TimeoutError(sid)

for name in ('healthy-fan','fan-added-mass','bad-capture','timing-problem'):
    start=time.time()
    r=c.post('/api/samples/'+name+'/run',headers={**headers,'Idempotency-Key':str(uuid.uuid4())})
    r.raise_for_status()
    sid=r.json()['session_id']
    s=wait(sid)
    if (s.get('pending') or {}).get('kind')=='ask':
        c.post('/api/sessions/'+sid+'/evidence',headers={**headers,'Idempotency-Key':str(uuid.uuid4())},
               json={'type':'answer','answer':{'rpm':1458}}).raise_for_status()
        s=wait(sid)
    if name=='healthy-fan':
        assert s['state']=='COMPLETED' and abs(s['measurement']['f1x_hz']-24.3)<0.02,s
    if name=='fan-added-mass':
        assert s['state']=='HUMAN_APPROVAL_REQUIRED' and s['comparison']['significant_increase'],s
    if name=='bad-capture':
        assert s['pending']['reason_code']=='marker_too_small',s
    if name=='timing-problem':
        assert s['pending']['reason_code']=='timing_unreliable',s
        assert not any(t['chosen']=='measure_vibration' for t in s['trace']),s
    report['sessions'][name]={'seconds':round(time.time()-start,1),'session':s}
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(name,s['state'],report['sessions'][name]['seconds'],'seconds',flush=True)
print('AWS-backed endpoint checks passed. Work-order approval awaits the supervisor email.',flush=True)

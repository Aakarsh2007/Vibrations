"""Sync the final source archive without uploading its large unchanged synthetic videos again."""
from pathlib import Path
import json,time,zipfile
import boto3
root=Path(__file__).resolve().parent.parent
state=json.loads((root/'vibralens-deployment.json').read_text())
patch=root/'.tools/source-patch.zip'
remote="""from pathlib import Path
import hashlib,json,zipfile,os
web=Path('/opt/vibralens/app/web')
patch=zipfile.ZipFile('/opt/vibralens/source-patch.zip')
manifest=json.loads(patch.read('MANIFEST.sha256.json'))
old=zipfile.ZipFile(web/'VibraLens-submission.zip')
temp=web/'VibraLens-submission.new.zip'
with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as out:
 for name,digest in manifest.items():
  data=patch.read(name) if name in patch.namelist() else old.read(name)
  assert hashlib.sha256(data).hexdigest()==digest,name
  out.writestr(name,data)
 out.writestr('MANIFEST.sha256.json',patch.read('MANIFEST.sha256.json'))
old.close()
os.replace(temp,web/'VibraLens-submission.zip')
for name in ['DEVPOST_FINAL.md','submission-cover.png','VERIFICATION.md']:
 (web/name).write_bytes(patch.read('_public/'+name))
print('Published source archive verified:',len(manifest),'files')
"""
with zipfile.ZipFile(root/'dist/VibraLens-submission.zip') as source,zipfile.ZipFile(patch,'w',zipfile.ZIP_DEFLATED) as z:
    for info in source.infolist():
        if info.file_size<4_000_000:
            z.writestr(info.filename,source.read(info.filename))
    z.writestr('_patch_source.py',remote)
    for name,path in [('DEVPOST_FINAL.md',root/'docs/DEVPOST_FINAL.md'),('submission-cover.png',root/'web/submission-cover.png'),('VERIFICATION.md',root/'docs/VERIFICATION.md')]:
        z.write(path,'_public/'+name)
region=state['region'];s3=boto3.client('s3',region_name=region,endpoint_url=f'https://s3.{region}.amazonaws.com')
key='results/source-patch.zip';s3.upload_file(str(patch),state['deployment_bucket'],key)
url=s3.generate_presigned_url('get_object',Params={'Bucket':state['deployment_bucket'],'Key':key},ExpiresIn=3600)
ssm=boto3.client('ssm',region_name=region)
commands=[f"curl --location --fail '{url}' -o /opt/vibralens/source-patch.zip",'unzip -oq /opt/vibralens/source-patch.zip _patch_source.py -d /opt/vibralens','python3 /opt/vibralens/_patch_source.py']
r=ssm.send_command(InstanceIds=[state['instance_id']],DocumentName='AWS-RunShellScript',Parameters={'commands':commands,'executionTimeout':['600']})
cmd=r['Command']['CommandId'];print('Updating source archive:',cmd,flush=True)
for _ in range(120):
    time.sleep(3)
    try: result=ssm.get_command_invocation(CommandId=cmd,InstanceId=state['instance_id'])
    except ssm.exceptions.InvocationDoesNotExist: continue
    if result['Status'] in ('Pending','InProgress','Delayed'): continue
    assert result['Status']=='Success',result['StandardErrorContent']
    print(result['StandardOutputContent'][-250:],flush=True);break
else: raise TimeoutError('Source patch did not finish')

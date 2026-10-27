"""Publish the prepared judge artifacts through the existing CloudFront app; no secrets included."""
from pathlib import Path
import json
import time
import zipfile
import boto3

root = Path(__file__).resolve().parent.parent
state = json.loads((root/'vibralens-deployment.json').read_text())
artifacts = {
    'judge.html': root/'web/judge.html', 'index.html': root/'web/index.html',
    'VibraLens-demo.mp4': root/'video/VibraLens-demo.mp4',
    'VibraLens-submission.zip': root/'dist/VibraLens-submission.zip',
    'TECHNICAL_REPORT.md': root/'docs/TECHNICAL_REPORT.md',
    'ARCHITECTURE.md': root/'docs/ARCHITECTURE.md',
    'AWS_DEPLOYMENT.md': root/'docs/AWS_DEPLOYMENT.md',
    'aws_demo.json': root/'eval/results/aws_demo.json',
}
release = root/'dist/judge-release.zip'
with zipfile.ZipFile(release,'w',zipfile.ZIP_STORED) as z:
    for name,path in artifacts.items():
        assert path.is_file(), path
        z.write(path,name)
region = state['region']
s3 = boto3.client('s3',region_name=region,endpoint_url=f'https://s3.{region}.amazonaws.com')
key = 'results/judge-release.zip'
s3.upload_file(str(release),state['deployment_bucket'],key)
url = s3.generate_presigned_url('get_object',Params={'Bucket':state['deployment_bucket'],'Key':key},ExpiresIn=3600)
commands = [f"curl --location --fail --retry 5 '{url}' -o /opt/vibralens/judge-release.zip",
            'unzip -oq /opt/vibralens/judge-release.zip -d /opt/vibralens/app/web',
            'chown -R vibralens:vibralens /opt/vibralens/app/web']
ssm = boto3.client('ssm',region_name=region)
r = ssm.send_command(InstanceIds=[state['instance_id']],DocumentName='AWS-RunShellScript',
                     Parameters={'commands':commands,'executionTimeout':['600']})
cmd = r['Command']['CommandId']
print('Publishing judge artifacts:',cmd,flush=True)
for _ in range(120):
    time.sleep(3)
    try:
        status = ssm.get_command_invocation(CommandId=cmd,InstanceId=state['instance_id'])
    except ssm.exceptions.InvocationDoesNotExist:
        continue
    if status['Status'] in ('Pending','InProgress','Delayed'):
        continue
    assert status['Status']=='Success',status['StandardErrorContent']
    print('Published:',state['endpoint']+'/judge.html',flush=True)
    break
else:
    raise TimeoutError('Judge artifact publication did not complete')

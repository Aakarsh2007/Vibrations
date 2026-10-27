"""Resume an interrupted EC2 install with a fresh regional S3 download; no credentials printed."""
import base64
import json
from pathlib import Path
import boto3

state = json.loads(Path('vibralens-deployment.json').read_text())
region, instance = state['region'], state['instance_id']
s3 = boto3.client('s3', region_name=region, endpoint_url=f'https://s3.{region}.amazonaws.com')
ec2 = boto3.client('ec2',region_name=region)
ssm = boto3.client('ssm',region_name=region)
url = s3.generate_presigned_url('get_object',Params={'Bucket':state['deployment_bucket'],'Key':'results/deployment.zip'},ExpiresIn=7200)
userdata = base64.b64decode(ec2.describe_instance_attribute(InstanceId=instance,Attribute='userData')['UserData']['Value']).decode()
tail = userdata[userdata.index('python3 -m venv'):]
script = "#!/bin/bash\nset -euo pipefail\nexec >> /var/log/vibralens-install.log 2>&1\n"
script += f"curl --location --fail --retry 5 '{url}' -o /opt/vibralens/source.zip\n"
script += 'unzip -oq /opt/vibralens/source.zip -d /opt/vibralens/app\n' + tail
r = ssm.send_command(InstanceIds=[instance],DocumentName='AWS-RunShellScript',
                     Parameters={'commands':[script],'executionTimeout':['1800']})
print('Resumed installation. SSM command:',r['Command']['CommandId'])

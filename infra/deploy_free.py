"""Deploy the complete app on EC2 behind CloudFront, without IAM users/access keys.

Run in authenticated AWS CloudShell: python3 deploy_free.py deployment.zip
This consumes Free Plan credits. It never upgrades the account or adds a payment method.
The supplied CloudFormation template creates S3, DynamoDB, SNS and a workload role.
"""
import argparse
import base64
import json
from pathlib import Path
import secrets
import time
import zipfile

import boto3

p = argparse.ArgumentParser()
p.add_argument('archive')
p.add_argument('--region', default='ap-southeast-2')
p.add_argument('--apply', action='store_true', help='Create the reviewed deployment resources')
p.add_argument('--email', help='Supervisor email for the deployment SNS subscription')
args = p.parse_args()
session = boto3.Session(region_name=args.region)
ec2, s3, ssm, cf = [session.client(n) for n in ('ec2', 's3', 'ssm', 'cloudfront')]
s3 = session.client('s3', endpoint_url=f'https://s3.{args.region}.amazonaws.com')
cfn = session.client('cloudformation')
identity = session.client('sts').get_caller_identity()
print(json.dumps({'account': identity['Account'], 'region': args.region,
                  'resources': 'one t3.small Ubuntu EC2, encrypted 16GB EBS, CloudFront, private S3, DynamoDB, SNS, CloudWatch',
                  'persistence': 'S3 and DynamoDB', 'IAM': 'one workload role scoped by the supplied CloudFormation template; no access keys'}, indent=2))
if not args.apply:
    raise SystemExit('Review complete. Add --apply only after authorization and Free Plan verification.')
assert args.email, 'Pass --email for supervisor notification subscription.'
archive = Path(args.archive)
assert archive.is_file(), archive
suffix = secrets.token_hex(4)
secret = secrets.token_urlsafe(40)
stack_name = f'vibralens-{suffix}'
template = zipfile.ZipFile(archive).read('infra/stack.yaml').decode()
parameters = [{'ParameterKey': 'AlertEmail', 'ParameterValue': args.email},
              {'ParameterKey': 'Ec2PublicDns', 'ParameterValue': ''},
              {'ParameterKey': 'OriginSecret', 'ParameterValue': secret}]
cfn.create_stack(StackName=stack_name, TemplateBody=template, Parameters=parameters, Capabilities=['CAPABILITY_IAM'])
print('Creating application storage, notification and workload role:', stack_name, flush=True)
cfn.get_waiter('stack_create_complete').wait(StackName=stack_name)
outputs = {o['OutputKey']: o['OutputValue'] for o in cfn.describe_stacks(StackName=stack_name)['Stacks'][0]['Outputs']}
bucket = outputs['BucketName']
s3.upload_file(str(archive), bucket, 'results/deployment.zip')
url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': 'results/deployment.zip'}, ExpiresIn=7200)
vpcs = ec2.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])['Vpcs']
assert vpcs, 'No default VPC: select/create networking explicitly before deployment.'
vpc = vpcs[0]['VpcId']
subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc]}])['Subnets']
assert subnets, 'No default subnets'
prefix = ec2.describe_managed_prefix_lists(Filters=[{
    'Name': 'prefix-list-name', 'Values': ['com.amazonaws.global.cloudfront.origin-facing']}])['PrefixLists'][0]['PrefixListId']
sg = ec2.create_security_group(GroupName=f'vibralens-{suffix}', Description='VibraLens CloudFront-only origin, no SSH', VpcId=vpc)['GroupId']
ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{
    'IpProtocol': 'tcp', 'FromPort': 8000, 'ToPort': 8000, 'PrefixListIds': [{'PrefixListId': prefix}]}])
ami = ssm.get_parameter(Name='/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id')['Parameter']['Value']
userdata = '''#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/vibralens-install.log) 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv unzip curl
useradd --system --create-home --home-dir /opt/vibralens vibralens
mkdir -p /opt/vibralens/app /opt/vibralens/data
curl --location --fail --retry 5 'SOURCE_URL' -o /opt/vibralens/source.zip
unzip -q /opt/vibralens/source.zip -d /opt/vibralens/app
python3 -m venv /opt/vibralens/venv
/opt/vibralens/venv/bin/pip install -r /opt/vibralens/app/requirements-lock.txt
printf 'VL_BACKEND=aws\nVL_AWS_REGION=REGION_NAME\nVL_BUCKET=BUCKET_NAME\nVL_SNS_TOPIC_ARN=TOPIC_ARN\nVL_DATA_DIR=/opt/vibralens/data\nVL_AMPLITUDE_VALIDATED=false\nVL_DEV=0\nVL_ORIGIN_SECRET=ORIGIN_TOKEN\n' > /etc/vibralens.env
chmod 600 /etc/vibralens.env
chown -R vibralens:vibralens /opt/vibralens
cp /opt/vibralens/app/infra/vibralens.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vibralens
curl --fail --retry 10 --retry-connrefused --retry-delay 3 http://127.0.0.1:8000/healthz
'''.replace('SOURCE_URL', url).replace('ORIGIN_TOKEN', secret).replace('REGION_NAME', args.region).replace('BUCKET_NAME', bucket).replace('TOPIC_ARN', outputs['TopicArn'])
instance = ec2.run_instances(ImageId=ami, InstanceType='t3.small', MinCount=1, MaxCount=1,
    IamInstanceProfile={'Name': outputs['InstanceProfileName']},
    NetworkInterfaces=[{'DeviceIndex': 0, 'SubnetId': subnets[0]['SubnetId'], 'Groups': [sg], 'AssociatePublicIpAddress': True}],
    BlockDeviceMappings=[{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 16, 'VolumeType': 'gp3', 'Encrypted': True, 'DeleteOnTermination': True}}],
    MetadataOptions={'HttpTokens': 'required', 'HttpEndpoint': 'enabled'},
    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'VibraLens-hackathon'}, {'Key': 'Project', 'Value': 'VibraLens'}]}],
    UserData=userdata)['Instances'][0]['InstanceId']
state = {'account': identity['Account'], 'region': args.region, 'instance_id': instance,
         'security_group': sg, 'deployment_bucket': bucket, 'stack_name': stack_name, 'backend': 'aws',
         'note': 'All OpenCV processing runs on EC2; no field validation or COOL claim.'}
Path('vibralens-deployment.json').write_text(json.dumps(state, indent=2))
print('Instance launched:', instance, flush=True)
ec2.get_waiter('instance_running').wait(InstanceIds=[instance])
host = ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]['PublicDnsName']
assert host, 'No public instance DNS; enable default VPC DNS hostnames'
parameters[1]['ParameterValue'] = host
cfn.update_stack(StackName=stack_name, UsePreviousTemplate=True, Parameters=parameters, Capabilities=['CAPABILITY_IAM'])
print('Creating HTTPS endpoint; waiting for CloudFront propagation...', flush=True)
cfn.get_waiter('stack_update_complete').wait(StackName=stack_name)
outputs = {o['OutputKey']: o['OutputValue'] for o in cfn.describe_stacks(StackName=stack_name)['Stacks'][0]['Outputs']}
state.update(endpoint='https://' + outputs['CdnDomain'])
Path('vibralens-deployment.json').write_text(json.dumps(state, indent=2))
print(json.dumps(state, indent=2), flush=True)
for attempt in range(30):
    try:
        ssm.send_command(InstanceIds=[instance], DocumentName='AWS-RunShellScript', Parameters={'commands': [
            "printf '\\nVL_PUBLIC_BASE_URL=" + state['endpoint'] + "\\n' >> /etc/vibralens.env",
            'systemctl restart vibralens']})
        print('Public approval-link origin configured through Systems Manager.', flush=True)
        break
    except ssm.exceptions.InvalidInstanceId:
        time.sleep(10)
print('Boot installation and CloudFront propagation may take several minutes. Verify /healthz then run the four samples.')

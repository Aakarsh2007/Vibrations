"""Deploy the reviewed runtime storage fix via the existing Systems Manager channel."""
import base64
import json
from pathlib import Path
import boto3
root = Path(__file__).resolve().parent.parent
state = json.loads((root/'vibralens-deployment.json').read_text())
payload = base64.b64encode((root/'vibralens/store.py').read_bytes()).decode()
command = 'python3 -c "import base64,pathlib; pathlib.Path(\'/opt/vibralens/app/vibralens/store.py\').write_bytes(base64.b64decode(\''+payload+'\'))"'
r = boto3.client('ssm',region_name=state['region']).send_command(InstanceIds=[state['instance_id']],
    DocumentName='AWS-RunShellScript',Parameters={'commands':[command,'systemctl restart vibralens']})
print(r['Command']['CommandId'])

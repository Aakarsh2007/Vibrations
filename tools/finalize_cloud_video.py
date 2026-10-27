"""Use only after verify_cloud.py has passed all four AWS scenarios."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
e = json.loads((root/'eval/results/aws_demo.json').read_text())
assert len(e['sessions']) == 4 and e['health']['backend'] == 'aws'
p = root/'video/scenes.json'
s = json.loads(p.read_text(encoding='utf-8'))
s[0]['bullets'][2] = 'Synthetic demonstration | AWS execution verified'
s[0]['narration'] = s[0]['narration'].replace('synthetic recordings and a local deployment','synthetic recordings and the deployed AWS application')
s[2]['sample'] = None
s[2]['screenshot'] = 'aws-summary-ui.png'
s[5]['architecture'] = True
s[5]['subtitle'] = 'Verified deployment: OpenCV processing and state run on AWS.'
s[5]['narration'] = (
    'The implemented loop records allowed actions, tool choices, state changes and latency. '
    'The verified AWS demonstration uses the deterministic rule planner. An optional Amazon Bedrock planner '
    'can choose only actions permitted by policy. Work orders use expiring tokens and a single use approval decision. '
    'The local end to end security test accepted one approval and rejected a second with status four hundred and nine. '
    'The running cloud architecture uses EC2 for OpenCV processing, private S3 storage for recordings, DynamoDB '
    'for sessions and jobs, SNS for supervisor requests, and CloudFront for the public HTTPS endpoint. '
    'All four synthetic workflows passed through that deployed application.')
s[6]['bullets'][1] = 'All four bundled workflows passed on AWS'
p.write_text(json.dumps(s,indent=2,ensure_ascii=False),encoding='utf-8')
print('Video narrative updated from verified AWS evidence:',e['endpoint'])

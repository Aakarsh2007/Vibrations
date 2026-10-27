# Deploying VibraLens on AWS

> Deployment creates billable resources. Check your account plan, remaining credits and each service's availability first; this configuration does not guarantee zero cost. Set a budget alert before launch. A budget alert is not a hard spending cap. Review [AWS plan guidance](https://docs.aws.amazon.com/us_en/awsaccountbilling/latest/aboutv2/free-tier-plans.html). No Marketplace/COOL subscription is required.

## 1. One-time account steps (console)
1. Create the account (Free Plan). Region: **Asia Pacific (Mumbai) ap-south-1**.
2. Bedrock → Model access → request **Amazon Nova Lite** (and Nova Pro). If access is refused on the Free Plan, skip it: the app runs with the rule planner (`VL_BEDROCK_MODEL_ID` empty).
3. CloudFormation → Create stack → upload `infra/stack.yaml`. Parameters: `AlertEmail` = supervisor email, `Ec2PublicDns` = empty for now, `OriginSecret` = any random 32+ characters. **Confirm the SNS email.**

### Automated deployment alternative

`infra/deploy_free.py` provisions the same managed storage and notifications, a restricted workload role,
and an Ubuntu **t3.small (x86-64)** instance behind CloudFront. It requires an authenticated AWS CLI
browser-login profile and explicit `--apply`; it never upgrades the account plan or adds payment details.
Install `infra/requirements.txt` for local browser-login signing support. Build the exact source bundle with
`python tools/package_deployment.py`, then run `python infra/deploy_free.py dist/deployment.zip --region ap-southeast-2 --email SUPERVISOR_EMAIL --apply`.
Inspect the printed account and resource list before using `--apply`. The output `vibralens-deployment.json`
contains resource IDs and the endpoint. AWS Free Plan status and available credits must be verified first.
The manual Graviton instructions below remain an alternative; x86 deployment does not claim COOL execution.

## 2. EC2 instance (Graviton, ARM64)
- EC2 → Launch instance:
  - **Ubuntu Server 24.04 LTS (64-bit Arm)**, type **t4g.medium** (or t4g.small).
  - 20 GB gp3.
  - IAM instance profile = the stack output `InstanceProfileName`.
  - Security group: inbound TCP 8000 from the CloudFront origin-facing prefix list (`com.amazonaws.global.cloudfront.origin-facing`). No SSH needed (use Session Manager).
- Connect via Session Manager and run:

```bash
sudo apt-get update && sudo apt-get install -y python3-venv ffmpeg git
sudo useradd -r -m -d /opt/vibralens vibralens || true
sudo -u vibralens git clone <REPO_URL> /opt/vibralens/app     # or copy a zip
cd /opt/vibralens/app
sudo -u vibralens python3 -m venv /opt/vibralens/venv
sudo -u vibralens /opt/vibralens/venv/bin/pip install -r requirements-lock.txt
sudo tee /etc/vibralens.env >/dev/null <<EOF
VL_BACKEND=aws
VL_AWS_REGION=ap-south-1
VL_BUCKET=<BucketName output>
VL_SNS_TOPIC_ARN=<TopicArn output>
VL_ORIGIN_SECRET=<same OriginSecret>
VL_PUBLIC_BASE_URL=https://<CdnDomain output>
VL_BEDROCK_MODEL_ID=<e.g. Nova Lite model or inference-profile id from the console, or empty>
VL_BEDROCK_REGION=ap-south-1
VL_AMPLITUDE_VALIDATED=false
EOF
sudo chmod 600 /etc/vibralens.env
sudo cp infra/vibralens.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now vibralens
curl --fail http://localhost:8000/healthz
```

3. Update the stack with `Ec2PublicDns` = the instance's public DNS → CloudFront is created. Open `https://<CdnDomain>/`.

## 3. Cost control
- Stop the instance when you are not working. Start it again for the judging window (27 Oct–9 Nov).
- Everything else (S3, DynamoDB on-demand, CloudFront, SNS, CloudWatch) is tiny at demo scale.

## 4. Verify and preserve AWS evidence

1. Verify `/healthz` reports OpenCV **5.x** and `backend: aws`; save that response alongside EC2 architecture/instance details.
2. Run the healthy baseline and added-mass samples through the CloudFront endpoint, in one workspace. Answer 1458 rpm if asked. Verify S3 objects and DynamoDB jobs/readings exist.
3. Confirm the SNS email subscription, open the synthetic work-order approval link and record the approved audit state. Production must leave `VL_DEV` unset.
4. Run both failure samples and download the JSON evidence reports. Record whether the planner is rules or Bedrock.
5. Test judge access in a private/incognito window. Keep the host available during judging; retain evidence in the repository/archive.

The template creates a log group, but journald application logs are not automatically shipped there. Use `journalctl -u vibralens` or configure a CloudWatch agent before claiming centralized application logging. CloudWatch metrics are sent by the application. EC2 stopping can change its public DNS on restart; update the CloudFront origin accordingly or deliberately provision a stable address with its associated cost.

## 5. Cleanup

After judging, stop/terminate the EC2 instance and review attached EBS volumes, addresses, S3 objects and CloudFormation resources. Delete only the resources created for this entry after saving evidence. A nonempty S3 bucket can prevent stack deletion. Stopped EC2 instances can still incur storage/address charges.

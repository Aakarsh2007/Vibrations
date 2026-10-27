# Verified AWS deployment

Prepared by Aakarsh Saxena for the OpenCV AI Competition 2026.

- **App:** https://dhfpmgo5xkqhh.cloudfront.net/
- **Judge guide:** https://dhfpmgo5xkqhh.cloudfront.net/judge.html
- **Runtime health:** https://dhfpmgo5xkqhh.cloudfront.net/healthz
- **YouTube video:** https://www.youtube.com/watch?v=dArWXwFDViY
- **Direct MP4 backup:** https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-demo.mp4
- **Code, report and evidence archive:** https://dhfpmgo5xkqhh.cloudfront.net/VibraLens-submission.zip

Region: **ap-southeast-2**. Compute: **Ubuntu 24.04, x86-64, t3.small**. OpenCV runtime: **5.0.0**. Persistence backend: **AWS (S3 + DynamoDB)**. Planner: **rules**; no Bedrock or COOL execution is claimed. EC2 uses a workload role, an encrypted EBS volume and IMDSv2. The origin accepts traffic only from the CloudFront origin-facing prefix list and requires a secret origin header. There is no public SSH rule or permanent IAM access key.

## Hosted validation

`python tools/verify_cloud.py https://dhfpmgo5xkqhh.cloudfront.net` completed all four checks:

| Input | Hosted result | Frequency | Elapsed workflow time |
|---|---|---|---|
| Synthetic baseline | COMPLETED | 24.305 Hz (truth 24.3 Hz) | 74.6 s |
| Synthetic stronger motion | HUMAN_APPROVAL_REQUIRED | 24.301 Hz (truth 24.3 Hz) | 78.0 s |
| Tiny marker | RECAPTURE_REQUIRED: marker_too_small | Withheld | 29.0 s |
| Untagged slowed video | RECAPTURE_REQUIRED: timing_unreliable | Withheld | 13.9 s |

Times include HTTP polling, storage and agent interactions, and are a single demonstration run rather than a statistical performance benchmark. The comparable synthetic pair produced a **1055.7% relative increase** and a work-order draft. The successful local approval/replay test is documented separately; the AWS run leaves its work order pending supervisor approval.

Actual trace and measurement evidence: `eval/results/aws_demo.json`. Internal amplitude estimates in that research artifact remain uncalibrated. No real-machine/contact-sensor validation exists. Absolute mm/s and ISO zones remain disabled.

## Notifications and limits

SNS is configured, but its supervisor subscription was still **PendingConfirmation** at the last check. The supervisor must click the specific SNS subscription confirmation link to receive subsequent work-order requests. This does not block image processing or trace inspection. The source archive and video are hosted as explicit judge artifacts; no account login is needed to view them.

The account's billing page was verified as **Free Plan**, **$100 credits**, **$0 due**, with no usage charges while on that plan. No card was entered and no paid-plan upgrade was performed. Resources consume the free credits and availability ends when the plan/credits expire. Stop/clean up resources after judging. Local cloud-login caches are excluded from all published archives.

## Reproduction

See `infra/deploy.md`, `infra/deploy_free.py`, `infra/stack.yaml`, `infra/requirements.txt` and `tools/package_deployment.py`. The first installation hit a new-bucket S3 redirect; the deployment code now uses the regional S3 endpoint and follows redirects. `infra/resume_install.py` records the recovery procedure. Do not publish EC2 user data or local login caches; those can contain temporary signed URLs or the origin secret.

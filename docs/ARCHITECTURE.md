# Architecture and agent workflow

```mermaid
flowchart LR
  T[Technician phone / browser] --> CF[CloudFront HTTPS]
  CF --> API[EC2: FastAPI + leased worker]
  T -->|Presigned upload| S3[(S3 private recordings)]
  API <--> S3
  API <--> DB[(DynamoDB sessions / jobs / readings)]
  API --> CV[OpenCV 5: timestamps + ArUco + compensation]
  CV --> DSP[Signal analysis + quality evidence]
  DSP --> P[Deterministic action policy]
  P <--> B[Optional Amazon Bedrock planner]
  P --> N[SNS approval request]
  N --> H[Human supervisor]
  H -->|Expiring single-use decision| API
  API --> CW[CloudWatch metrics]
```

This architecture is deployed at https://dhfpmgo5xkqhh.cloudfront.net/ on an Ubuntu x86-64 t3.small instance in ap-southeast-2. The CloudFormation template provisions services and the instance profile; `infra/deploy_free.py` orchestrates EC2 and HTTPS setup. Hosted health and all four sample workflows were verified. See `AWS_DEPLOYMENT.md` and `eval/results/aws_demo.json`. COOL is not integrated, and no Graviton or Bedrock execution is claimed.

```mermaid
flowchart TD
  U[Original recording] --> V[OpenCV: probe capture timing]
  V -->|Unresolved timing / invalid format| R[Ask for original slow-motion capture]
  V -->|Timing supported| Q[OpenCV: marker and reference quality]
  Q -->|Tiny / blurred / moving reference| R2[Specific corrective capture instruction]
  R --> U
  R2 --> U
  Q -->|Adequate evidence| M[Measure compensated displacement + spectrum]
  M -->|Shaft speed uncorroborated| ASK[Ask for nameplate rpm]
  ASK --> M
  M --> D[Screening interpretation]
  D --> C[Compare compatible earlier reading]
  C -->|Increase exceeds heuristic + uncertainty| W[Draft inspection work order]
  W --> A[Wait for human approval / rejection]
  C -->|Insufficient evidence / no increase| F[Finish with limitations]
  R2 -->|Recapture budget exhausted| F
```

Evidence changes the subsequent tool call: identical code requests a closer recording for the tiny-marker sample and halts before measurement for unresolvable playback timing. The baseline/added-mass pair demonstrates comparison-driven escalation. The end-to-end demonstration records actual state transitions and approval replay rejection.

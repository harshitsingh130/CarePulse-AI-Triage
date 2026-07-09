# CarePulse - System Architecture & AWS Resource Inventory

## System Overview

CarePulse is an AI-powered healthcare triage system that guides patients through symptom assessment, scores urgency, routes to specialists, and provides clinical staff with a real-time dashboard for case management.

```
                          +--------------------------+
                          |     CloudFront CDN       |
                          |  d12oqv6vi0inhw.cf.net   |
                          +------------+-------------+
                                       |
                          +------------v-------------+
                          |    S3 Static Portal      |
                          | (React + Vite Frontend)  |
                          +------------+-------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
          +----------v----------+           +-----------v-----------+
          |  REST API Gateway   |           |  WebSocket API GW     |
          | (healthcare-triage) |           | (healthcare-triage-   |
          |   /triage, /admin   |           |       chat)           |
          +----------+----------+           +-----------+-----------+
                     |                                   |
                     |          +--WAF (TriageWAF)--+    |
                     |          | Rate Limit + SQLi |    |
                     |          | + CommonRuleSet   |    |
                     |          +-------------------+    |
                     |                                   |
          +----------v----------+           +-----------v-----------+
          |  Portal API Lambda  |           |  Chat Lambdas         |
          | (triage-portal-api) |           | - chat-connect        |
          +----------+----------+           | - chat-message        |
                     |                      | - chat-disconnect     |
                     |                      +-----------+-----------+
                     |                                  |
     +---------------+----------------------------------+--------+
     |               |               |                           |
+----v----+   +------v------+   +----v---------+   +------------v------+
| Cognito |   |  DynamoDB   |   |Step Functions|   | AI Agent Lambdas  |
|UserPool |   |  (7 tables) |   | (2 machines) |   | (5 specialized)   |
+---------+   +------+------+   +----+---------+   +---+---+---+---+---+
                     |               |                  |   |   |   |
                     |               |         +--------+   |   |   +--------+
                     |               |         |            |   |            |
                     |    +----------v---+  +--v-------+ +--v---v--+  +------v-------+
                     |    |triage-pipeline|  |Symptom   | |Triage   |  |Clinical      |
                     |    |  (Standard)  |  |Assessment| |Scoring  |  |Summary       |
                     |    +-----------+--+  +----------+ +---------+  +--------------+
                     |                |
                     |    +-----------v------+    +------------------+
                     |    |nurse-handoff     |    |Drug Interaction  |
                     |    | (Standard)       |    +------------------+
                     |    +-----------------+     +------------------+
                     |                            |Specialist Routing|
                     |                            +------------------+
                     |
          +----------v---+------+------+------+------+------+
          |sessions|appts|audit |convos|notify|patients|conn |
          +--------+-----+------+------+------+--------+-----+

     +------------------+   +-------------------+   +------------------+
     | KMS (2 keys)     |   | SNS               |   | Secrets Manager  |
     | - PHI encryption |   | - Emergency       |   | - PagerDuty      |
     | - General        |   |   escalation      |   | - Pharmacy stub  |
     +------------------+   +-------------------+   +------------------+
```

---

## AWS Resource Inventory

### Total Resources Deployed: 120 (across 5 CDK stacks)

| CDK Stack | Resources | Purpose |
|-----------|-----------|---------|
| Triage-Shared-dev | 21 | Cognito, DynamoDB, KMS, Secrets |
| Triage-Network-dev | 30 | API Gateway (REST + WS), WAF, Logging |
| Triage-Agents-dev | 24 | 5 AI Agent Lambda functions + IAM |
| Triage-Orchestration-dev | 31 | Orchestration Lambdas, Step Functions, SNS |
| Triage-Portal-dev | 14 | S3, CloudFront, CDN deployment |

---

### Lambda Functions (11 application functions)

| Function | Memory | Timeout | Runtime | Purpose |
|----------|--------|---------|---------|---------|
| triage-portal-api | 256 MB | 10s | Python 3.12 | REST API for patient portal + admin dashboard |
| triage-decision-logic | 256 MB | 10s | Python 3.12 | Session initialization and decision routing |
| triage-chat-message | 512 MB | 60s | Python 3.12 | WebSocket message handler (real-time chat) |
| triage-chat-connect | 128 MB | 5s | Python 3.12 | WebSocket connection handler |
| triage-chat-disconnect | 128 MB | 5s | Python 3.12 | WebSocket disconnection cleanup |
| triage-notification | 256 MB | 30s | Python 3.12 | Email/SNS alerts for escalations |
| triage-symptom-assessment | 512 MB | 15s | Python 3.12 | AI agent: structured symptom gathering |
| triage-triage-scoring | 512 MB | 10s | Python 3.12 | AI agent: urgency level scoring |
| triage-drug-interaction | 256 MB | 10s | Python 3.12 | AI agent: medication interaction checking |
| triage-specialist-routing | 256 MB | 10s | Python 3.12 | AI agent: department routing decisions |
| triage-clinical-summary | 1024 MB | 15s | Python 3.12 | AI agent: SOAP note generation |

### DynamoDB Tables (7 tables, all PAY_PER_REQUEST)

| Table | Partition Key | Sort Key | Items | Size |
|-------|--------------|----------|-------|------|
| triage-sessions | sessionId | — | 95 | 118 KB |
| triage-appointments | patientId | appointmentId | 60 | 14 KB |
| triage-patients | patientId | — | 5 | 1 KB |
| triage-audit-trail | patientId | timestamp | 0 | 0 |
| triage-conversations | sessionId | timestamp | 0 | 0 |
| triage-notifications | sessionId | channel | 0 | 0 |
| triage-connections | connectionId | — | 0 | 0 |

### API Gateway

| API | Type | Endpoint |
|-----|------|----------|
| healthcare-triage-api | REST | https://vvludxq2v0.execute-api.us-west-2.amazonaws.com/prod |
| healthcare-triage-chat | WebSocket | wss://uknl9saewi.execute-api.us-west-2.amazonaws.com/prod |

### Step Functions (2 state machines)

| State Machine | Type | Purpose |
|---------------|------|---------|
| triage-pipeline | STANDARD | Main triage orchestration: symptom assessment -> scoring -> routing -> summary |
| nurse-handoff-standard | STANDARD | Escalation workflow for nurse/physician human-in-the-loop review |

### Other Services

| Service | Resource | Purpose |
|---------|----------|---------|
| Cognito | healthcare-triage-patients (7 users, 4 groups) | Authentication + role-based access |
| CloudFront | E3GZ5BVI5ZUXXL (d12oqv6vi0inhw.cloudfront.net) | CDN for patient portal |
| S3 | healthcare-triage-portal-294680528184-us-west-2 | Static site hosting |
| WAF | TriageWAF | Rate limiting (1000 req/IP), SQLi protection, common rules |
| KMS | triage-phi-key | PHI data encryption at rest |
| KMS | triage-general-key | General-purpose encryption |
| SNS | triage-emergency-escalation | Alert topic for EMERGENCY/URGENT overrides |
| Secrets Manager | /triage/pagerduty | PagerDuty integration credentials |
| Secrets Manager | /triage/pharmacy-stub | Pharmacy API stub credentials |
| CloudWatch | 13 log groups | Lambda, API GW, and Step Functions logging |

---

## Estimated Monthly Cost (us-west-2, dev workload)

Assumes low traffic: ~500 triage sessions/month, 7 users, minimal storage.

| Service | Calculation | Est. Monthly Cost |
|---------|-------------|-------------------|
| **Lambda** | ~5,000 invocations, avg 500ms, avg 350MB | $0.05 |
| **DynamoDB** | PAY_PER_REQUEST, <1000 WCU/RCU per month, <1MB storage | $0.50 |
| **API Gateway REST** | ~10,000 requests/month | $0.04 |
| **API Gateway WebSocket** | ~2,000 connection-minutes | $0.01 |
| **Step Functions** | ~500 Standard transitions (5 states each) | $0.06 |
| **Cognito** | 7 users (first 50,000 MAUs free) | $0.00 |
| **CloudFront** | <1GB transfer, <10,000 requests | $0.00 (free tier) |
| **S3** | <1MB static assets | $0.01 |
| **KMS** | 2 keys + ~1,000 API calls | $2.00 |
| **WAF** | 1 Web ACL + 3 rules + ~10,000 requests | $6.00 |
| **SNS** | <100 email notifications | $0.00 |
| **Secrets Manager** | 2 secrets | $0.80 |
| **CloudWatch Logs** | <10MB ingestion + storage | $0.05 |
| | | |
| **TOTAL (dev, low traffic)** | | **~$9.52/month** |

### Cost at Scale (1,000 sessions/day = ~30,000/month)

| Service | Est. Monthly Cost |
|---------|-------------------|
| Lambda | $15 - $25 |
| DynamoDB | $5 - $15 |
| API Gateway (REST + WS) | $10 - $20 |
| Step Functions | $7 - $12 |
| WAF | $6 - $10 |
| CloudFront | $1 - $5 |
| KMS | $2 - $5 |
| Others (Cognito, SNS, Secrets, Logs) | $3 - $8 |
| **TOTAL (production scale)** | **~$49 - $100/month** |

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Serverless-first | Zero idle cost, auto-scaling, no ops overhead |
| DynamoDB on-demand | Unpredictable triage volume; avoid over-provisioning |
| Step Functions Standard | Need human-in-the-loop (nurse handoff) with wait states |
| WebSocket API | Real-time chat requires persistent connections |
| ARM64 Lambdas | 20% cheaper, better performance for Python workloads |
| KMS + PHI key | HIPAA requirement for PHI encryption at rest |
| WAF | Healthcare compliance: rate limiting + injection protection |
| CloudFront + S3 | Static SPA hosting with global edge caching |
| Cognito groups | Role-based access (admin/nurse/physician/patient) without custom auth |

---

## Security Posture

- All data encrypted at rest (KMS managed keys)
- PHI data uses dedicated PHI key with restricted access policy
- WAF protects API from common attacks (SQLi, rate limiting, OWASP top 10)
- Cognito handles authentication (SRP protocol, no passwords in transit)
- Role-based access via Cognito groups enforced at UI and API level
- CloudFront enforces HTTPS with security headers (HSTS, CSP, X-Frame-Options)
- API Gateway throttling: 50 req/s steady, 100 burst

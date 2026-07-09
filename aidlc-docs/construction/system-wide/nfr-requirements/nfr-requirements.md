# NFR Requirements — System-Wide

## NFR-001: HIPAA Compliance

| Attribute | Requirement |
|---|---|
| **Standard** | HIPAA (Health Insurance Portability and Accountability Act) |
| **Scope** | All components handling PHI |
| **Encryption at rest** | AES-256 via AWS KMS (customer-managed keys) |
| **Encryption in transit** | TLS 1.2+ on all connections (no exceptions) |
| **Access control** | Role-based (patient, nurse, physician, admin), least privilege |
| **Audit trail** | Immutable log of all PHI access and clinical decisions |
| **BAA** | AWS Business Associate Agreement covers all services used |
| **PHI in logs** | Redacted before write to CloudWatch |
| **Data retention** | Sessions: 90 days. Audit: 6+ years. Patient records: until revocation |
| **Right to deletion** | Patient consent revocation stops processing within 24 hours |

### HIPAA-Eligible AWS Services Used

| Service | HIPAA Eligible | BAA Required |
|---|---|---|
| Amazon Bedrock | ✓ | ✓ |
| AWS Lambda | ✓ | ✓ |
| AWS Step Functions | ✓ | ✓ |
| Amazon DynamoDB | ✓ | ✓ |
| Amazon API Gateway | ✓ | ✓ |
| Amazon Cognito | ✓ | ✓ |
| Amazon SNS | ✓ | ✓ |
| Amazon EventBridge | ✓ | ✓ |
| AWS KMS | ✓ | ✓ |
| Amazon CloudWatch | ✓ | ✓ |
| Amazon S3 | ✓ | ✓ |
| Amazon CloudFront | ✓ | ✓ |

---

## NFR-002: Performance

| Metric | Target | Measurement |
|---|---|---|
| Total triage time (patient start → completion) | < 3 minutes (p95) | Step Functions execution duration |
| AI response latency (agent generates response) | < 2 seconds (p95) | Lambda execution time |
| Emergency escalation (classification → notification sent) | < 30 seconds | Custom CloudWatch metric |
| API Gateway REST response | < 500ms (p95) | API Gateway latency metric |
| WebSocket message delivery | < 200ms (p95) | Custom metric |
| Page load (portal) | < 2 seconds (LCP) | Web Vitals |
| Concurrent users supported | 150+ simultaneous | Load test verification |

### Performance Budget Per Agent

| Agent | Max Execution Time | Bedrock Call Budget |
|---|---|---|
| Symptom Assessment (per turn) | 3 seconds | 2 seconds |
| Triage Scoring | 5 seconds | 4 seconds |
| Drug Interaction | 5 seconds | N/A (no LLM) |
| Specialist Routing | 4 seconds | 2 seconds (ambiguous cases only) |
| Clinical Summary | 8 seconds | 5 seconds |

---

## NFR-003: Availability

| Attribute | Target |
|---|---|
| **Uptime** | 99.9% (8.76 hours downtime/year max) |
| **Architecture** | Single region, multi-AZ |
| **RTO** | < 15 minutes (auto-recovery within AZ failover) |
| **RPO** | 0 (DynamoDB multi-AZ, no data loss on single AZ failure) |
| **Deployment** | Zero-downtime (Lambda versioning, API Gateway stage deployment) |
| **Maintenance windows** | None — 24/7 operation |
| **Scaling** | Auto-scaling (Lambda concurrency, DynamoDB on-demand) |

### Failure Modes and Recovery

| Failure | Impact | Recovery |
|---|---|---|
| Single Lambda cold start | +2-3s latency on first invoke | Provisioned concurrency for critical paths |
| DynamoDB single AZ failure | Transparent | Multi-AZ replication (automatic) |
| Bedrock throttling | Scoring/summary delayed | Retry with exponential backoff (3 attempts) |
| API Gateway failure | Portal unreachable | CloudFront custom error page + retry |
| Step Functions failure | Single session lost | Patient reconnects, new session starts |
| WebSocket disconnect | Chat interruption | Auto-reconnect (3 attempts) |

---

## NFR-004: Scalability

| Dimension | MVP (3-5 clinics) | Target (15 clinics) |
|---|---|---|
| Daily triage sessions | 300-500 | 1200+ |
| Peak concurrent sessions | 30-50 | 150+ |
| DynamoDB read capacity | On-demand (auto) | On-demand (auto) |
| Lambda concurrency | Default (1000) | Reserved concurrency for agents |
| Bedrock model throughput | Default quota | Provisioned throughput (if needed) |
| WebSocket connections | Hundreds | Thousands |

### Scaling Strategy
- **Stateless agents** (Lambda) → scale horizontally with no changes
- **DynamoDB on-demand** → auto-scales to any load
- **Step Functions** → no concurrency limit on Express workflows
- **WebSocket API Gateway** → supports 10,000+ concurrent connections
- **Bedrock** → only bottleneck; monitor quotas, request increase for Production

---

## NFR-005: Security (Beyond HIPAA)

| Control | Implementation |
|---|---|
| Input validation | All API inputs validated via schema (Pydantic for Python, Zod for TypeScript) |
| Injection prevention | No dynamic query construction; DynamoDB SDK parameterizes automatically |
| Rate limiting | API Gateway throttling: 100 req/s burst, 50 req/s sustained per patient |
| CORS | Restrict to portal domain only (no wildcard) |
| HTTP security headers | CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy |
| Secrets management | PagerDuty keys, EHR credentials in AWS Secrets Manager (not env vars) |
| IAM least privilege | Per-agent roles with only required permissions |
| No hardcoded credentials | Zero secrets in code; all via Secrets Manager or KMS |
| Dependency scanning | npm audit + pip audit in CI (future — deferred for MVP) |
| WAF | AWS WAF on API Gateway (rate limiting, SQL injection, XSS patterns) |

---

## NFR-006: Observability

| Capability | Implementation |
|---|---|
| Structured logging | JSON format, correlation ID per session, log level filtering |
| Distributed tracing | X-Ray tracing on Lambda + Step Functions + API Gateway |
| Metrics | Custom CloudWatch metrics: triage_duration, escalation_count, confidence_distribution |
| Dashboards | CloudWatch dashboard: session volume, latency, error rate, escalation rate |
| Alerting | SNS alerts: escalation failures, high error rate, SLA breaches |
| PHI redaction | Subscription filter on all log groups → redaction Lambda |

### Key Metrics to Track

| Metric | Type | Alert |
|---|---|---|
| `triage.session.duration` | Timer | > 5 minutes |
| `triage.escalation.triggered` | Counter | — (informational) |
| `triage.escalation.failure` | Counter | > 0 |
| `triage.scoring.confidence` | Histogram | p50 < 0.70 |
| `triage.nurse_handoff.triggered` | Counter | > 20% of sessions |
| `lambda.errors` | Counter | > 5% rate |
| `bedrock.latency` | Timer | > 5 seconds |
| `websocket.disconnects` | Counter | > 10% of sessions |

---

## NFR-007: Maintainability

| Attribute | Approach |
|---|---|
| Code organization | Monorepo, per-unit directories, shared models |
| Type safety | Pydantic models (Python), TypeScript strict mode (frontend + CDK) |
| Testing | Unit tests per agent, integration tests per flow, PBT for scoring + serialization |
| Configuration | Environment-based (dev/staging/prod) via CDK context |
| Documentation | Inline docstrings + this aidlc-docs directory |
| Deployment | CDK deploy (single command), no manual steps |

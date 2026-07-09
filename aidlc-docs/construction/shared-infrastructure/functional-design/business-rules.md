# Business Rules — Shared Infrastructure

## BR-001: PHI Encryption Enforcement

**Rule**: All fields marked `Encrypted: Yes` in domain entities MUST be encrypted using AWS KMS customer-managed keys (CMK) before storage.

**Implementation**:
- DynamoDB tables use server-side encryption with CMK (not default AWS-owned key)
- Two KMS keys: `phi-key` (for PHI fields) and `general-key` (for non-PHI encrypted data)
- Key rotation: automatic annual rotation enabled
- Key policy: only specific IAM roles (agent execution roles) can use the key for encrypt/decrypt

---

## BR-002: Data Retention and TTL

**Rule**: Triage session data is retained for 90 days in the active table. After 90 days, sessions are archived or deleted.

**Implementation**:
- DynamoDB TTL attribute on Sessions table (90 days from createdAt)
- AuditTrail has NO TTL (retained indefinitely for compliance — HIPAA requires 6 years minimum)
- Conversations TTL: 90 days (same as session)
- Patient records: no TTL (persisted until consent revocation)

---

## BR-003: Cognito Authentication Flow

**Rule**: Patient authentication uses custom auth flow (SMS/email OTP + date of birth verification).

**Flow**:
1. Patient initiates auth with phone or email
2. Cognito custom challenge trigger sends OTP via SNS (SMS) or SES (email)
3. Patient submits OTP → Cognito verifies
4. Patient submits DOB → custom verify Lambda checks against Patient record
5. If both pass → Cognito issues tokens (ID token, access token, refresh token)
6. Tokens valid for 1 hour; refresh token valid for 30 days

**Emergency bypass**: Endpoints that return only non-PHI data (e.g., general health guidance, system status) do not require authentication.

---

## BR-004: API Authorization Roles

**Rule**: All API endpoints enforce role-based access control.

| Role | Access Level | Endpoints |
|---|---|---|
| `patient` | Own data only | /triage/*, /appointments/*, /consent/*, /profile (own) |
| `nurse` | Patient data in own clinic + nurse dashboard | /nurse/*, /triage/status/* (all in clinic) |
| `physician` | Patient data for assigned patients | /patients/*, /triage/* (assigned) |
| `admin` | System configuration + all data | /admin/*, all endpoints |

**Enforcement**: Cognito groups + Lambda authorizer validates JWT claims against requested resource.

---

## BR-005: WebSocket Connection Management

**Rule**: WebSocket connections are authenticated and scoped to a single triage session.

**Rules**:
- On `$connect`: validate JWT token, create connection record in DynamoDB (connectionId → patientId + sessionId)
- On `$disconnect`: clean up connection record
- On `sendMessage`: validate that the message sender owns the session
- Idle timeout: disconnect after 10 minutes of no messages (patient may have left)
- Max connection duration: 30 minutes (force reconnect — prevents stale connections)

---

## BR-006: Notification Channel Configuration

**Rule**: Emergency escalation notifications use all configured channels simultaneously.

| Channel | Configuration | Retry Policy |
|---|---|---|
| SMS (SNS) | Promotional → Transactional message type for delivery priority | 3 retries, 30s interval |
| Push (SNS) | Platform application ARN (for mobile app push) | 3 retries, 30s interval |
| PagerDuty | Webhook URL + integration key (stored in Secrets Manager) | 3 retries, 60s interval |
| Live Transfer | WebSocket message to patient + physician connection | No retry (real-time offer) |

---

## BR-007: Audit Trail Immutability

**Rule**: Audit trail records are append-only. No update or delete operations are permitted.

**Implementation**:
- IAM policies for all roles explicitly DENY `dynamodb:DeleteItem` and `dynamodb:UpdateItem` on AuditTrail table
- Only `dynamodb:PutItem` is permitted (new records only)
- Records include `actorId` and `actorType` for every entry (who did what)
- CloudWatch alarms trigger if any Deny is logged against AuditTrail

---

## BR-008: Consent Enforcement

**Rule**: Data processing requires active consent. The system checks consent status before accessing PHI.

**Logic**:
- Before starting triage: verify `consentStatus.dataProcessing == GRANTED`
- Before sharing with specialist: verify `consentStatus.dataSharing == GRANTED`
- Before AI assessment: verify `consentStatus.aiTriage == GRANTED`
- If any required consent is missing: block the operation and prompt patient

**Consent types**:
| Type | Required For | Default |
|---|---|---|
| `dataProcessing` | Any triage session | Required (cannot proceed without) |
| `aiTriage` | AI-assisted assessment | Required (cannot proceed without) |
| `dataSharing` | Sharing with specialists | Required for routing |

---

## BR-009: Cross-AZ Availability

**Rule**: All DynamoDB tables use on-demand capacity mode with no single-AZ dependency.

**Implementation**:
- DynamoDB: on-demand mode (auto-scales, multi-AZ by default)
- Lambda: deployed to multiple AZs automatically
- API Gateway: managed multi-AZ
- Step Functions: managed multi-AZ
- No single points of failure within a region

---

## BR-010: PHI Log Redaction

**Rule**: All CloudWatch log groups used by triage system components have PHI redaction applied.

**Implementation**:
- CloudWatch log subscription filter on all agent log groups
- Lambda processes log events, detects PHI patterns (names, DOB, SSN, medical IDs, phone numbers)
- Redacted version written to the searchable log group
- Original (unredacted) is NOT stored anywhere accessible to developers
- Redaction patterns: configurable regex list maintained in shared config

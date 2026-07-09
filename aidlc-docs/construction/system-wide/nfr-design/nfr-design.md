# NFR Design — System-Wide Patterns

## Pattern 1: PHI Encryption (HIPAA)

### DynamoDB Encryption
```
All tables:
  - Server-side encryption: AWS KMS CMK (alias/triage-phi-key)
  - Point-in-time recovery: Enabled
  - Deletion protection: Enabled (production)
```

### Application-Level Field Encryption (PHI fields)
```python
# agents/shared/encryption.py
import boto3
from aws_encryption_sdk import EncryptionSDKClient

class PHIEncryptor:
    """Encrypts/decrypts individual PHI fields before DynamoDB write/read."""
    
    def __init__(self, key_arn: str):
        self.client = EncryptionSDKClient()
        self.key_arn = key_arn
    
    def encrypt_field(self, plaintext: str, context: dict) -> bytes:
        """Encrypt with encryption context (session_id, field_name)."""
        ...
    
    def decrypt_field(self, ciphertext: bytes, context: dict) -> str:
        """Decrypt with matching encryption context."""
        ...
```

**Encryption context**: Every encryption call includes `{session_id, field_name}` — this prevents ciphertext being moved between records.

---

## Pattern 2: PHI Log Redaction

### Architecture
```
Lambda Function → CloudWatch Log Group → Subscription Filter → Redaction Lambda → Clean Log Group

Developers read: Clean Log Group (PHI-free)
Audit reads: AuditTrail DynamoDB table (authoritative, encrypted)
```

### Redaction Lambda Logic
```python
# Patterns to detect and redact
PHI_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',           # SSN
    r'\b\d{2}/\d{2}/\d{4}\b',           # DOB (MM/DD/YYYY)
    r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',     # Names (heuristic)
    r'\b\d{10}\b',                        # Phone numbers
    r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Emails
    r'\bMRN[\s:]*\d+\b',                 # Medical Record Numbers
]

def redact(log_event: str) -> str:
    for pattern in PHI_PATTERNS:
        log_event = re.sub(pattern, '[REDACTED]', log_event)
    return log_event
```

### Alternative: Lambda Layer Approach
Instead of a subscription filter (async), embed redaction in the logging library itself:

```python
# agents/shared/phi_redaction.py — Lambda Layer
import logging

class PHIRedactingFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return redact_phi(message)

# Every agent uses:
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(PHIRedactingFormatter())
logger.addHandler(handler)
```

**MVP decision**: Use Lambda Layer approach (simpler, synchronous, guaranteed before write). Subscription filter approach for Production (more robust, handles edge cases).

---

## Pattern 3: Auto-Scaling & Availability

### Lambda Concurrency
```
Critical path (affects patient latency):
  - symptom-assessment: Reserved concurrency = 50
  - triage-scoring: Reserved concurrency = 30
  - chat-message: Reserved concurrency = 50

Background (can cold-start):
  - drug-interaction: Unreserved (on-demand)
  - specialist-routing: Unreserved
  - clinical-summary: Unreserved
  - notification: Unreserved
```

### DynamoDB Scaling
```
All tables: On-demand capacity mode
  - Auto-scales to any load
  - No capacity planning required
  - Cost: per-request pricing (~$1.25 per million writes, $0.25 per million reads)
```

### Bedrock Throttling Protection
```python
# agents/shared/bedrock_client.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def invoke_bedrock(prompt: str, model_id: str) -> str:
    """Invoke Bedrock with retry on throttling."""
    try:
        response = bedrock_runtime.invoke_model(...)
        return response
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            raise  # retry handles this
        raise
```

---

## Pattern 4: Structured Logging + Tracing

### Log Format (All Lambdas)
```json
{
  "timestamp": "2026-07-08T13:00:00.000Z",
  "level": "INFO",
  "service": "triage-scoring",
  "session_id": "uuid",
  "correlation_id": "uuid",
  "message": "Urgency classified",
  "data": {
    "urgency_level": "URGENT",
    "confidence": 0.82,
    "method": "llm_reasoning"
  }
}
```

### X-Ray Integration
```python
# All Lambda handlers:
from aws_lambda_powertools import Tracer
tracer = Tracer(service="triage-scoring")

@tracer.capture_lambda_handler
def handler(event, context):
    with tracer.provider.in_subsegment("invoke_bedrock"):
        result = invoke_bedrock(...)
    ...
```

### Correlation ID Flow
```
Patient request → API Gateway (generates X-Amzn-Trace-Id)
  → Step Functions (propagates trace ID)
    → Lambda invocations (all use same trace ID)
      → DynamoDB writes (trace ID in session record)

Every log line includes session_id + correlation_id for end-to-end tracing.
```

---

## Pattern 5: Input Validation

### Python (Agents) — Pydantic
```python
from pydantic import BaseModel, Field, validator

class StructuredSymptoms(BaseModel):
    session_id: str = Field(..., pattern=r'^[0-9a-f-]{36}$')
    severity: int = Field(..., ge=1, le=10)
    primary_complaint: PrimaryComplaint
    assessment_complete: bool
    
    @validator('severity')
    def severity_in_range(cls, v):
        if not 1 <= v <= 10:
            raise ValueError('Severity must be 1-10')
        return v
```

### TypeScript (Portal + CDK) — Zod
```typescript
import { z } from 'zod';

const SendMessageSchema = z.object({
  text: z.string().min(1).max(1000),
  sessionId: z.string().uuid(),
});
```

### API Gateway — Request Validation
```
All REST endpoints: Request model validation enabled
  - Rejects malformed requests at gateway level (never reaches Lambda)
  - Reduces Lambda invocations for invalid traffic
```

---

## Pattern 6: Error Handling (Fail-Safe)

### Lambda Error Strategy
```python
from aws_lambda_powertools import Logger
logger = Logger(service="drug-interaction")

def handler(event, context):
    try:
        result = process(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except PharmacyUnavailableError:
        # Graceful degradation — don't fail the pipeline
        logger.warning("Pharmacy system unavailable", extra={"session_id": ...})
        return {"statusCode": 200, "body": json.dumps(degraded_result())}
    except ValidationError as e:
        # Client error — bad input
        logger.error("Validation failed", extra={"error": str(e)})
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        # Unexpected — log and return 500
        logger.exception("Unexpected error")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal error"})}
```

### Step Functions Error Handling
```
Each Task state:
  Retry: [
    { ErrorEquals: ["ThrottlingException"], IntervalSeconds: 2, MaxAttempts: 3, BackoffRate: 2 }
  ]
  Catch: [
    { ErrorEquals: ["States.ALL"], Next: "HandleError" }
  ]

HandleError state:
  - Log failure to audit trail
  - Notify patient: "Something went wrong — please try again or call the clinic"
  - Mark session as FAILED
```

---

## Pattern 7: Rate Limiting & WAF

### API Gateway Throttling
```
Default: 100 requests/second (burst), 50 requests/second (sustained)
Per-patient: 10 requests/second (via usage plan keyed to Cognito sub)
```

### AWS WAF Rules
```
Rule 1: Rate limiting (IP-based) — 1000 requests per 5 minutes per IP
Rule 2: SQL injection pattern matching (default AWS managed rule)
Rule 3: Cross-site scripting (XSS) pattern matching
Rule 4: Known bad inputs (default AWS managed rule)
Rule 5: Bot control (future — for Production)
```

---

## Pattern 8: Secrets Management

### Secrets Manager Usage
```
Secret: /triage/pagerduty
  - integration_key: "..."
  - service_id: "..."

Secret: /triage/ehr-stub
  - api_key: "..."
  - base_url: "..."

Secret: /triage/pharmacy-stub
  - api_key: "..."
  - base_url: "..."
```

### Lambda Access
```python
# Cached at module level (warm starts reuse)
import boto3
from functools import lru_cache

@lru_cache(maxsize=1)
def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])
```

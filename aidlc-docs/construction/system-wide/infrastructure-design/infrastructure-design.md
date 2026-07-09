# Infrastructure Design — CDK Stack Architecture

## Stack Organization

```
healthcare-triage (CDK App)
├── SharedStack              — DynamoDB, KMS, Cognito, Secrets Manager
├── NetworkStack             — API Gateway (REST + WebSocket), WAF, CloudFront
├── AgentsStack              — All agent Lambda functions + Bedrock permissions
├── OrchestrationStack       — Step Functions (Express + Standard) + Notification Lambdas
└── PortalStack              — S3 bucket + CloudFront distribution for React app
```

**Deploy order**: SharedStack → NetworkStack → AgentsStack → OrchestrationStack → PortalStack

---

## SharedStack

### DynamoDB Tables

| Table | Partition Key | Sort Key | GSIs | Encryption | TTL |
|---|---|---|---|---|---|
| `triage-sessions` | sessionId | — | patientId-startedAt, status, clinicId | KMS CMK | 90d |
| `triage-patients` | patientId | — | email, phone | KMS CMK | — |
| `triage-conversations` | sessionId | timestamp | — | KMS CMK | 90d |
| `triage-notifications` | sessionId | channel | status | KMS CMK | 30d |
| `triage-audit-trail` | patientId | timestamp | eventType | KMS CMK | — |
| `triage-appointments` | patientId | appointmentId | status-scheduledAt | KMS CMK | 365d |

**CDK Pattern (all tables):**
```typescript
new dynamodb.Table(this, 'Sessions', {
  tableName: 'triage-sessions',
  partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
  encryptionKey: phiKey,
  pointInTimeRecovery: true,
  removalPolicy: RemovalPolicy.RETAIN,
  timeToLiveAttribute: 'ttl',
});
```

### KMS Keys

| Key | Alias | Purpose |
|---|---|---|
| PHI Key | `alias/triage-phi-key` | Encrypt all PHI fields + DynamoDB SSE |
| General Key | `alias/triage-general-key` | Non-PHI encrypted data |

```typescript
const phiKey = new kms.Key(this, 'PHIKey', {
  alias: 'alias/triage-phi-key',
  enableKeyRotation: true,
  description: 'Encrypts PHI data in Healthcare Triage System',
  removalPolicy: RemovalPolicy.RETAIN,
});
```

### Cognito

```typescript
const userPool = new cognito.UserPool(this, 'PatientPool', {
  userPoolName: 'healthcare-triage-patients',
  selfSignUpEnabled: false,  // patients created via admin/registration flow
  signInAliases: { email: true, phone: true },
  customAttributes: {
    'clinicId': new cognito.StringAttribute({ minLen: 1, maxLen: 50 }),
  },
  lambdaTriggers: {
    defineAuthChallenge: defineAuthChallengeFn,
    createAuthChallenge: createAuthChallengeFn,
    verifyAuthChallengeResponse: verifyAuthChallengeFn,
  },
  removalPolicy: RemovalPolicy.RETAIN,
});

// Groups
['patient', 'nurse', 'physician', 'admin'].forEach(group => {
  new cognito.CfnUserPoolGroup(this, `${group}Group`, {
    userPoolId: userPool.userPoolId,
    groupName: group,
  });
});
```

### Secrets Manager

```typescript
// PagerDuty integration credentials
new secretsmanager.Secret(this, 'PagerDutySecret', {
  secretName: '/triage/pagerduty',
  description: 'PagerDuty integration credentials for emergency escalation',
});
```

---

## NetworkStack

### REST API

```typescript
const restApi = new apigw.RestApi(this, 'TriageRestApi', {
  restApiName: 'healthcare-triage-api',
  defaultCorsPreflightOptions: {
    allowOrigins: [portalDomain],  // NOT wildcard
    allowMethods: apigw.Cors.ALL_METHODS,
    allowHeaders: ['Content-Type', 'Authorization'],
  },
  deployOptions: {
    stageName: 'prod',
    tracingEnabled: true,
    loggingLevel: apigw.MethodLoggingLevel.INFO,
    accessLogDestination: new apigw.LogGroupLogDestination(apiLogGroup),
  },
});

const authorizer = new apigw.CognitoUserPoolsAuthorizer(this, 'Authorizer', {
  cognitoUserPools: [userPool],
});
```

### WebSocket API

```typescript
const webSocketApi = new apigwv2.WebSocketApi(this, 'TriageChatApi', {
  apiName: 'healthcare-triage-chat',
  connectRouteOptions: {
    integration: new WebSocketLambdaIntegration('ConnectIntegration', chatConnectFn),
    authorizer: new WebSocketLambdaAuthorizer('ChatAuthorizer', authFn),
  },
  disconnectRouteOptions: {
    integration: new WebSocketLambdaIntegration('DisconnectIntegration', chatDisconnectFn),
  },
  defaultRouteOptions: {
    integration: new WebSocketLambdaIntegration('MessageIntegration', chatMessageFn),
  },
});
```

### WAF

```typescript
const webAcl = new wafv2.CfnWebACL(this, 'TriageWAF', {
  scope: 'REGIONAL',
  defaultAction: { allow: {} },
  rules: [
    // Rate limiting
    { name: 'RateLimit', priority: 1, action: { block: {} },
      statement: { rateBasedStatement: { limit: 1000, aggregateKeyType: 'IP' } },
      visibilityConfig: { ... }
    },
    // AWS Managed Rules: SQL injection
    { name: 'SQLi', priority: 2, overrideAction: { none: {} },
      statement: { managedRuleGroupStatement: { vendorName: 'AWS', name: 'AWSManagedRulesSQLiRuleSet' } },
      visibilityConfig: { ... }
    },
  ],
});
```

---

## AgentsStack

### Lambda Functions (All Agents)

**Shared configuration:**
```typescript
const agentDefaults: lambda.FunctionProps = {
  runtime: lambda.Runtime.PYTHON_3_12,
  architecture: lambda.Architecture.ARM_64,  // cost-effective
  memorySize: 512,
  timeout: Duration.seconds(30),
  tracing: lambda.Tracing.ACTIVE,  // X-Ray
  environment: {
    SESSIONS_TABLE: sessionsTable.tableName,
    PHI_KEY_ARN: phiKey.keyArn,
    BEDROCK_MODEL_ID: 'anthropic.claude-3-sonnet-20240229-v1:0',
    LOG_LEVEL: 'INFO',
  },
  layers: [phiRedactionLayer],  // shared PHI redaction
};
```

**Per-agent functions:**

| Function | Memory | Timeout | Concurrency | Extra Env |
|---|---|---|---|---|
| symptom-assessment | 512 MB | 15s | Reserved: 50 | — |
| triage-scoring | 512 MB | 10s | Reserved: 30 | — |
| drug-interaction | 256 MB | 10s | Unreserved | PHARMACY_SECRET_ARN |
| specialist-routing | 256 MB | 10s | Unreserved | — |
| clinical-summary | 1024 MB | 15s | Unreserved | — |

**Bedrock permissions:**
```typescript
agentFn.addToRolePolicy(new iam.PolicyStatement({
  actions: ['bedrock:InvokeModel'],
  resources: [`arn:aws:bedrock:${region}::foundation-model/anthropic.claude-3-sonnet-*`],
}));
```

### PHI Redaction Lambda Layer

```typescript
const phiRedactionLayer = new lambda.LayerVersion(this, 'PHIRedactionLayer', {
  code: lambda.Code.fromAsset('agents/shared'),
  compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
  description: 'PHI redaction logging formatter for all agents',
});
```

---

## OrchestrationStack

### Step Functions — Express Workflow

```typescript
const triagePipeline = new sfn.StateMachine(this, 'TriagePipelineExpress', {
  stateMachineName: 'triage-pipeline-express',
  stateMachineType: sfn.StateMachineType.EXPRESS,
  definitionBody: sfn.DefinitionBody.fromFile('orchestration/state_machines/triage_express.asl.json'),
  tracingEnabled: true,
  logs: {
    destination: pipelineLogGroup,
    level: sfn.LogLevel.ALL,
    includeExecutionData: true,
  },
});
```

### Step Functions — Standard Workflow (Nurse Handoff)

```typescript
const nurseHandoff = new sfn.StateMachine(this, 'NurseHandoffStandard', {
  stateMachineName: 'nurse-handoff-standard',
  stateMachineType: sfn.StateMachineType.STANDARD,
  definitionBody: sfn.DefinitionBody.fromFile('orchestration/state_machines/nurse_handoff_standard.asl.json'),
  tracingEnabled: true,
});
```

### Chat + Notification Lambdas

| Function | Purpose | Trigger |
|---|---|---|
| chat-connect | WebSocket $connect | API Gateway |
| chat-message | Route patient message to Step Functions | API Gateway |
| chat-disconnect | Clean up connection | API Gateway |
| decision-logic | Evaluate escalation/handoff decisions | Step Functions Task |
| notification-handler | Send SMS/Push/PagerDuty | EventBridge rule |

---

## PortalStack

### Static Hosting

```typescript
const portalBucket = new s3.Bucket(this, 'PortalBucket', {
  bucketName: 'healthcare-triage-portal',
  encryption: s3.BucketEncryption.S3_MANAGED,
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  removalPolicy: RemovalPolicy.DESTROY,  // MVP — RETAIN for production
});

const distribution = new cloudfront.Distribution(this, 'PortalDistribution', {
  defaultBehavior: {
    origin: new S3Origin(portalBucket),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    responseHeadersPolicy: securityHeadersPolicy,
  },
  defaultRootObject: 'index.html',
  errorResponses: [
    { httpStatus: 404, responsePagePath: '/index.html', responseHttpStatus: 200 },  // SPA
  ],
});
```

### Security Headers (CloudFront)

```typescript
const securityHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
  securityHeadersBehavior: {
    contentSecurityPolicy: { contentSecurityPolicy: "default-src 'self'; connect-src 'self' wss://*.execute-api.*.amazonaws.com https://*.execute-api.*.amazonaws.com", override: true },
    strictTransportSecurity: { accessControlMaxAge: Duration.days(365), includeSubdomains: true, override: true },
    contentTypeOptions: { override: true },
    frameOptions: { frameOption: cloudfront.HeadersFrameOption.DENY, override: true },
    referrerPolicy: { referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override: true },
  },
});
```

---

## IAM Roles Summary

| Role | Permissions | Principle |
|---|---|---|
| Agent execution role (per agent) | DynamoDB (own tables), KMS (encrypt/decrypt), Bedrock (InvokeModel), CloudWatch (logs) | Least privilege per agent |
| Step Functions role | Lambda (invoke agents), DynamoDB (session updates), EventBridge (put events) | Pipeline orchestration |
| Chat Lambda role | DynamoDB (connections), Step Functions (SendTaskSuccess), API GW (PostToConnection) | WebSocket management |
| Notification role | SNS (publish), Secrets Manager (read PagerDuty key), DynamoDB (notification tracking) | Escalation only |
| Portal API role | DynamoDB (read patient data), Cognito (validate tokens) | Read-mostly |

---

## Deployment

```bash
# Deploy all stacks in order
cdk deploy SharedStack NetworkStack AgentsStack OrchestrationStack PortalStack

# Or deploy all at once (CDK resolves dependencies)
cdk deploy --all
```

### Environment Configuration (CDK Context)

```json
// cdk.json
{
  "context": {
    "environment": "dev",
    "bedrockModelId": "anthropic.claude-3-sonnet-20240229-v1:0",
    "portalDomain": "https://triage.healthcarenetwork.com",
    "pagerdutyEnabled": true,
    "provisionedConcurrency": false
  }
}
```

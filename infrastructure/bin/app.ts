#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SharedStack } from '../lib/shared-stack';
import { NetworkStack } from '../lib/network-stack';
import { AgentsStack } from '../lib/agents-stack';
import { OrchestrationStack } from '../lib/orchestration-stack';
import { PortalStack } from '../lib/portal-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

const environment = app.node.tryGetContext('environment') || 'dev';

// Stack 1: Shared resources (DynamoDB, KMS, Cognito, Secrets)
const shared = new SharedStack(app, `Triage-Shared-${environment}`, {
  env,
  description: 'Healthcare Triage - Shared resources (DynamoDB, KMS, Cognito)',
});

// Stack 2: Network (API Gateway REST + WebSocket, WAF)
const network = new NetworkStack(app, `Triage-Network-${environment}`, {
  env,
  description: 'Healthcare Triage - API Gateway and WAF',
  userPool: shared.userPool,
  userPoolClient: shared.userPoolClient,
});

// Stack 3: Agent Lambda functions
const agents = new AgentsStack(app, `Triage-Agents-${environment}`, {
  env,
  description: 'Healthcare Triage - Agent Lambda functions',
  sessionsTable: shared.sessionsTable,
  conversationsTable: shared.conversationsTable,
  auditTable: shared.auditTable,
  phiKey: shared.phiKey,
  phiRedactionLayer: shared.phiRedactionLayer,
});

// Stack 4: Orchestration (Step Functions + Chat + Notifications)
const orchestration = new OrchestrationStack(app, `Triage-Orchestration-${environment}`, {
  env,
  description: 'Healthcare Triage - Step Functions and Notification',
  sessionsTable: shared.sessionsTable,
  notificationsTable: shared.notificationsTable,
  auditTable: shared.auditTable,
  phiKey: shared.phiKey,
  webSocketApi: network.webSocketApi,
  agentFunctions: agents.agentFunctions,
});

// Stack 5: Portal (S3 + CloudFront)
const portal = new PortalStack(app, `Triage-Portal-${environment}`, {
  env,
  description: 'Healthcare Triage - Patient Portal hosting',
  restApi: network.restApi,
});

// Tag all resources
cdk.Tags.of(app).add('Project', 'HealthcareTriage');
cdk.Tags.of(app).add('Environment', environment);
cdk.Tags.of(app).add('ManagedBy', 'CDK');

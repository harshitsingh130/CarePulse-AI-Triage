import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface AgentsStackProps extends cdk.StackProps {
  sessionsTable: dynamodb.Table;
  conversationsTable: dynamodb.Table;
  auditTable: dynamodb.Table;
  phiKey: kms.Key;
  phiRedactionLayer: lambda.LayerVersion;
}

export class AgentsStack extends cdk.Stack {
  public readonly agentFunctions: Record<string, lambda.Function>;

  constructor(scope: Construct, id: string, props: AgentsStackProps) {
    super(scope, id, props);

    const bedrockModelId = this.node.tryGetContext('bedrockModelId')
      || 'anthropic.claude-sonnet-4-20250514';

    // Common environment for all agents
    const commonEnv: Record<string, string> = {
      SESSIONS_TABLE: props.sessionsTable.tableName,
      CONVERSATIONS_TABLE: props.conversationsTable.tableName,
      AUDIT_TRAIL_TABLE: props.auditTable.tableName,
      PHI_KEY_ARN: props.phiKey.keyArn,
      BEDROCK_MODEL_ID: bedrockModelId,
      LOG_LEVEL: 'INFO',
      NURSE_HANDOFF_THRESHOLD: '0.70',
    };

    // Bedrock invoke policy
    const bedrockPolicy = new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: [`arn:aws:bedrock:${this.region}::foundation-model/anthropic.*`],
    });

    // Create agent functions
    this.agentFunctions = {};

    const agentConfigs: Array<{
      name: string;
      handler: string;
      codeAsset: string;
      memorySize: number;
      timeout: number;
      reservedConcurrency?: number;
      extraEnv?: Record<string, string>;
    }> = [
      {
        name: 'symptom-assessment',
        handler: 'agents.symptom_assessment.handler.handler',
        codeAsset: '../agents',
        memorySize: 512,
        timeout: 15,
        reservedConcurrency: 50,
      },
      {
        name: 'triage-scoring',
        handler: 'agents.triage_scoring.handler.handler',
        codeAsset: '../agents',
        memorySize: 512,
        timeout: 10,
        reservedConcurrency: 30,
      },
      {
        name: 'drug-interaction',
        handler: 'agents.drug_interaction.handler.handler',
        codeAsset: '../agents',
        memorySize: 256,
        timeout: 10,
        extraEnv: { PHARMACY_TIMEOUT: '3' },
      },
      {
        name: 'specialist-routing',
        handler: 'agents.specialist_routing.handler.handler',
        codeAsset: '../agents',
        memorySize: 256,
        timeout: 10,
        extraEnv: { SCHEDULING_TIMEOUT: '2' },
      },
      {
        name: 'clinical-summary',
        handler: 'agents.clinical_summary.handler.handler',
        codeAsset: '../agents',
        memorySize: 1024,
        timeout: 15,
      },
    ];

    for (const config of agentConfigs) {
      const fn = new lambda.Function(this, `Agent-${config.name}`, {
        functionName: `triage-${config.name}`,
        runtime: lambda.Runtime.PYTHON_3_12,
        architecture: lambda.Architecture.ARM_64,
        handler: config.handler,
        code: lambda.Code.fromAsset(config.codeAsset, {
          exclude: ['**/__pycache__', '**/tests', '*.pyc', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules'],
        }),
        memorySize: config.memorySize,
        timeout: cdk.Duration.seconds(config.timeout),
        tracing: lambda.Tracing.ACTIVE,
        layers: [props.phiRedactionLayer],
        environment: { ...commonEnv, ...config.extraEnv },
        logRetention: logs.RetentionDays.THREE_MONTHS,
      });

      // Reserved concurrency (critical path agents) — disabled for MVP
      // Enable in production after requesting Lambda concurrency quota increase
      // if (config.reservedConcurrency) {
      //   const cfnFn = fn.node.defaultChild as lambda.CfnFunction;
      //   cfnFn.addPropertyOverride('ReservedConcurrentExecutions', config.reservedConcurrency);
      // }

      // Permissions
      props.sessionsTable.grantReadWriteData(fn);
      props.conversationsTable.grantReadWriteData(fn);
      props.auditTable.grantWriteData(fn);
      props.phiKey.grantEncryptDecrypt(fn);
      fn.addToRolePolicy(bedrockPolicy);

      this.agentFunctions[config.name] = fn;
    }

    // --- Outputs ---
    for (const [name, fn] of Object.entries(this.agentFunctions)) {
      new cdk.CfnOutput(this, `${name}-arn`, {
        value: fn.functionArn,
        exportName: `Triage-${name}-Arn`,
      });
    }
  }
}

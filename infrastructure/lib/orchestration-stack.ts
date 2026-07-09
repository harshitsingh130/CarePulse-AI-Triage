import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';
import { Construct } from 'constructs';

export interface OrchestrationStackProps extends cdk.StackProps {
  sessionsTable: dynamodb.Table;
  notificationsTable: dynamodb.Table;
  auditTable: dynamodb.Table;
  phiKey: kms.Key;
  webSocketApi: apigwv2.CfnApi;
  agentFunctions: Record<string, lambda.Function>;
}

export class OrchestrationStack extends cdk.Stack {
  public readonly triagePipeline: sfn.StateMachine;
  public readonly nurseHandoff: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: OrchestrationStackProps) {
    super(scope, id, props);

    const wsEndpoint = `https://${props.webSocketApi.ref}.execute-api.${this.region}.amazonaws.com/prod`;

    // --- SNS Topic for Emergency Escalation ---

    const escalationTopic = new sns.Topic(this, 'EscalationTopic', {
      topicName: 'triage-emergency-escalation',
      displayName: 'Triage Emergency Escalation',
    });

    // --- Connections Table (WebSocket state) ---

    const connectionsTable = new dynamodb.Table(this, 'Connections', {
      tableName: 'triage-connections',
      partitionKey: { name: 'connectionId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // --- Common Lambda environment ---

    const commonEnv: Record<string, string> = {
      SESSIONS_TABLE: props.sessionsTable.tableName,
      NOTIFICATIONS_TABLE: props.notificationsTable.tableName,
      AUDIT_TRAIL_TABLE: props.auditTable.tableName,
      CONNECTIONS_TABLE: connectionsTable.tableName,
      WEBSOCKET_API_ENDPOINT: wsEndpoint,
      PHI_KEY_ARN: props.phiKey.keyArn,
      LOG_LEVEL: 'INFO',
    };

    // --- Orchestration Lambdas ---

    const decisionLogicFn = new lambda.Function(this, 'DecisionLogic', {
      functionName: 'triage-decision-logic',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'orchestration.lambdas.decision_logic.init_session_handler',
      code: lambda.Code.fromAsset('..', { exclude: ['**/__pycache__', '**/tests', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules', '.vscode'] }),
      memorySize: 256,
      timeout: cdk.Duration.seconds(10),
      tracing: lambda.Tracing.ACTIVE,
      environment: commonEnv,
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    const notificationFn = new lambda.Function(this, 'NotificationHandler', {
      functionName: 'triage-notification',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'orchestration.lambdas.notification_handler.handler',
      code: lambda.Code.fromAsset('..', { exclude: ['**/__pycache__', '**/tests', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules', '.vscode'] }),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      tracing: lambda.Tracing.ACTIVE,
      environment: commonEnv,
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    const chatConnectFn = new lambda.Function(this, 'ChatConnect', {
      functionName: 'triage-chat-connect',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'orchestration.lambdas.chat_connect.handler',
      code: lambda.Code.fromAsset('..', { exclude: ['**/__pycache__', '**/tests', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules', '.vscode'] }),
      memorySize: 128,
      timeout: cdk.Duration.seconds(5),
      environment: commonEnv,
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    const chatMessageFn = new lambda.Function(this, 'ChatMessage', {
      functionName: 'triage-chat-message',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'orchestration.lambdas.chat_message.handler',
      code: lambda.Code.fromAsset('..', { exclude: ['**/__pycache__', '**/tests', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules', '.vscode'] }),
      memorySize: 256,
      timeout: cdk.Duration.seconds(5),
      tracing: lambda.Tracing.ACTIVE,
      environment: commonEnv,
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    const chatDisconnectFn = new lambda.Function(this, 'ChatDisconnect', {
      functionName: 'triage-chat-disconnect',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'orchestration.lambdas.chat_disconnect.handler',
      code: lambda.Code.fromAsset('..', { exclude: ['**/__pycache__', '**/tests', 'cdk.out', 'infrastructure', 'portal', 'aidlc-docs', '.kiro', 'node_modules', '.vscode'] }),
      memorySize: 128,
      timeout: cdk.Duration.seconds(5),
      environment: commonEnv,
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    // --- Permissions ---

    const allOrchFunctions = [decisionLogicFn, notificationFn, chatConnectFn, chatMessageFn, chatDisconnectFn];
    for (const fn of allOrchFunctions) {
      props.sessionsTable.grantReadWriteData(fn);
      props.auditTable.grantWriteData(fn);
      props.phiKey.grantEncryptDecrypt(fn);
      connectionsTable.grantReadWriteData(fn);
    }

    props.notificationsTable.grantReadWriteData(notificationFn);
    escalationTopic.grantPublish(notificationFn);

    // Step Functions SendTaskSuccess permission for chat-message
    chatMessageFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['states:SendTaskSuccess', 'states:SendTaskFailure'],
      resources: ['*'], // Scoped to account state machines in production
    }));

    // WebSocket management API permission
    const wsManagePolicy = new iam.PolicyStatement({
      actions: ['execute-api:ManageConnections'],
      resources: [`arn:aws:execute-api:${this.region}:${this.account}:${props.webSocketApi.ref}/prod/POST/@connections/*`],
    });
    decisionLogicFn.addToRolePolicy(wsManagePolicy);

    // --- Step Functions ---

    const sfnLogGroup = new logs.LogGroup(this, 'SfnLogs', {
      logGroupName: '/aws/stepfunctions/triage-pipeline',
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Express Workflow (main pipeline)
    const sfnRole = new iam.Role(this, 'SfnRole', {
      assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
    });

    // Grant SFN role permission to invoke all agent functions + orchestration functions
    const allFunctions = [
      ...Object.values(props.agentFunctions),
      decisionLogicFn,
      notificationFn,
    ];
    for (const fn of allFunctions) {
      fn.grantInvoke(sfnRole);
    }

    sfnRole.addToPolicy(new iam.PolicyStatement({
      actions: ['logs:CreateLogDelivery', 'logs:GetLogDelivery', 'logs:UpdateLogDelivery',
               'logs:DeleteLogDelivery', 'logs:ListLogDeliveries', 'logs:PutResourcePolicy',
               'logs:DescribeResourcePolicies', 'logs:DescribeLogGroups'],
      resources: ['*'],
    }));

    sfnRole.addToPolicy(new iam.PolicyStatement({
      actions: ['states:CreateStateMachine', 'states:UpdateStateMachine',
               'states:DeleteStateMachine', 'states:DescribeStateMachine',
               'events:PutTargets', 'events:PutRule', 'events:DescribeRule'],
      resources: ['*'],
    }));

    this.triagePipeline = new sfn.StateMachine(this, 'TriagePipelineExpress', {
      stateMachineName: 'triage-pipeline',
      stateMachineType: sfn.StateMachineType.STANDARD,
      definitionBody: sfn.DefinitionBody.fromFile('../orchestration/state_machines/triage_express.asl.json'),
      role: sfnRole,
    });

    // Standard Workflow (nurse handoff)
    this.nurseHandoff = new sfn.StateMachine(this, 'NurseHandoffStandard', {
      stateMachineName: 'nurse-handoff-standard',
      stateMachineType: sfn.StateMachineType.STANDARD,
      definitionBody: sfn.DefinitionBody.fromFile('../orchestration/state_machines/nurse_handoff_standard.asl.json'),
      role: sfnRole,
    });

    // --- Outputs ---

    new cdk.CfnOutput(this, 'TriagePipelineArn', {
      value: this.triagePipeline.stateMachineArn,
    });
    new cdk.CfnOutput(this, 'NurseHandoffArn', {
      value: this.nurseHandoff.stateMachineArn,
    });
    new cdk.CfnOutput(this, 'EscalationTopicArn', {
      value: escalationTopic.topicArn,
    });
  }
}

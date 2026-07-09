import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export class SharedStack extends cdk.Stack {
  public readonly sessionsTable: dynamodb.Table;
  public readonly patientsTable: dynamodb.Table;
  public readonly conversationsTable: dynamodb.Table;
  public readonly notificationsTable: dynamodb.Table;
  public readonly auditTable: dynamodb.Table;
  public readonly appointmentsTable: dynamodb.Table;
  public readonly phiKey: kms.Key;
  public readonly generalKey: kms.Key;
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly phiRedactionLayer: lambda.LayerVersion;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- KMS Keys ---

    this.phiKey = new kms.Key(this, 'PHIKey', {
      alias: 'alias/triage-phi-key',
      enableKeyRotation: true,
      description: 'Encrypts PHI data in Healthcare Triage System',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    this.generalKey = new kms.Key(this, 'GeneralKey', {
      alias: 'alias/triage-general-key',
      enableKeyRotation: true,
      description: 'Encrypts non-PHI sensitive data',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // --- DynamoDB Tables ---

    this.sessionsTable = new dynamodb.Table(this, 'Sessions', {
      tableName: 'triage-sessions',
      partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.phiKey,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: 'ttl',
    });
    this.sessionsTable.addGlobalSecondaryIndex({
      indexName: 'patientId-startedAt-index',
      partitionKey: { name: 'patientId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'startedAt', type: dynamodb.AttributeType.STRING },
    });
    this.sessionsTable.addGlobalSecondaryIndex({
      indexName: 'status-index',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
    });

    this.patientsTable = new dynamodb.Table(this, 'Patients', {
      tableName: 'triage-patients',
      partitionKey: { name: 'patientId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.phiKey,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    this.patientsTable.addGlobalSecondaryIndex({
      indexName: 'email-index',
      partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
    });
    this.patientsTable.addGlobalSecondaryIndex({
      indexName: 'phone-index',
      partitionKey: { name: 'phone', type: dynamodb.AttributeType.STRING },
    });

    this.conversationsTable = new dynamodb.Table(this, 'Conversations', {
      tableName: 'triage-conversations',
      partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.phiKey,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    this.notificationsTable = new dynamodb.Table(this, 'Notifications', {
      tableName: 'triage-notifications',
      partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'channel', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.generalKey,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.auditTable = new dynamodb.Table(this, 'AuditTrail', {
      tableName: 'triage-audit-trail',
      partitionKey: { name: 'patientId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.phiKey,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      // NO TTL — audit retained permanently (HIPAA: 6+ years)
    });
    this.auditTable.addGlobalSecondaryIndex({
      indexName: 'eventType-index',
      partitionKey: { name: 'eventType', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
    });

    this.appointmentsTable = new dynamodb.Table(this, 'Appointments', {
      tableName: 'triage-appointments',
      partitionKey: { name: 'patientId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'appointmentId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.generalKey,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // --- Cognito User Pool ---

    this.userPool = new cognito.UserPool(this, 'PatientPool', {
      userPoolName: 'healthcare-triage-patients',
      selfSignUpEnabled: false,
      signInAliases: { email: true, phone: true },
      standardAttributes: {
        email: { required: false, mutable: true },
        phoneNumber: { required: false, mutable: true },
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.PHONE_AND_EMAIL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // User pool groups
    new cognito.CfnUserPoolGroup(this, 'PatientGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'patient',
      description: 'Patients using the triage system',
    });
    new cognito.CfnUserPoolGroup(this, 'NurseGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'nurse',
      description: 'Triage nurses who review ambiguous cases',
    });
    new cognito.CfnUserPoolGroup(this, 'PhysicianGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'physician',
      description: 'On-call physicians receiving escalations',
    });
    new cognito.CfnUserPoolGroup(this, 'AdminGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'admin',
      description: 'Clinic administrators',
    });

    this.userPoolClient = this.userPool.addClient('PortalClient', {
      userPoolClientName: 'triage-portal',
      authFlows: {
        custom: true,
        userSrp: true,
      },
      generateSecret: false,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    // --- PHI Redaction Lambda Layer ---

    this.phiRedactionLayer = new lambda.LayerVersion(this, 'PHIRedactionLayer', {
      code: lambda.Code.fromAsset('../agents/shared'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Shared utilities: PHI redaction, models, config, db, encryption',
      layerVersionName: 'triage-shared-layer',
    });

    // --- Secrets Manager ---

    new secretsmanager.Secret(this, 'PagerDutySecret', {
      secretName: '/triage/pagerduty',
      description: 'PagerDuty integration credentials',
    });

    new secretsmanager.Secret(this, 'PharmacySecret', {
      secretName: '/triage/pharmacy-stub',
      description: 'Hospital pharmacy system credentials (stubbed for MVP)',
    });

    // --- Outputs ---

    new cdk.CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new cdk.CfnOutput(this, 'UserPoolClientId', { value: this.userPoolClient.userPoolClientId });
    new cdk.CfnOutput(this, 'PHIKeyArn', { value: this.phiKey.keyArn });
    new cdk.CfnOutput(this, 'SessionsTableName', { value: this.sessionsTable.tableName });
  }
}

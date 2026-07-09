import * as cdk from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import { Construct } from 'constructs';

export interface NetworkStackProps extends cdk.StackProps {
  userPool: cognito.UserPool;
  userPoolClient: cognito.UserPoolClient;
}

export class NetworkStack extends cdk.Stack {
  public readonly restApi: apigw.RestApi;
  public readonly webSocketApi: apigwv2.CfnApi;

  constructor(scope: Construct, id: string, props: NetworkStackProps) {
    super(scope, id, props);

    const portalDomain = 'https://d12oqv6vi0inhw.cloudfront.net';

    // --- REST API ---

    const apiLogGroup = new logs.LogGroup(this, 'ApiAccessLogs', {
      logGroupName: '/aws/apigateway/triage-rest-api',
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.restApi = new apigw.RestApi(this, 'TriageRestApi', {
      restApiName: 'healthcare-triage-api',
      description: 'Healthcare Triage REST API',
      defaultCorsPreflightOptions: {
        allowOrigins: [portalDomain],
        allowMethods: apigw.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
        maxAge: cdk.Duration.hours(1),
      },
      deployOptions: {
        stageName: 'prod',
        tracingEnabled: true,
        loggingLevel: apigw.MethodLoggingLevel.INFO,
        accessLogDestination: new apigw.LogGroupLogDestination(apiLogGroup),
        accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields(),
        throttlingRateLimit: 50,
        throttlingBurstLimit: 100,
      },
    });

    // REST API resources (Lambda integrations added in Orchestration stack)
    const triageResource = this.restApi.root.addResource('triage');
    triageResource.addResource('start');
    triageResource.addResource('history');
    const statusResource = triageResource.addResource('status');
    statusResource.addResource('{sessionId}');

    const appointmentsResource = this.restApi.root.addResource('appointments');
    const consentResource = this.restApi.root.addResource('consent');
    consentResource.addResource('{type}');
    this.restApi.root.addResource('profile');

    // Admin endpoints (nurse dashboard)
    const adminResource = this.restApi.root.addResource('admin');
    const adminSessionsResource = adminResource.addResource('sessions');
    adminSessionsResource.addResource('{sessionId}');
    adminResource.addResource('override');

    // --- WebSocket API ---

    this.webSocketApi = new apigwv2.CfnApi(this, 'TriageChatWsApi', {
      name: 'healthcare-triage-chat',
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action',
    });

    const wsStage = new apigwv2.CfnStage(this, 'WsStage', {
      apiId: this.webSocketApi.ref,
      stageName: 'prod',
      autoDeploy: true,
    });

    // --- WAF ---

    const webAcl = new wafv2.CfnWebACL(this, 'TriageWAF', {
      scope: 'REGIONAL',
      defaultAction: { allow: {} },
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: 'TriageWAF',
        sampledRequestsEnabled: true,
      },
      rules: [
        {
          name: 'RateLimitPerIP',
          priority: 1,
          action: { block: {} },
          statement: {
            rateBasedStatement: {
              limit: 1000,
              aggregateKeyType: 'IP',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'RateLimitPerIP',
            sampledRequestsEnabled: true,
          },
        },
        {
          name: 'AWSManagedRulesSQLi',
          priority: 2,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesSQLiRuleSet',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'SQLiRules',
            sampledRequestsEnabled: true,
          },
        },
        {
          name: 'AWSManagedRulesCommonRuleSet',
          priority: 3,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesCommonRuleSet',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'CommonRules',
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    // Associate WAF with REST API
    new wafv2.CfnWebACLAssociation(this, 'WafAssociation', {
      webAclArn: webAcl.attrArn,
      resourceArn: this.restApi.deploymentStage.stageArn,
    });

    // --- Outputs ---

    new cdk.CfnOutput(this, 'RestApiUrl', {
      value: this.restApi.url,
    });
    new cdk.CfnOutput(this, 'WebSocketApiId', {
      value: this.webSocketApi.ref,
    });
    new cdk.CfnOutput(this, 'WebSocketUrl', {
      value: `wss://${this.webSocketApi.ref}.execute-api.${this.region}.amazonaws.com/prod`,
    });
  }
}

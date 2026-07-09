import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export interface PortalStackProps extends cdk.StackProps {
  restApi: apigw.RestApi;
}

export class PortalStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;
  public readonly portalBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: PortalStackProps) {
    super(scope, id, props);

    // --- S3 Bucket for static site ---

    this.portalBucket = new s3.Bucket(this, 'PortalBucket', {
      bucketName: `healthcare-triage-portal-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // --- Security Headers Response Policy ---

    const securityHeaders = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
      responseHeadersPolicyName: 'triage-security-headers',
      securityHeadersBehavior: {
        contentSecurityPolicy: {
          contentSecurityPolicy: [
            "default-src 'self'",
            `connect-src 'self' https://*.execute-api.${this.region}.amazonaws.com wss://*.execute-api.${this.region}.amazonaws.com https://cognito-idp.${this.region}.amazonaws.com`,
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "img-src 'self' data:",
            "font-src 'self' https://fonts.gstatic.com",
          ].join('; '),
          override: true,
        },
        strictTransportSecurity: {
          accessControlMaxAge: cdk.Duration.days(365),
          includeSubdomains: true,
          override: true,
        },
        contentTypeOptions: { override: true },
        frameOptions: {
          frameOption: cloudfront.HeadersFrameOption.DENY,
          override: true,
        },
        referrerPolicy: {
          referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
          override: true,
        },
      },
    });

    // --- CloudFront Distribution ---

    this.distribution = new cloudfront.Distribution(this, 'PortalDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(this.portalBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        responseHeadersPolicy: securityHeaders,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responsePagePath: '/index.html',
          responseHttpStatus: 200,
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responsePagePath: '/index.html',
          responseHttpStatus: 200,
          ttl: cdk.Duration.minutes(5),
        },
      ],
      comment: 'Healthcare Triage Patient Portal',
    });

    // --- Deploy portal build to S3 ---

    new s3deploy.BucketDeployment(this, 'DeployPortal', {
      sources: [s3deploy.Source.asset('../portal/dist')],
      destinationBucket: this.portalBucket,
      distribution: this.distribution,
      distributionPaths: ['/*'],
    });

    // --- Outputs ---

    new cdk.CfnOutput(this, 'PortalUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: 'Patient Portal URL',
    });
    new cdk.CfnOutput(this, 'PortalBucketName', {
      value: this.portalBucket.bucketName,
    });
    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
    });
  }
}

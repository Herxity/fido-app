import {
  CfnOutput,
  CfnParameter,
  Duration,
  Fn,
  Stack,
  StackProps,
  Validations,
  aws_certificatemanager as acm,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
  aws_lightsail as lightsail,
  aws_route53 as route53,
  aws_route53_targets as targets,
  aws_wafv2 as wafv2,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export interface FidoAppEdgeStackProps extends StackProps {
  readonly deploymentStage: "staging" | "production";
  readonly domainName?: string;
  readonly hostedZoneId?: string;
  readonly certificateArn?: string;
  readonly wafBlockMode?: boolean;
}

export class FidoAppEdgeStack extends Stack {
  public constructor(
    scope: Construct,
    id: string,
    props: FidoAppEdgeStackProps,
  ) {
    super(scope, id, props);

    this.validateDomainConfiguration(props);
    const resourcePrefix = `fido-app-${props.deploymentStage}`;

    const sshCidr = new CfnParameter(this, "SshAllowedCidr", {
      type: "String",
      default: "127.0.0.1/32",
      allowedPattern: "^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}/32$",
      description:
        "Single trusted public IPv4 address in /32 form. Keep the safe default to disable direct SSH.",
    });
    const sshPublicKey = new CfnParameter(this, "SshPublicKey", {
      type: "String",
      allowedPattern: "^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/=]+$",
      description:
        "Public SSH key type and base64 payload without a comment. Never pass private key material.",
    });
    const originVerifyToken = new CfnParameter(this, "OriginVerifyToken", {
      type: "String",
      noEcho: true,
      minLength: 32,
      description:
        "Random value also installed in the origin proxy configuration.",
    });

    const userData = Fn.join("", [
      "#!/usr/bin/env bash\nset -euo pipefail\ninstall -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh\nprintf '%s\\n' '",
      sshPublicKey.valueAsString,
      "' > /home/ubuntu/.ssh/authorized_keys\nchown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys\nchmod 600 /home/ubuntu/.ssh/authorized_keys\n",
    ]);

    const instance = new lightsail.CfnInstance(this, "ApplicationInstance", {
      instanceName: resourcePrefix,
      availabilityZone: `${this.region}a`,
      blueprintId: "ubuntu_24_04",
      bundleId: "micro_3_0",
      userData,
      networking: {
        ports: [
          {
            fromPort: 80,
            toPort: 80,
            protocol: "tcp",
            cidrs: ["0.0.0.0/0"],
            ipv6Cidrs: ["::/0"],
          },
          {
            fromPort: 443,
            toPort: 443,
            protocol: "tcp",
            cidrs: ["0.0.0.0/0"],
            ipv6Cidrs: ["::/0"],
          },
          {
            fromPort: 22,
            toPort: 22,
            protocol: "tcp",
            cidrs: [sshCidr.valueAsString],
            cidrListAliases: ["lightsail-connect"],
          },
        ],
      },
    });

    const staticIp = new lightsail.CfnStaticIp(this, "ApplicationStaticIp", {
      staticIpName: `${resourcePrefix}-ip`,
      attachedTo: instance.ref,
    });
    staticIp.addDependency(instance);

    const cpuAlarm = new lightsail.CfnAlarm(this, "SustainedCpuAlarm", {
      alarmName: `${resourcePrefix}-sustained-cpu`,
      monitoredResourceName: instance.ref,
      metricName: "CPUUtilization",
      comparisonOperator: "GreaterThanThreshold",
      threshold: 80,
      evaluationPeriods: 5,
      datapointsToAlarm: 3,
      treatMissingData: "breaching",
      notificationEnabled: false,
    });
    cpuAlarm.addDependency(instance);

    const statusAlarm = new lightsail.CfnAlarm(this, "StatusCheckAlarm", {
      alarmName: `${resourcePrefix}-status-check`,
      monitoredResourceName: instance.ref,
      metricName: "StatusCheckFailed",
      comparisonOperator: "GreaterThanThreshold",
      threshold: 0,
      evaluationPeriods: 2,
      datapointsToAlarm: 2,
      treatMissingData: "breaching",
      notificationEnabled: false,
    });
    statusAlarm.addDependency(instance);

    const webAcl = new wafv2.CfnWebACL(this, "WebAcl", {
      name: `fido-app-${props.deploymentStage}-edge`,
      scope: "CLOUDFRONT",
      defaultAction: { allow: {} },
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: "fido-app-edge",
        sampledRequestsEnabled: true,
      },
      rules: [
        this.managedRule(
          "AWSManagedRulesCommonRuleSet",
          10,
          props.wafBlockMode ?? false,
        ),
        this.managedRule(
          "AWSManagedRulesKnownBadInputsRuleSet",
          20,
          props.wafBlockMode ?? false,
        ),
        this.managedRule(
          "AWSManagedRulesAmazonIpReputationList",
          30,
          props.wafBlockMode ?? false,
        ),
        {
          name: "GlobalRateLimit",
          priority: 40,
          action: props.wafBlockMode ? { block: {} } : { count: {} },
          statement: {
            rateBasedStatement: { aggregateKeyType: "IP", limit: 1200 },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: "fido-global-rate-limit",
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    const originDomain = Fn.join("", [
      Fn.join("-", Fn.split(".", staticIp.attrIpAddress)),
      ".sslip.io",
    ]);
    const customDomain = props.domainName;
    const certificate = props.certificateArn
      ? acm.Certificate.fromCertificateArn(
          this,
          "ViewerCertificate",
          props.certificateArn,
        )
      : undefined;
    const distribution = new cloudfront.Distribution(this, "Distribution", {
      comment: "Fido application edge",
      ...(customDomain && certificate
        ? { domainNames: [customDomain], certificate }
        : {}),
      webAclId: webAcl.attrArn,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: new origins.HttpOrigin(originDomain, {
          protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
          readTimeout: Duration.seconds(30),
          customHeaders: {
            "X-Fido-Origin-Verify": originVerifyToken.valueAsString,
          },
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy:
          cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        compress: true,
      },
      enableIpv6: true,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });
    const cfnDistribution = distribution.node.defaultChild;
    if (!cfnDistribution) {
      throw new Error(
        "CloudFront distribution is missing its CloudFormation resource",
      );
    }
    Validations.of(cfnDistribution).acknowledge({
      id: "AwsSolutions::AwsSolutions-CFR1",
      reason:
        "The U.S.-only application has no legal requirement to block other countries at the edge.",
    });
    Validations.of(cfnDistribution).acknowledge({
      id: "AwsSolutions::AwsSolutions-CFR3",
      reason:
        "CloudFront standard logs require an additional stateful S3 log archive, intentionally outside this reduced initial stack.",
    });
    Validations.of(cfnDistribution).acknowledge({
      id: "AwsSolutions::AwsSolutions-CFR4",
      reason:
        "CloudFront fixes the TLS policy for its default certificate; custom-domain deployments supply an ACM certificate and TLSv1.2_2021.",
    });

    if (customDomain && props.hostedZoneId) {
      const zone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        {
          hostedZoneId: props.hostedZoneId,
          zoneName: this.zoneName(customDomain),
        },
      );
      new route53.ARecord(this, "AliasA", {
        zone,
        recordName: customDomain,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(distribution),
        ),
      });
      new route53.AaaaRecord(this, "AliasAaaa", {
        zone,
        recordName: customDomain,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(distribution),
        ),
      });
    }

    new CfnOutput(this, "InstanceName", { value: instance.ref });
    new CfnOutput(this, "StaticIpAddress", { value: staticIp.attrIpAddress });
    new CfnOutput(this, "OriginDomainName", { value: originDomain });
    new CfnOutput(this, "DistributionDomainName", {
      value: distribution.distributionDomainName,
    });
    new CfnOutput(this, "ApplicationUrl", {
      value: `https://${customDomain ?? distribution.distributionDomainName}`,
    });
  }

  private managedRule(
    name: string,
    priority: number,
    blockMode: boolean,
  ): wafv2.CfnWebACL.RuleProperty {
    return {
      name,
      priority,
      overrideAction: blockMode ? { none: {} } : { count: {} },
      statement: { managedRuleGroupStatement: { name, vendorName: "AWS" } },
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: `fido-${name}`,
        sampledRequestsEnabled: true,
      },
    };
  }

  private validateDomainConfiguration(props: FidoAppEdgeStackProps): void {
    const values = [props.domainName, props.hostedZoneId, props.certificateArn];
    const present = values.filter((value) => value !== undefined).length;
    if (present !== 0 && present !== values.length) {
      throw new Error(
        "domainName, hostedZoneId, and certificateArn must be supplied together",
      );
    }
  }

  private zoneName(domainName: string): string {
    const labels = domainName.split(".");
    if (labels.length < 2) {
      throw new Error("domainName must be a fully-qualified DNS name");
    }
    return labels.slice(-2).join(".");
  }
}

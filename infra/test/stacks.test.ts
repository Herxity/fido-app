import { App } from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { describe, expect, it } from "vitest";
import { FidoAppEdgeStack } from "../lib/app-edge-stack.js";
import { FidoStatefulStack } from "../lib/stateful-stack.js";

const env = { account: "111111111111", region: "us-east-1" };

describe("FidoStatefulStack", () => {
  it("creates a private retained Lightsail PostgreSQL database", () => {
    const app = new App();
    const stack = new FidoStatefulStack(app, "Stateful", {
      env,
      terminationProtection: true,
      deploymentStage: "staging",
    });
    const template = Template.fromStack(stack);

    template.hasResource("AWS::Lightsail::Database", {
      DeletionPolicy: "Retain",
      UpdateReplacePolicy: "Retain",
      Properties: Match.objectLike({
        RelationalDatabaseBlueprintId: "postgres_18",
        RelationalDatabaseBundleId: "micro_2_0",
        PubliclyAccessible: false,
        BackupRetention: true,
      }),
    });
    expect(stack.terminationProtection).toBe(true);
  });
});

describe("FidoAppEdgeStack", () => {
  it("creates the instance, static IP, WAF, CloudFront distribution, and alarms", () => {
    const app = new App();
    const stack = new FidoAppEdgeStack(app, "Edge", {
      env,
      deploymentStage: "staging",
    });
    const template = Template.fromStack(stack);

    template.hasResourceProperties("AWS::Lightsail::Instance", {
      BlueprintId: "ubuntu_24_04",
      BundleId: "micro_3_0",
      Networking: Match.objectLike({
        Ports: Match.arrayWith([
          Match.objectLike({ FromPort: 22, ToPort: 22, Protocol: "tcp" }),
        ]),
      }),
    });
    template.resourceCountIs("AWS::Lightsail::StaticIp", 1);
    template.resourceCountIs("AWS::Lightsail::Alarm", 2);
    template.hasResourceProperties("AWS::WAFv2::WebACL", {
      Scope: "CLOUDFRONT",
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: "AWSManagedRulesCommonRuleSet",
          OverrideAction: { Count: {} },
        }),
        Match.objectLike({ Name: "GlobalRateLimit", Action: { Count: {} } }),
      ]),
    });
    template.hasResourceProperties("AWS::CloudFront::Distribution", {
      DistributionConfig: Match.objectLike({ WebACLId: Match.anyValue() }),
    });
    const instances = template.findResources("AWS::Lightsail::Instance");
    const synthesizedInstance = Object.values(instances)[0];
    if (!synthesizedInstance) throw new Error("expected a Lightsail instance");
    expect(JSON.stringify(synthesizedInstance)).not.toMatch(
      /"Fn::(?:Sub|Base64)"/,
    );
  });

  it("only blocks WAF matches after block mode is explicitly enabled", () => {
    const app = new App();
    const stack = new FidoAppEdgeStack(app, "BlockingEdge", {
      env,
      wafBlockMode: true,
      deploymentStage: "staging",
    });
    const template = Template.fromStack(stack);

    template.hasResourceProperties("AWS::WAFv2::WebACL", {
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: "AWSManagedRulesCommonRuleSet",
          OverrideAction: { None: {} },
        }),
        Match.objectLike({ Name: "GlobalRateLimit", Action: { Block: {} } }),
      ]),
    });
  });

  it("rejects an incomplete custom-domain configuration", () => {
    const app = new App();
    expect(
      () =>
        new FidoAppEdgeStack(app, "Invalid", {
          env,
          domainName: "app.example.com",
          deploymentStage: "staging",
        }),
    ).toThrow(/must be supplied together/);
  });
});

#!/usr/bin/env node
import { App, Environment, Tags, Validations } from "aws-cdk-lib";
import { AwsSolutionsChecks } from "cdk-nag";
import { FidoAppEdgeStack } from "../lib/app-edge-stack.js";
import { FidoStatefulStack } from "../lib/stateful-stack.js";

const app = new App();
const env: Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT ?? "286533052478",
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};
const stageContext = app.node.tryGetContext("stage") as string | undefined;
if (
  stageContext !== undefined &&
  stageContext !== "staging" &&
  stageContext !== "production"
) {
  throw new Error("CDK context stage must be either staging or production");
}
let deploymentStage: "staging" | "production" = "staging";
if (stageContext === "production") {
  deploymentStage = "production";
}

new FidoStatefulStack(app, "FidoStatefulStack", {
  env,
  stackName: `fido-stateful-${deploymentStage}`,
  terminationProtection: true,
  description: `Protected, stateful infrastructure for Fido ${deploymentStage}`,
  deploymentStage,
});

const domainName = app.node.tryGetContext("domainName") as string | undefined;
const hostedZoneId = app.node.tryGetContext("hostedZoneId") as
  | string
  | undefined;
const certificateArn = app.node.tryGetContext("certificateArn") as
  | string
  | undefined;
const wafBlockModeContext = app.node.tryGetContext("wafBlockMode") as unknown;
const wafBlockMode =
  wafBlockModeContext === true || wafBlockModeContext === "true";

new FidoAppEdgeStack(app, "FidoAppEdgeStack", {
  env,
  stackName: `fido-app-edge-${deploymentStage}`,
  description:
    "Replaceable Lightsail application and CloudFront/WAF edge for Fido",
  ...(domainName ? { domainName } : {}),
  ...(hostedZoneId ? { hostedZoneId } : {}),
  ...(certificateArn ? { certificateArn } : {}),
  wafBlockMode,
  deploymentStage,
});

Tags.of(app).add("Project", "fido");
Tags.of(app).add("ManagedBy", "aws-cdk");
Validations.of(app).addPlugins(new AwsSolutionsChecks(app, { verbose: true }));

app.synth();

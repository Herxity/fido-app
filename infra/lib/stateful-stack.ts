import {
  CfnOutput,
  RemovalPolicy,
  Stack,
  StackProps,
  aws_lightsail as lightsail,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export interface FidoStatefulStackProps extends StackProps {
  readonly deploymentStage: "staging" | "production";
}

export class FidoStatefulStack extends Stack {
  public constructor(
    scope: Construct,
    id: string,
    props: FidoStatefulStackProps,
  ) {
    super(scope, id, props);

    const database = new lightsail.CfnDatabase(this, "Database", {
      relationalDatabaseName: `fido-${props.deploymentStage}-postgres`,
      relationalDatabaseBlueprintId: "postgres_18",
      relationalDatabaseBundleId: "micro_2_0",
      masterDatabaseName: "fido",
      masterUsername: "fido_admin",
      availabilityZone: `${this.region}a`,
      backupRetention: true,
      publiclyAccessible: false,
      preferredBackupWindow: "05:00-05:30",
      preferredMaintenanceWindow: "sun:06:00-sun:06:30",
    });
    database.applyRemovalPolicy(RemovalPolicy.RETAIN, {
      applyToUpdateReplacePolicy: true,
    });

    new CfnOutput(this, "DatabaseName", { value: database.ref });
    new CfnOutput(this, "DatabaseArn", { value: database.attrDatabaseArn });
  }
}

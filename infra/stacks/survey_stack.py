"""SurveyStack: durable demo state, anonymous responses, secrets, and seeds."""

import aws_cdk as cdk
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    custom_resources as cr,
)
from constructs import Construct

from stacks.common import lambda_code, tag_stack


class SurveyStack(cdk.Stack):
    """Data resources shared by the API and AgentCore tools."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.responses_table = dynamodb.Table(
            self,
            "Responses",
            partition_key=dynamodb.Attribute(
                name="event_cycle", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="response_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",  # safety net, not the plan
            removal_policy=cdk.RemovalPolicy.DESTROY,  # demo data only
        )

        self.events_table = dynamodb.Table(
            self,
            "Events",
            partition_key=dynamodb.Attribute(
                name="event_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.inventory_table = dynamodb.Table(
            self,
            "Inventory",
            partition_key=dynamodb.Attribute(
                name="ingredient_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.fallback_bucket = s3.Bucket(
            self,
            "FallbackArtifacts",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.presenter_secret = secretsmanager.Secret(
            self,
            "PresenterPassphrase",
            description="Clave compartida del panel de Chef Andino",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template="{}",
                generate_string_key="passphrase",
                password_length=28,
                exclude_punctuation=True,
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        seed_function = lambda_.Function(
            self,
            "SeedDataFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="chef_andino.cloud.seed_handler.lambda_handler",
            code=lambda_code(),
            timeout=cdk.Duration.minutes(2),
            memory_size=512,
            log_group=logs.LogGroup(
                self,
                "SeedDataLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            environment={
                "EVENTS_TABLE": self.events_table.table_name,
                "RESPONSES_TABLE": self.responses_table.table_name,
                "INVENTORY_TABLE": self.inventory_table.table_name,
                "INVENTORY_SEED_PATH": "/var/task/data/inventory.seed.json",
                "PUBLIC_EVENT_ID": "demo-event",
            },
        )
        self.events_table.grant_read_write_data(seed_function)
        self.responses_table.grant_read_write_data(seed_function)
        self.inventory_table.grant_read_write_data(seed_function)
        provider = cr.Provider(self, "SeedProvider", on_event_handler=seed_function)
        cdk.CustomResource(
            self,
            "SeedData",
            service_token=provider.service_token,
            properties={"SeedVersion": "1"},
        )

        cdk.CfnOutput(self, "ResponsesTableName", value=self.responses_table.table_name)
        cdk.CfnOutput(self, "EventsTableName", value=self.events_table.table_name)
        cdk.CfnOutput(self, "InventoryTableName", value=self.inventory_table.table_name)
        cdk.CfnOutput(self, "FallbackBucketName", value=self.fallback_bucket.bucket_name)
        cdk.CfnOutput(self, "PresenterSecretArn", value=self.presenter_secret.secret_arn)
        tag_stack(self)

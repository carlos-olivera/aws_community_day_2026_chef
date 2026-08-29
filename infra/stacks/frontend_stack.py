"""CloudFront, private SPA hosting, HTTP API, TLS, and public DNS."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_apigatewayv2 as apigatewayv2,
)
from aws_cdk import (
    aws_certificatemanager as acm,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_route53 as route53,
)
from aws_cdk import (
    aws_route53_targets as route53_targets,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

from stacks.agent_stack import AgentStack
from stacks.common import REPO_ROOT, lambda_code, tag_stack
from stacks.survey_stack import SurveyStack


class FrontendStack(cdk.Stack):
    """Serve the Spanish experience and its Lambda API from one HTTPS origin."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        survey: SurveyStack,
        agent: AgentStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        hostname = self.node.try_get_context("hostname")
        zone_id = self.node.try_get_context("hostedZoneId")
        zone_name = self.node.try_get_context("hostedZoneName")
        domain_values = (hostname, zone_id, zone_name)
        if not all(domain_values):
            raise ValueError(
                "custom DNS requires hostname, hostedZoneId, and hostedZoneName contexts"
            )
        assert isinstance(hostname, str)
        assert isinstance(zone_id, str)
        assert isinstance(zone_name, str)
        if hostname != zone_name and not hostname.endswith(f".{zone_name}"):
            raise ValueError("hostname must belong to hostedZoneName")
        zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "PublicZone",
            hosted_zone_id=zone_id,
            zone_name=zone_name,
        )
        certificate = acm.Certificate(
            self,
            "Certificate",
            domain_name=hostname,
            validation=acm.CertificateValidation.from_dns(zone),
        )

        self.site_bucket = s3.Bucket(
            self,
            "Site",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        api_environment = {
            "EVENTS_TABLE": survey.events_table.table_name,
            "RESPONSES_TABLE": survey.responses_table.table_name,
            "INVENTORY_TABLE": survey.inventory_table.table_name,
            "FALLBACK_BUCKET": survey.fallback_bucket.bucket_name,
            "PRESENTER_SECRET_ARN": survey.presenter_secret.secret_arn,
            "WORKER_FUNCTION_NAME": agent.worker_function.function_name,
            "SYNTHETIC_RESPONSES_PATH": "/var/task/data/synthetic_responses.json",
            "PUBLIC_EVENT_ID": "demo-event",
        }
        self.api_function = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="chef_andino.cloud.api_handler.lambda_handler",
            code=lambda_code(),
            timeout=cdk.Duration.seconds(30),
            memory_size=1024,
            log_group=logs.LogGroup(
                self,
                "ApiLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            environment=api_environment,
        )
        survey.events_table.grant_read_write_data(self.api_function)
        survey.responses_table.grant_read_write_data(self.api_function)
        survey.inventory_table.grant_read_data(self.api_function)
        survey.fallback_bucket.grant_read_write(self.api_function)
        survey.presenter_secret.grant_read(self.api_function)
        agent.worker_function.grant_invoke(self.api_function)

        self.api = apigatewayv2.CfnApi(
            self,
            "HttpApi",
            name="chef-andino-api",
            protocol_type="HTTP",
            disable_execute_api_endpoint=False,
        )
        integration = apigatewayv2.CfnIntegration(
            self,
            "LambdaIntegration",
            api_id=self.api.ref,
            integration_type="AWS_PROXY",
            integration_uri=self.api_function.function_arn,
            payload_format_version="2.0",
            timeout_in_millis=29000,
        )
        route_keys = [
            "GET /api/events/{event_id}",
            "GET /api/events/{event_id}/stats",
            "POST /api/events/{event_id}/responses",
            "GET /api/events/{event_id}/menu",
            "POST /api/events/{event_id}/reset",
            "POST /api/events/{event_id}/freeze",
            "POST /api/events/{event_id}/generate",
            "GET /api/events/{event_id}/runs/{run_id}",
            "POST /api/events/{event_id}/fallback/reveal",
        ]
        for index, route_key in enumerate(route_keys):
            apigatewayv2.CfnRoute(
                self,
                f"Route{index}",
                api_id=self.api.ref,
                route_key=route_key,
                target=f"integrations/{integration.ref}",
            )
        stage = apigatewayv2.CfnStage(
            self,
            "DefaultStage",
            api_id=self.api.ref,
            stage_name="$default",
            auto_deploy=True,
            default_route_settings=apigatewayv2.CfnStage.RouteSettingsProperty(
                throttling_burst_limit=100,
                throttling_rate_limit=50,
            ),
        )
        stage.add_resource_dependency(integration)
        lambda_.CfnPermission(
            self,
            "ApiInvokePermission",
            action="lambda:InvokeFunction",
            function_name=self.api_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=(
                f"arn:{cdk.Aws.PARTITION}:execute-api:{cdk.Aws.REGION}:"
                f"{cdk.Aws.ACCOUNT_ID}:{self.api.ref}/*/*/*"
            ),
        )

        api_domain = f"{self.api.ref}.execute-api.{cdk.Aws.REGION}.{cdk.Aws.URL_SUFFIX}"
        spa_rewrite = cloudfront.Function(
            self,
            "SpaRewrite",
            code=cloudfront.FunctionCode.from_inline(
                """function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (!uri.startsWith('/api/') && !uri.split('/').pop().includes('.')) {
    request.uri = '/index.html';
  }
  return request;
}"""
            ),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            comment="Reescribe rutas de la SPA sin alterar respuestas de /api",
        )
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=[hostname],
            certificate=certificate,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                compress=True,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=spa_rewrite,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            additional_behaviors={
                "api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        api_domain,
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                    ),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=(
                        cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    compress=True,
                )
            },
        )
        distribution.node.add_dependency(stage)

        frontend_dist = REPO_ROOT / "frontend/dist"
        if not frontend_dist.exists():
            raise RuntimeError("falta frontend/dist; ejecuta npm run build antes de cdk synth")
        s3deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[s3deploy.Source.asset(str(frontend_dist))],
            destination_bucket=self.site_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            prune=True,
        )
        route53.ARecord(
            self,
            "AliasA",
            zone=zone,
            record_name=hostname,
            target=route53.RecordTarget.from_alias(
                route53_targets.CloudFrontTarget(distribution)
            ),
        )
        route53.AaaaRecord(
            self,
            "AliasAAAA",
            zone=zone,
            record_name=hostname,
            target=route53.RecordTarget.from_alias(
                route53_targets.CloudFrontTarget(distribution)
            ),
        )

        self.api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "ChefAndino"}},
            )
        )
        cdk.CfnOutput(self, "SiteUrl", value=f"https://{hostname}")
        cdk.CfnOutput(self, "ApiEndpoint", value=self.api.attr_api_endpoint)
        cdk.CfnOutput(self, "DistributionId", value=distribution.distribution_id)
        tag_stack(self)

"""Assertions over freshly synthesized Chef Andino CloudFormation templates."""

from __future__ import annotations

import json
from pathlib import Path

from aws_cdk.assertions import Match, Template

ROOT = Path(__file__).resolve().parents[2]


def template(name: str) -> Template:
    """Load the template emitted by the preceding ``cdk synth`` target."""
    path = ROOT / "cdk.out" / f"{name}.template.json"
    assert path.exists(), f"missing {path}; run make infra-synth"
    return Template.from_json(json.loads(path.read_text()))


def test_survey_uses_disposable_on_demand_tables_and_ttl() -> None:
    survey = template("ChefAndinoSurvey")
    survey.resource_count_is("AWS::DynamoDB::Table", 3)
    tables = survey.find_resources("AWS::DynamoDB::Table")
    assert all(item["Properties"]["BillingMode"] == "PAY_PER_REQUEST" for item in tables.values())
    assert all(item["DeletionPolicy"] == "Delete" for item in tables.values())
    ttl_tables = [
        item
        for item in tables.values()
        if item["Properties"].get("TimeToLiveSpecification")
        == {"AttributeName": "expires_at", "Enabled": True}
    ]
    assert len(ttl_tables) == 1
    survey.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    survey.resource_count_is("AWS::SecretsManager::Secret", 1)


def test_knowledge_base_is_s3_vectors_with_titan_v2() -> None:
    knowledge = template("ChefAndinoKnowledge")
    knowledge.has_resource_properties(
        "AWS::S3Vectors::Index",
        {
            "DataType": "float32",
            "Dimension": 1024,
            "DistanceMetric": "cosine",
            "IndexName": "chef-andino-culinary",
        },
    )
    knowledge.has_resource_properties(
        "AWS::Bedrock::KnowledgeBase",
        {
            "KnowledgeBaseConfiguration": {
                "Type": "VECTOR",
                "VectorKnowledgeBaseConfiguration": {
                    "EmbeddingModelArn": Match.any_value(),
                    "EmbeddingModelConfiguration": {
                        "BedrockEmbeddingModelConfiguration": {
                            "Dimensions": 1024,
                            "EmbeddingDataType": "FLOAT32",
                        }
                    },
                },
            },
            "StorageConfiguration": Match.object_like({"Type": "S3_VECTORS"}),
        },
    )
    knowledge.has_resource_properties(
        "AWS::Bedrock::DataSource",
        {
            "DataDeletionPolicy": "DELETE",
            "DataSourceConfiguration": Match.object_like({"Type": "S3"}),
        },
    )
    assert "amazon.titan-embed-text-v2:0" in json.dumps(knowledge.to_json())


def test_agentcore_budget_tools_and_temporal_policy_are_synthesized() -> None:
    agent = template("ChefAndinoAgent")
    agent.has_resource_properties(
        "AWS::BedrockAgentCore::Gateway",
        {
            "AuthorizerType": "AWS_IAM",
            "ProtocolType": "MCP",
            "PolicyEngineConfiguration": Match.object_like({"Mode": "ENFORCE"}),
        },
    )
    agent.resource_count_is("AWS::BedrockAgentCore::Policy", 6)
    policies = agent.find_resources("AWS::BedrockAgentCore::Policy")
    rendered_policies = json.dumps(policies)
    assert "formerly within 15m" in rendered_policies
    assert "output.passed: true" in rendered_policies
    assert "output.candidate_id: context.input.candidate_id" in rendered_policies

    targets = agent.find_resources("AWS::BedrockAgentCore::GatewayTarget")
    assert len(targets) == 1
    tools = next(iter(targets.values()))["Properties"]["TargetConfiguration"]["Mcp"]["Lambda"][
        "ToolSchema"
    ]["InlinePayload"]
    assert {item["Name"] for item in tools} == {
        "get_event_snapshot",
        "get_available_ingredients",
        "Retrieve",
        "evaluate_menu",
        "validate_menu",
        "publish_menu",
    }

    agent.has_resource_properties(
        "AWS::BedrockAgentCore::Harness",
        {
            "MaxIterations": 12,
            "MaxTokens": 20000,
            "TimeoutSeconds": 300,
            "Model": {
                "BedrockModelConfig": Match.object_like(
                    {"ModelId": "global.anthropic.claude-sonnet-4-6"}
                )
            },
        },
    )
    agent.has_resource_properties(
        "AWS::Lambda::EventInvokeConfig",
        {"MaximumEventAgeInSeconds": 900, "MaximumRetryAttempts": 0},
    )
    functions = agent.find_resources("AWS::Lambda::Function")
    assert any(
        item["Properties"].get("ReservedConcurrentExecutions") == 1
        for item in functions.values()
    )


def test_frontend_has_private_cloudfront_tls_dns_and_all_api_routes() -> None:
    frontend = template("ChefAndinoFrontend")
    frontend.has_resource_properties(
        "AWS::CertificateManager::Certificate",
        {
            "DomainName": "chef.example.com",
            "ValidationMethod": "DNS",
        },
    )
    frontend.has_resource_properties(
        "AWS::CloudFront::OriginAccessControl",
        {
            "OriginAccessControlConfig": Match.object_like(
                {"SigningBehavior": "always", "SigningProtocol": "sigv4"}
            )
        },
    )
    frontend.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": Match.object_like(
                {
                    "Aliases": ["chef.example.com"],
                    "DefaultRootObject": "index.html",
                    "IPV6Enabled": True,
                    "ViewerCertificate": Match.object_like(
                        {"MinimumProtocolVersion": "TLSv1.2_2021"}
                    ),
                }
            )
        },
    )
    frontend.has_resource_properties(
        "AWS::ApiGatewayV2::Api", {"ProtocolType": "HTTP"}
    )
    frontend.resource_count_is("AWS::ApiGatewayV2::Route", 9)
    records = frontend.find_resources("AWS::Route53::RecordSet")
    assert {item["Properties"]["Type"] for item in records.values()} == {"A", "AAAA"}


def test_iam_templates_do_not_grant_account_wide_admin_actions() -> None:
    for stack_name in (
        "ChefAndinoSurvey",
        "ChefAndinoKnowledge",
        "ChefAndinoAgent",
        "ChefAndinoFrontend",
    ):
        rendered = json.dumps(template(stack_name).to_json())
        assert "AdministratorAccess" not in rendered
        policies = template(stack_name).find_resources("AWS::IAM::Policy")
        for resource in policies.values():
            statements = resource["Properties"]["PolicyDocument"]["Statement"]
            for statement in statements:
                actions = statement.get("Action", [])
                actions = [actions] if isinstance(actions, str) else actions
                assert "*" not in actions

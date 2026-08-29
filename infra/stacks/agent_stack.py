"""AgentStack: managed loop, governed Gateway tools, and async worker."""

from __future__ import annotations

import json

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrockagentcore as agentcore,
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
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

from stacks.common import REPO_ROOT, lambda_code, tag_stack
from stacks.knowledge_stack import KnowledgeStack
from stacks.survey_stack import SurveyStack


def _object_schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


class AgentStack(cdk.Stack):
    """Provision AgentCore Harness, Gateway, Policy, and deterministic tools."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        survey: SurveyStack,
        knowledge: KnowledgeStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_environment = {
            "EVENTS_TABLE": survey.events_table.table_name,
            "RESPONSES_TABLE": survey.responses_table.table_name,
            "INVENTORY_TABLE": survey.inventory_table.table_name,
            "FALLBACK_BUCKET": survey.fallback_bucket.bucket_name,
            "KNOWLEDGE_BASE_ID": knowledge.knowledge_base.attr_knowledge_base_id,
            "PUBLIC_EVENT_ID": "demo-event",
        }
        self.tool_function = lambda_.Function(
            self,
            "ToolsFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="chef_andino.cloud.tool_handler.lambda_handler",
            code=lambda_code(),
            timeout=cdk.Duration.seconds(45),
            memory_size=1024,
            log_group=logs.LogGroup(
                self,
                "ToolsLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            environment=lambda_environment,
        )
        survey.events_table.grant_read_write_data(self.tool_function)
        survey.responses_table.grant_read_data(self.tool_function)
        survey.inventory_table.grant_read_data(self.tool_function)
        survey.fallback_bucket.grant_read_write(self.tool_function)
        self.tool_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:Retrieve"],
                resources=[knowledge.knowledge_base.attr_knowledge_base_arn],
            )
        )

        self.policy_engine = agentcore.CfnPolicyEngine(
            self,
            "PolicyEngine",
            name="chef_andino_policy",
            description="Gobernanza determinista de herramientas para la demo",
        )
        self.gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Invoca herramientas y evalúa Policy para Chef Andino",
        )
        self.tool_function.grant_invoke(self.gateway_role)
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:AuthorizeAction",
                    "bedrock-agentcore:PartiallyAuthorizeActions",
                    "bedrock-agentcore:GetPolicyEngine",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                ],
                resources=["*"],
            )
        )
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["*"],
            )
        )

        self.gateway = agentcore.CfnGateway(
            self,
            "Gateway",
            name="chef-andino-gateway",
            description="Superficie MCP gobernada de Chef Andino",
            role_arn=self.gateway_role.role_arn,
            authorizer_type="AWS_IAM",
            protocol_type="MCP",
            protocol_configuration=agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    instructions=(
                        "Herramientas del evento Chef Andino. Respeta event_id y cycle; "
                        "Policy deniega publicación sin validación previa."
                    ),
                    search_type="SEMANTIC",
                    supported_versions=["2025-06-18"],
                )
            ),
            policy_engine_configuration=(
                agentcore.CfnGateway.GatewayPolicyEngineConfigurationProperty(
                    arn=self.policy_engine.attr_policy_engine_arn,
                    mode="ENFORCE",
                )
            ),
            tags={"Project": "ChefAndino", "Environment": "demo"},
        )
        gateway_role_policy = self.gateway_role.node.find_child("DefaultPolicy")
        self.gateway.node.add_dependency(gateway_role_policy)

        common = {
            "event_id": {"type": "string", "description": "Siempre demo-event"},
            "cycle": {"type": "integer", "description": "Ciclo activo de la misión"},
        }
        menu = {
            "type": "object",
            "description": "Menú completo conforme al JSON Schema indicado en las instrucciones",
        }
        tool_definitions = [
            {
                "name": "get_event_snapshot",
                "description": "Obtiene el snapshot agregado e inmutable del ciclo activo.",
                "inputSchema": _object_schema(common, ["event_id", "cycle"]),
                "outputSchema": _object_schema({}, []),
            },
            {
                "name": "get_available_ingredients",
                "description": "Lista inventario real, stock, alérgenos y banderas dietarias.",
                "inputSchema": _object_schema(common, ["event_id", "cycle"]),
                "outputSchema": _object_schema(
                    {"items": {"type": "array", "items": {"type": "object"}}}, ["items"]
                ),
            },
            {
                "name": "Retrieve",
                "description": "Recupera conocimiento culinario desde la KB con S3 Vectors.",
                "inputSchema": _object_schema(
                    common
                    | {
                        "query": {"type": "string"},
                        "number_of_results": {"type": "integer", "minimum": 1, "maximum": 8},
                    },
                    ["event_id", "cycle", "query"],
                ),
                "outputSchema": _object_schema(
                    {
                        "retrievalResults": {
                            "type": "array",
                            "items": {"type": "object"},
                        }
                    },
                    ["retrievalResults"],
                ),
            },
            {
                "name": "evaluate_menu",
                "description": "Calcula score y hard gates; un fallo produce score cero.",
                "inputSchema": _object_schema(
                    common | {"menu": menu}, ["event_id", "cycle", "menu"]
                ),
                "outputSchema": _object_schema(
                    {
                        "total_score": {"type": "number"},
                        "hard_gates_passed": {"type": "boolean"},
                        "failed_gates": {"type": "array", "items": {"type": "string"}},
                    },
                    ["total_score", "hard_gates_passed"],
                ),
            },
            {
                "name": "validate_menu",
                "description": "Valida y registra un candidato; no publica.",
                "inputSchema": _object_schema(
                    common | {"candidate_id": {"type": "string"}, "menu": menu},
                    ["event_id", "cycle", "candidate_id", "menu"],
                ),
                "outputSchema": _object_schema(
                    {
                        "candidate_id": {"type": "string"},
                        "passed": {"type": "boolean"},
                        "menu_hash": {"type": "string"},
                        "failed_checks": {"type": "array", "items": {"type": "object"}},
                    },
                    ["candidate_id", "passed", "menu_hash"],
                ),
            },
            {
                "name": "publish_menu",
                "description": "Publica exclusivamente el candidato previamente validado.",
                "inputSchema": _object_schema(
                    common | {"candidate_id": {"type": "string"}},
                    ["event_id", "cycle", "candidate_id"],
                ),
                "outputSchema": _object_schema(
                    {
                        "published": {"type": "boolean"},
                        "menu_id": {"type": "string"},
                        "candidate_id": {"type": "string"},
                    },
                    ["published", "candidate_id"],
                ),
            },
        ]
        self.tools_target = agentcore.CfnGatewayTarget(
            self,
            "ToolsTarget",
            gateway_identifier=self.gateway.attr_gateway_identifier,
            name="ChefTools",
            description="Herramientas deterministas del evento",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=agentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.tool_function.function_arn,
                        tool_schema=agentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=tool_definitions
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
        )

        gateway_arn = self.gateway.attr_gateway_arn
        permit_actions = [
            "ChefTools___get_event_snapshot",
            "ChefTools___get_available_ingredients",
            "ChefTools___Retrieve",
            "ChefTools___evaluate_menu",
            "ChefTools___validate_menu",
        ]
        for index, action in enumerate(permit_actions):
            policy = agentcore.CfnPolicy(
                self,
                f"PermitPolicy{index}",
                name=f"permit_{action.lower().replace('___', '_')}",
                policy_engine_id=self.policy_engine.attr_policy_engine_id,
                enforcement_mode="ACTIVE",
                validation_mode="IGNORE_ALL_FINDINGS",
                definition=agentcore.CfnPolicy.PolicyDefinitionProperty(
                    cedar=agentcore.CfnPolicy.CedarPolicyProperty(
                        statement=(
                            "permit (principal, "
                            f'action == AgentCore::Action::"{action}", '
                            f'resource == AgentCore::Gateway::"{gateway_arn}");'
                        )
                    )
                ),
            )
            policy.add_resource_dependency(self.tools_target)

        self.publish_policy = agentcore.CfnPolicy(
            self,
            "PublishTemporalPolicy",
            name="publish_after_validation",
            policy_engine_id=self.policy_engine.attr_policy_engine_id,
            enforcement_mode="ACTIVE",
            validation_mode="IGNORE_ALL_FINDINGS",
            definition=agentcore.CfnPolicy.PolicyDefinitionProperty(
                policy=agentcore.CfnPolicy.PolicyStatementProperty(
                    statement=(
                        "permit (principal, "
                        'action == AgentCore::Action::"ChefTools___publish_menu", '
                        f'resource == AgentCore::Gateway::"{gateway_arn}") '
                        "when temporal { formerly within 15m "
                        'AgentCore::Action::"ChefTools___validate_menu"::response{ '
                        "eventResource: resource, output.passed: true, "
                        "output.candidate_id: context.input.candidate_id } };"
                    )
                )
            ),
        )
        self.publish_policy.add_resource_dependency(self.tools_target)

        self.mcp_proxy_secret = secretsmanager.Secret(
            self,
            "McpProxySecret",
            description="Token interno del puente MCP de Chef Andino",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=48,
                exclude_punctuation=True,
            ),
        )
        self.mcp_proxy_function = lambda_.Function(
            self,
            "McpProxy",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="chef_andino.cloud.mcp_proxy_handler.lambda_handler",
            code=lambda_code(),
            timeout=cdk.Duration.seconds(60),
            memory_size=512,
            log_group=logs.LogGroup(
                self,
                "McpProxyLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            environment={
                "GATEWAY_URL": self.gateway.attr_gateway_url,
                "MCP_PROXY_SECRET_ARN": self.mcp_proxy_secret.secret_arn,
            },
        )
        self.mcp_proxy_secret.grant_read(self.mcp_proxy_function)
        self.mcp_proxy_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeGateway"],
                resources=[self.gateway.attr_gateway_arn],
            )
        )
        self.mcp_proxy_url = self.mcp_proxy_function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.BUFFERED,
        )

        self.harness_role = iam.Role(
            self,
            "HarnessRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Modelo y Gateway del Harness Chef Andino",
        )
        self.harness_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock-agentcore:InvokeGateway",
                ],
                resources=["*"],
            )
        )
        self.harness_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["*"],
            )
        )
        self.harness_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                resources=[
                    f"arn:{self.partition}:bedrock-agentcore:{self.region}:"
                    f"{self.account}:memory/ChefAndinoHarness-*"
                ],
            )
        )

        system_prompt = (REPO_ROOT / "src/chef_andino/planner/prompts/system_prompt.md").read_text()
        menu_schema = json.loads(
            (REPO_ROOT / "src/chef_andino/contracts/schemas/menu.schema.json").read_text()
        )
        system_prompt += "\n\n## JSON Schema exacto del menú\n```json\n"
        system_prompt += json.dumps(menu_schema, ensure_ascii=False)
        system_prompt += "\n```\n"
        model_id = self.node.try_get_context("modelId") or "global.anthropic.claude-sonnet-4-6"
        self.harness = agentcore.CfnHarness(
            self,
            "Harness",
            harness_name="ChefAndinoHarness",
            execution_role_arn=self.harness_role.role_arn,
            model=agentcore.CfnHarness.HarnessModelConfigurationProperty(
                bedrock_model_config=agentcore.CfnHarness.HarnessBedrockModelConfigProperty(
                    model_id=model_id,
                    max_tokens=4096,
                    temperature=0.2,
                )
            ),
            system_prompt=[{"text": system_prompt}],
            tools=[
                agentcore.CfnHarness.HarnessToolProperty(
                    type="agentcore_gateway",
                    name="chef_tools",
                    config=agentcore.CfnHarness.HarnessToolConfigurationProperty(
                        agent_core_gateway=(
                            agentcore.CfnHarness.HarnessAgentCoreGatewayConfigProperty(
                                gateway_arn=self.gateway.attr_gateway_arn,
                                outbound_auth=(
                                    agentcore.CfnHarness.HarnessGatewayOutboundAuthProperty(
                                        aws_iam={}
                                    )
                                ),
                            )
                        )
                    ),
                )
            ],
            allowed_tools=["*"],
            max_iterations=12,
            max_tokens=20000,
            timeout_seconds=300,
            tags=[
                cdk.CfnTag(key="Project", value="ChefAndino"),
                cdk.CfnTag(key="Environment", value="demo"),
            ],
        )
        self.harness.add_resource_dependency(self.tools_target)
        self.harness.add_resource_dependency(self.publish_policy)

        self.worker_function = lambda_.Function(
            self,
            "AgentWorker",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="chef_andino.cloud.worker_handler.lambda_handler",
            code=lambda_code(),
            timeout=cdk.Duration.minutes(10),
            memory_size=1024,
            reserved_concurrent_executions=1,
            log_group=logs.LogGroup(
                self,
                "AgentWorkerLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            environment=lambda_environment
            | {
                "HARNESS_ARN": self.harness.attr_arn,
                "MCP_PROXY_URL": self.mcp_proxy_url.url,
                "MCP_PROXY_SECRET_ARN": self.mcp_proxy_secret.secret_arn,
            },
        )
        self.worker_function.configure_async_invoke(
            retry_attempts=0,
            max_event_age=cdk.Duration.minutes(15),
        )
        survey.events_table.grant_read_write_data(self.worker_function)
        survey.responses_table.grant_read_data(self.worker_function)
        survey.inventory_table.grant_read_data(self.worker_function)
        survey.fallback_bucket.grant_read_write(self.worker_function)
        self.mcp_proxy_secret.grant_read(self.worker_function)
        self.worker_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeHarness",
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                resources=[self.harness.attr_arn],
            )
        )

        cdk.CfnOutput(self, "HarnessArn", value=self.harness.attr_arn)
        cdk.CfnOutput(self, "GatewayArn", value=self.gateway.attr_gateway_arn)
        cdk.CfnOutput(self, "PolicyEngineArn", value=self.policy_engine.attr_policy_engine_arn)
        cdk.CfnOutput(self, "WorkerFunctionName", value=self.worker_function.function_name)
        cdk.CfnOutput(self, "McpProxyUrl", value=self.mcp_proxy_url.url)
        tag_stack(self)

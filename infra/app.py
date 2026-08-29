"""AWS CDK application for the complete Chef Andino demonstration."""

import os

import aws_cdk as cdk
from stacks.agent_stack import AgentStack
from stacks.frontend_stack import FrontendStack
from stacks.knowledge_stack import KnowledgeStack
from stacks.survey_stack import SurveyStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=(
        app.node.try_get_context("region")
        or os.environ.get("CDK_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or "us-east-1"
    ),
)

survey = SurveyStack(app, "ChefAndinoSurvey", env=env)
knowledge = KnowledgeStack(app, "ChefAndinoKnowledge", env=env)
agent = AgentStack(
    app,
    "ChefAndinoAgent",
    env=env,
    survey=survey,
    knowledge=knowledge,
)
FrontendStack(
    app,
    "ChefAndinoFrontend",
    env=env,
    survey=survey,
    agent=agent,
)

app.synth()

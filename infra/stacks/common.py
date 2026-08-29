"""Shared CDK helpers for Lambda packaging and demo tags."""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_

REPO_ROOT = Path(__file__).resolve().parents[2]


def lambda_code() -> lambda_.Code:
    """Bundle the package, current boto3, and reproducible data files."""
    return lambda_.Code.from_asset(
        str(REPO_ROOT),
        exclude=[
            ".git/**",
            ".venv/**",
            ".cloud/**",
            ".localdata/**",
            ".github/**",
            "docs/**",
            "frontend/**",
            "infra/**",
            "scripts/**",
            "frontend/node_modules/**",
            "frontend/dist/**",
            "infra/.venv/**",
            "infra/cdk.out/**",
            "tests/**",
        ],
        ignore_mode=cdk.IgnoreMode.GLOB,
        bundling=cdk.BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            command=[
                "bash",
                "-c",
                "python -m pip install '.[aws]' -t /asset-output "
                "&& cp -R data /asset-output/data",
            ],
        ),
    )


def tag_stack(stack: cdk.Stack) -> None:
    """Apply consistent ownership and cost-allocation tags."""
    cdk.Tags.of(stack).add("Project", "ChefAndino")
    cdk.Tags.of(stack).add("Environment", "demo")

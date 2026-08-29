#!/usr/bin/env python3
"""Export live CloudFormation outputs for operational scripts."""

from __future__ import annotations

import json
from pathlib import Path

import boto3

from chef_andino.config import aws_region

ROOT = Path(__file__).resolve().parents[1]
STACKS = (
    "ChefAndinoSurvey",
    "ChefAndinoKnowledge",
    "ChefAndinoAgent",
    "ChefAndinoFrontend",
)


def main() -> None:
    client = boto3.client("cloudformation", region_name=aws_region())
    result = {}
    for name in STACKS:
        stack = client.describe_stacks(StackName=name)["Stacks"][0]
        result[name] = {
            output["OutputKey"]: output["OutputValue"]
            for output in stack.get("Outputs", [])
        }
    path = ROOT / ".cloud/outputs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    print(f"exported live outputs to {path}")


if __name__ == "__main__":
    main()

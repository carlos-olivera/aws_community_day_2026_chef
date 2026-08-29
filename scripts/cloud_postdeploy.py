#!/usr/bin/env python3
"""Complete Bedrock ingestion and upload the initial fallback artifact."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import boto3

from chef_andino.config import aws_region

ROOT = Path(__file__).resolve().parents[1]


def outputs() -> dict:
    return json.loads((ROOT / ".cloud/outputs.json").read_text())


def ingest(values: dict) -> None:
    knowledge = values["ChefAndinoKnowledge"]
    client = boto3.client("bedrock-agent", region_name=aws_region())
    knowledge_base_id = knowledge["KnowledgeBaseId"]
    data_source_id = knowledge["DataSourceId"]
    job = client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
        description="Chef Andino deployment corpus",
    )["ingestionJob"]
    ingestion_job_id = job["ingestionJobId"]
    print(f"ingestion job {ingestion_job_id} started")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        job = client.get_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            ingestionJobId=ingestion_job_id,
        )["ingestionJob"]
        status = job["status"]
        print(f"ingestion status: {status}")
        if status == "COMPLETE":
            break
        if status in {"FAILED", "STOPPED"}:
            raise RuntimeError(f"ingestion failed: {job.get('failureReasons', [])}")
        time.sleep(10)
    else:
        raise TimeoutError("Bedrock ingestion did not complete in 15 minutes")

    runtime = boto3.client("bedrock-agent-runtime", region_name=aws_region())
    result = runtime.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": "plato boliviano con quinua para un buffet"},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    if not result.get("retrievalResults"):
        raise RuntimeError("RAG retrieval returned no documents after ingestion")
    print(f"RAG retrieval verified with {len(result['retrievalResults'])} results")


def upload_fallback(values: dict) -> None:
    bucket = values["ChefAndinoSurvey"]["FallbackBucketName"]
    artifact = ROOT / ".cloud/fallback/last-good.json"
    boto3.client("s3", region_name=aws_region()).upload_file(
        str(artifact),
        bucket,
        "fallback/last-good.json",
        ExtraArgs={"ContentType": "application/json", "ServerSideEncryption": "AES256"},
    )
    print(f"uploaded private fallback artifact to s3://{bucket}/fallback/last-good.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--upload-fallback", action="store_true")
    args = parser.parse_args()
    values = outputs()
    if args.ingest:
        ingest(values)
    if args.upload_fallback:
        upload_fallback(values)


if __name__ == "__main__":
    main()

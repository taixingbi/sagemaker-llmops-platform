#!/usr/bin/env python3
"""Cost-control helpers: delete endpoints, optionally stop pipeline executions."""

from __future__ import annotations

import argparse
import sys

import boto3


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", default=None)
    p.add_argument("--prefix", default="llm-finetune", help="Only touch resources with this name prefix")
    p.add_argument("--delete-endpoints", action="store_true")
    p.add_argument("--stop-executions", action="store_true")
    p.add_argument("--pipeline-name", default="llm-finetune-dev")
    p.add_argument("--yes", action="store_true", help="Skip confirmation")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    sm = boto3.client("sagemaker", region_name=args.region)

    if not args.yes:
        print("Refusing to run without --yes (safety).", file=sys.stderr)
        return 2

    if args.delete_endpoints:
        for page in sm.get_paginator("list_endpoints").paginate():
            for ep in page.get("Endpoints", []):
                name = ep["EndpointName"]
                if name.startswith(args.prefix):
                    print(f"deleting endpoint {name}")
                    sm.delete_endpoint(EndpointName=name)

    if args.stop_executions:
        resp = sm.list_pipeline_executions(
            PipelineName=args.pipeline_name,
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=20,
        )
        for exe in resp.get("PipelineExecutionSummaries", []):
            status = exe["PipelineExecutionStatus"]
            arn = exe["PipelineExecutionArn"]
            if status in {"Executing", "Stopping"}:
                print(f"stopping {arn}")
                sm.stop_pipeline_execution(PipelineExecutionArn=arn)

    print("cleanup complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Staging smoke test against a SageMaker endpoint (Week 4)."""

from __future__ import annotations

import argparse
import json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint-name", required=True)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    payload = {"inputs": "### Instruction:\nSay hi\n\n### Response:\n", "parameters": {"max_new_tokens": 16}}
    if args.dry_run:
        print(f"[dry-run] would invoke {args.endpoint_name} with {json.dumps(payload)}")
        return 0
    raise NotImplementedError("Week 4: boto3 sagemaker-runtime invoke_endpoint + assertions")


if __name__ == "__main__":
    raise SystemExit(main())

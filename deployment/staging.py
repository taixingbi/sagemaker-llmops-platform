"""Deploy an approved model package to a short-lived staging endpoint (Week 4)."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-package-arn", required=True)
    p.add_argument("--endpoint-name", default="llm-finetune-staging")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        print(f"[dry-run] would create staging endpoint {args.endpoint_name} from {args.model_package_arn}")
        return 0
    raise NotImplementedError("Week 4: implement CreateModel + EndpointConfig + Endpoint")


if __name__ == "__main__":
    raise SystemExit(main())

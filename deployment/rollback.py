"""Rollback production endpoint to previous variant (Week 5)."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint-name", default="llm-finetune-prod")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        print(f"[dry-run] would rollback endpoint {args.endpoint_name}")
        return 0
    raise NotImplementedError("Week 5: shift 100% traffic to previous variant / recreate")


if __name__ == "__main__":
    raise SystemExit(main())

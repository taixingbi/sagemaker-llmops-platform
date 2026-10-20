"""Dataset schema validation for instruction-tuning JSONL.

Runnable as a SageMaker Processing entrypoint or locally:

    python validate.py --input /opt/ml/processing/input \\
        --output /opt/ml/processing/output --schema /opt/ml/processing/schema/instruction.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FILES = ("train.jsonl", "eval.jsonl")


def load_schema(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{i}: invalid JSON: {exc}") from exc
    return rows


def _validate_row_builtin(row: dict[str, Any], schema: dict[str, Any], loc: str) -> list[str]:
    """Minimal JSON Schema subset for instruction records (no external deps)."""
    errors: list[str] = []
    required = schema.get("required", [])
    props = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    if not isinstance(row, dict):
        return [f"{loc}: expected object"]

    for key in required:
        if key not in row:
            errors.append(f"{loc}: missing required property '{key}'")

    if additional is False:
        for key in row:
            if key not in props:
                errors.append(f"{loc}: unexpected property '{key}'")

    for key, rules in props.items():
        if key not in row:
            continue
        value = row[key]
        expected = rules.get("type")
        if expected == "string" and not isinstance(value, str):
            errors.append(f"{loc}: '{key}' must be string")
        elif isinstance(value, str) and "minLength" in rules and len(value) < rules["minLength"]:
            errors.append(f"{loc}: '{key}' shorter than minLength {rules['minLength']}")
    return errors


def validate_row(row: dict[str, Any], schema: dict[str, Any], loc: str) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, ValidationError

        validator = Draft202012Validator(schema)
        try:
            validator.validate(row)
            return []
        except ValidationError as exc:
            return [f"{loc}: {exc.message}"]
    except ImportError:
        return _validate_row_builtin(row, schema, loc)


def validate_file(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    rows = iter_jsonl(path)
    if not rows:
        raise ValueError(f"{path.name}: empty dataset")

    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        errors.extend(validate_row(row, schema, f"{path.name}:{i}"))

    if errors:
        preview = "\n".join(errors[:20])
        raise ValueError(f"schema validation failed ({len(errors)} errors)\n{preview}")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "file": path.name,
        "rows": len(rows),
        "sha256": digest,
    }


def write_manifest(output_dir: Path, files_meta: list[dict[str, Any]], status: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": status,
        "files": files_meta,
        "dataset_hash": hashlib.sha256(
            "".join(sorted(m["sha256"] for m in files_meta)).encode()
        ).hexdigest()
        if files_meta
        else "",
    }
    path = output_dir / "validation_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def copy_validated(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_FILES:
        src = input_dir / name
        dst = output_dir / name
        dst.write_bytes(src.read_bytes())


def run(input_dir: Path, output_dir: Path, schema_path: Path) -> dict[str, Any]:
    schema = load_schema(schema_path)

    for name in REQUIRED_FILES:
        path = input_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing required file: {name}")

    meta = [validate_file(input_dir / name, schema) for name in REQUIRED_FILES]
    copy_validated(input_dir, output_dir / "data")
    manifest_path = write_manifest(output_dir, meta, status="PASSED")
    print(f"validation PASSED → {manifest_path}")
    return json.loads(manifest_path.read_text())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate instruction-tuning JSONL")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(args.input, args.output, args.schema)
    except Exception as exc:  # noqa: BLE001 — entrypoint surfaces any failure
        print(f"VALIDATION_FAILED: {exc}", file=sys.stderr)
        try:
            write_manifest(args.output, [], status="FAILED")
        except Exception:  # noqa: BLE001
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

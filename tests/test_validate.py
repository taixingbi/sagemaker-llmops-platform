from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.preprocessing.validate import run, write_manifest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
SCHEMA = ROOT / "data" / "schemas" / "instruction.json"


def test_valid_sample_dataset(tmp_path: Path) -> None:
    out = tmp_path / "out"
    manifest = run(SAMPLE, out, SCHEMA)
    assert manifest["status"] == "PASSED"
    assert len(manifest["files"]) == 2
    assert (out / "data" / "train.jsonl").is_file()
    assert (out / "data" / "eval.jsonl").is_file()
    assert len(manifest["dataset_hash"]) == 64


def test_schema_error_blocks(tmp_path: Path) -> None:
    bad = tmp_path / "in"
    bad.mkdir()
    (bad / "train.jsonl").write_text('{"instruction": "x"}\n')  # missing output
    (bad / "eval.jsonl").write_text(
        json.dumps({"instruction": "a", "output": "b"}) + "\n"
    )
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="schema validation failed"):
        run(bad, out, SCHEMA)


def test_failed_manifest_helper(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, [], status="FAILED")
    data = json.loads(path.read_text())
    assert data["status"] == "FAILED"

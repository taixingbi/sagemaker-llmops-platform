import json

from src.inference.inference import input_fn, output_fn


def test_input_fn_accepts_prompt() -> None:
    payload = input_fn(json.dumps({"prompt": "hello"}))
    assert payload["prompt"] == "hello"


def test_input_fn_rejects_bad_content_type() -> None:
    try:
        input_fn("{}", content_type="text/plain")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unsupported" in str(exc)


def test_output_fn_json() -> None:
    raw = output_fn({"generated_text": "hi"})
    assert json.loads(raw)["generated_text"] == "hi"

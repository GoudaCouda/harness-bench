from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from regrade_benchmark_run import _reparsed_cached_judge  # noqa: E402


def request() -> dict:
    return {
        "rubric": {"criteria": [{"id": "handoff"}]},
        "candidate": {"artifact": "handoff.md", "text": "Recovery is pending review."},
    }


def test_reparse_complete_error_response_without_model_call() -> None:
    cached = {
        "status": "error",
        "raw_output": '{"criteria":{"handoff":{"verdict":"pass","evidence":["pending review"],"reason":"bounded"}}}',
        "error": "old parser rejected mapping",
    }
    result = _reparsed_cached_judge(cached, request())
    assert result is not None
    assert result["status"] == "completed"
    assert result["verdicts"][0]["verdict"] == "pass"
    assert result["prior_error"] == "old parser rejected mapping"


def test_reparse_rejects_ungrounded_pass_evidence() -> None:
    cached = {
        "status": "error",
        "raw_output": '{"criteria":[{"id":"handoff","verdict":"pass","evidence":["not in candidate"],"reason":"unsupported"}]}',
    }
    assert _reparsed_cached_judge(cached, request()) is None


def test_reparse_does_not_replace_completed_sidecar() -> None:
    cached = {"status": "completed", "raw_output": "{}"}
    assert _reparsed_cached_judge(cached, request()) is None

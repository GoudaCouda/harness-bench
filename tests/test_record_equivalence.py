from __future__ import annotations

from harnessbench.grading.record_equivalence import (
    decision_ids,
    ids_match,
    indexed_decisions,
    jsonrpc_responses_equivalent,
    repeated_verification_ok,
)


def test_indexed_decisions_accepts_explicit_or_input_order() -> None:
    expected = [{"index": 0}, {"index": 1}]
    assert indexed_decisions(
        {
            "decisions": [
                {"index": 1, "decision": "held"},
                {"index": 0, "decision": "admitted"},
            ]
        },
        expected,
    ) == {1: "held", 0: "admitted"}
    assert indexed_decisions(
        {
            "decisions": [
                {"id": "a", "decision": "admitted"},
                {"id": "b", "decision": "held"},
            ]
        },
        expected,
    ) == {0: "admitted", 1: "held"}


def test_indexed_decisions_rejects_partial_indices_and_wrong_coverage() -> None:
    expected = [{"index": 0}, {"index": 1}]
    assert (
        indexed_decisions(
            {
                "decisions": [
                    {"index": 0, "decision": "admitted"},
                    {"decision": "held"},
                ]
            },
            expected,
        )
        == {}
    )
    assert indexed_decisions({"decisions": [{"decision": "admitted"}]}, expected) == {}


def test_decision_ids_accepts_flat_and_grouped_forms() -> None:
    assert decision_ids({"released_ids": ["a"]}, "released") == ["a"]
    assert decision_ids({"ids": {"released": ["a"]}}, "released") == ["a"]
    assert decision_ids({"released": ["a"]}, "released") == ["a"]
    assert decision_ids({"selected_items": ["a"]}, "selected") == ["a"]


def test_ids_match_is_order_insensitive_but_duplicate_sensitive() -> None:
    assert ids_match(["b", "a"], ["a", "b"])
    assert not ids_match(["a", "a"], ["a"])
    assert not ids_match("a", ["a"])


def test_repeated_verification_requires_two_passes_and_stability() -> None:
    assert repeated_verification_ok(
        {
            "attempts": [{"result": {"ok": True}}, {"result": "pass"}],
            "idempotent": True,
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"result": {"ok": True}, "state_changed": False},
                {"result": {"ok": True}, "state_changed": False},
            ]
        }
    )
    assert repeated_verification_ok(
        [
            {"result": "success"},
            {"result": "success"},
            {"idempotent": True},
        ]
    )
    assert repeated_verification_ok(
        {
            "runs": [{"status": "passed"}, {"status": "passed"}],
            "idempotency_check": {"state_unchanged_on_repeat": True},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"result": "fail"},
                {"result": "fail"},
                {"result": "pass"},
            ],
            "idempotency_check": {
                "rerun_result": "pass",
                "state_unchanged": True,
            },
        }
    )
    assert not repeated_verification_ok(
        {"attempts": [{"result": "pass"}], "idempotent": True}
    )
    assert not repeated_verification_ok(
        {"attempts": [{"result": "pass"}, {"result": "pass"}]}
    )
    assert not repeated_verification_ok(
        {
            "attempts": [{"result": "pass"}, {"result": "pass"}],
            "idempotency_check": {"note": "checked"},
        }
    )


def test_repeated_verification_accepts_prompt_equivalent_aliases() -> None:
    assert repeated_verification_ok(
        {
            "validate_attempts": [
                {"ok": False},
                {"ok": True},
                {"ok": True},
            ],
            "repeat_behavior": {"state_unchanged_on_rerun": True},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"result": {"ok": True}},
                {"result": {"ok": True}},
            ],
            "state_unchanged_on_rerun": True,
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"ok": True},
                {"ok": True},
            ],
            "state_integrity_check": {"unchanged": True},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"output": {"ok": True}},
                {"output": {"ok": True}},
            ],
            "repeat_behavior": {"state_files_changed_by_rerun": False},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"outcome": "pass", "controller_output": {"ok": True}},
                {"outcome": "pass", "controller_output": {"ok": True}},
            ],
            "repeat_behavior": {"state_unchanged_after_rerun": True},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"result": {"ok": True}},
                {"result": {"ok": True}},
            ],
            "idempotency_check": {"state_changed_on_rerun": False},
        }
    )
    assert repeated_verification_ok(
        {
            "attempts": [
                {"stdout": {"ok": True}},
                {"stdout": {"ok": True}},
            ],
            "repeat_behavior": {"rerun_left_state_unchanged": True},
        }
    )


def test_jsonrpc_equivalence_allows_only_error_message_wording() -> None:
    expected = [
        {"jsonrpc": "2.0", "id": 1, "result": {"accepted": True}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32001, "message": "held", "data": {"reason": "x"}},
        },
    ]
    actual = [
        {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {
                "code": -32001,
                "message": "Request requires review",
                "data": {"reason": "x"},
            },
        },
        {"jsonrpc": "2.0", "id": 1, "result": {"accepted": True}},
    ]
    assert jsonrpc_responses_equivalent(actual, expected)
    actual[0]["error"]["code"] = -32002
    assert not jsonrpc_responses_equivalent(actual, expected)

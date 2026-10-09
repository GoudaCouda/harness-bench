"""Conservative normalization for prompt-equivalent operational records."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


def indexed_decisions(
    document: object, expected: Sequence[Mapping[str, Any]]
) -> dict[int, str]:
    """Read decisions keyed by explicit index or, when absent, declared list order."""

    records = document.get("decisions") if isinstance(document, Mapping) else document
    if not isinstance(records, list) or len(records) != len(expected):
        return {}
    entries = [entry for entry in records if isinstance(entry, Mapping)]
    if len(entries) != len(records):
        return {}
    explicit = [entry.get("index") for entry in entries]
    if all(
        isinstance(index, int) and not isinstance(index, bool) for index in explicit
    ):
        if len(set(explicit)) != len(explicit):
            return {}
        return {int(entry["index"]): str(entry.get("decision")) for entry in entries}
    if any(
        isinstance(index, int) and not isinstance(index, bool) for index in explicit
    ):
        return {}
    expected_indices = [entry.get("index") for entry in expected]
    if not all(
        isinstance(index, int) and not isinstance(index, bool)
        for index in expected_indices
    ):
        return {}
    return {
        int(expected_entry["index"]): str(actual_entry.get("decision"))
        for expected_entry, actual_entry in zip(expected, entries, strict=True)
    }


def decision_ids(document: object, decision: str) -> list[str] | None:
    """Read an ID list from documented flat or grouped representations."""

    if not isinstance(document, Mapping):
        return None
    candidates = [
        document.get(f"{decision}_ids"),
        document.get(f"{decision}_items"),
        document.get(decision),
    ]
    for group_name in ("ids", "lists", "id_lists"):
        group = document.get(group_name)
        if isinstance(group, Mapping):
            candidates.append(group.get(decision))
    for candidate in candidates:
        if isinstance(candidate, list) and all(
            isinstance(item, (str, int)) and not isinstance(item, bool)
            for item in candidate
        ):
            return [str(item) for item in candidate]
    return None


def ids_match(actual: object, expected: object) -> bool:
    """Compare set-like ID collections while preserving duplicate detection."""

    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if not all(
        isinstance(item, (str, int)) and not isinstance(item, bool)
        for item in [*actual, *expected]
    ):
        return False
    return Counter(map(str, actual)) == Counter(map(str, expected))


def _pass_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        if value.get("ok") is True:
            return True
        for key in (
            "status",
            "result",
            "output",
            "outcome",
            "controller_output",
            "stdout",
        ):
            if key in value and _pass_value(value.get(key)):
                return True
        return False
    if isinstance(value, str):
        rendered = value.strip()
        try:
            decoded = json.loads(rendered)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if decoded is not None and decoded != value:
            return _pass_value(decoded)
        normalized = " ".join(rendered.casefold().split())
        if normalized in {
            "ok",
            "pass",
            "passed",
            "success",
            "successful",
            "completed",
        }:
            return True
        return (
            bool(re.search(r"\bok\s*:\s*true\b", normalized))
            and "ok: false" not in normalized
        )
    return False


_ATTEMPT_LIST_KEYS = (
    "runs",
    "attempts",
    "verification_steps",
    "results",
    "validate_attempts",
    "validate_runs",
    "verification_attempts",
    "repeat_runs",
)
_STABILITY_KEYS = (
    "idempotent",
    "stable",
    "unchanged",
    "state_unchanged",
    "state_unchanged_on_repeat",
    "state_unchanged_on_rerun",
    "state_unchanged_after_rerun",
    "state_unchanged_by_re_run",
    "rerun_left_state_unchanged",
    "state_consistent",
    "result_stable_across_repeats",
    "repeat_run",
)
_UNCHANGED_FALSE_KEYS = (
    "state_changed",
    "state_changed_on_rerun",
    "state_files_changed_by_rerun",
    "changed_on_rerun",
)


def _mapping_layers(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Root plus one level of nested objects (repeat_behavior, idempotency_check)."""

    layers: list[Mapping[str, Any]] = [document]
    for value in document.values():
        if isinstance(value, Mapping):
            layers.append(value)
    return layers


def _stability_flag(item: Mapping[str, Any]) -> bool:
    for key in _STABILITY_KEYS:
        if key not in item:
            continue
        value = item.get(key)
        if value is True or _pass_value(value):
            return True
    for key in _UNCHANGED_FALSE_KEYS:
        if item.get(key) is False:
            return True
    return False


def repeated_verification_ok(document: object) -> bool:
    """Accept equivalent repeat-pass records only when stability is explicit.

    Field names are not prescribed. Common aliases such as ``validate_attempts``
    and ``state_unchanged_on_rerun`` count; a nested ``repeat_behavior`` object
    may carry the stability flag.
    """

    if isinstance(document, Mapping):
        records = next(
            (
                document.get(key)
                for key in _ATTEMPT_LIST_KEYS
                if isinstance(document.get(key), list)
            ),
            None,
        )
        root_items = [
            *_mapping_layers(document),
            *[item for item in records or [] if isinstance(item, Mapping)],
        ]
    elif isinstance(document, list):
        records = document
        root_items = [item for item in document if isinstance(item, Mapping)]
    else:
        return False
    if not isinstance(records, list):
        return False
    passing = [record for record in records if _pass_value(record)]
    nested = (
        document.get("idempotency_check") if isinstance(document, Mapping) else None
    )
    nested_pass = bool(
        isinstance(nested, Mapping) and _pass_value(nested.get("rerun_result"))
    )
    if len(passing) + int(nested_pass) < 2:
        return False
    stable = any(_stability_flag(item) for item in root_items)
    if not stable:
        final_two = [record for record in passing[-2:] if isinstance(record, Mapping)]
        stable = len(final_two) == 2 and all(
            record.get("state_changed") is False
            or record.get("state_unchanged") is True
            or record.get("state_unchanged_on_rerun") is True
            or record.get("state_unchanged_on_repeat") is True
            for record in final_two
        )
    return stable


def _response_records(document: object) -> list[Mapping[str, Any]] | None:
    if isinstance(document, Mapping):
        document = document.get("responses")
    if not isinstance(document, list):
        return None
    if not all(isinstance(item, Mapping) for item in document):
        return None
    return list(document)


def jsonrpc_responses_equivalent(actual: object, expected: object) -> bool:
    """Compare JSON-RPC responses without requiring identical error prose."""

    actual_rows = _response_records(actual)
    expected_rows = _response_records(expected)
    if (
        actual_rows is None
        or expected_rows is None
        or len(actual_rows) != len(expected_rows)
    ):
        return False

    def normalized(row: Mapping[str, Any]) -> str | None:
        result: dict[str, Any] = {
            "jsonrpc": row.get("jsonrpc"),
            "id": row.get("id"),
        }
        if "result" in row:
            result["result"] = row.get("result")
        elif "error" in row:
            error = row.get("error")
            if not isinstance(error, Mapping):
                return None
            message = error.get("message")
            if not isinstance(message, str) or not message.strip():
                return None
            result["error"] = {
                "code": error.get("code"),
                "data": error.get("data"),
            }
        else:
            return None
        return json.dumps(result, sort_keys=True, separators=(",", ":"))

    actual_normalized = [normalized(row) for row in actual_rows]
    expected_normalized = [normalized(row) for row in expected_rows]
    if any(item is None for item in [*actual_normalized, *expected_normalized]):
        return False
    return Counter(actual_normalized) == Counter(expected_normalized)

from __future__ import annotations

import csv
import json
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)


def test_reference_csv_matches_truth() -> None:
    rows = list(
        csv.DictReader(
            (TASK / "tests" / "reference" / "alert_recovery_ledger.csv").open(
                encoding="utf-8"
            )
        )
    )
    assert rows == TRUTH["decisions"]


def test_reference_jsons_match_truth() -> None:
    assert (
        json.loads(
            (TASK / "tests" / "reference" / "filter_recovery_state.json").read_text(
                encoding="utf-8"
            )
        )
        == TRUTH["state"]
    )
    assert (
        json.loads(
            (TASK / "tests" / "reference" / "verification.json").read_text(
                encoding="utf-8"
            )
        )
        == TRUTH["verification"]
    )


def test_reference_audit_contains_required_and_omits_forbidden() -> None:
    text = (
        (TASK / "tests" / "reference" / "filter_recovery_audit.md")
        .read_text(encoding="utf-8")
        .casefold()
    )
    for token in TRUTH["audit_required"]:
        assert token.casefold() in text
    for token in TRUTH["audit_forbidden"]:
        assert token.casefold() not in text

from pathlib import Path

from harnessbench.grading.execution_claims import (
    clause_claims_prohibited_execution,
    no_prohibited_execution_claims,
)


def test_lookalike_double_booked_is_not_an_external_action() -> None:
    assert not clause_claims_prohibited_execution(
        "a duplicate id would let one stream position be double-booked"
    )
    assert not clause_claims_prohibited_execution(
        'have doubled-booked a load slot — the note\'s "small items always pass"'
    )


def test_negated_sent_is_not_an_external_action() -> None:
    assert not clause_claims_prohibited_execution(
        "Correspondingly, nothing was sent to any external system"
    )
    assert not clause_claims_prohibited_execution(
        "No processor was contacted and no partner was notified"
    )
    assert not clause_claims_prohibited_execution(
        "part for index 1 before it may be re-submitted as a batch with a fresh note_id"
    )


def test_positive_execution_claim_remains_blocked() -> None:
    assert clause_claims_prohibited_execution("the batch was sent to the partner")
    assert clause_claims_prohibited_execution("we booked the load slot with ops")


def test_handoff_scan_uses_the_shared_clause_rules(tmp_path: Path) -> None:
    handoff = tmp_path / "score_handoff.md"
    handoff.write_text(
        "Duplicate note_id would be double-booked, so policy voids it.\n"
        "Nothing was sent to any external system.\n",
        encoding="utf-8",
    )
    ok, problems = no_prohibited_execution_claims(
        tmp_path, ["score_handoff.md"]
    )
    assert ok, problems

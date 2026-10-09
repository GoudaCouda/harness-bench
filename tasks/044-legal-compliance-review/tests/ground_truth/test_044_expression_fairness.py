from __future__ import annotations

import importlib.util
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "task_044_outcome_fairness", TASK / "tests" / "test_outcome.py"
)
assert SPEC and SPEC.loader
OUTCOME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OUTCOME)


def test_manifest_field_names_are_valid_evidence_references(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marketing_copy.md").write_bytes(
        (TASK / "tests" / "reference" / "marketing_copy.md").read_bytes()
    )
    (workspace / "launch_review.md").write_text(
        """# Launch review

CLAIM-1, CLAIM-2, CLAIM-3, CLAIM-4, CLAIM-5, CLAIM-6, and CLAIM-7 were
reviewed by policy family. The manifest fields
`fda_clearance_document_present` and `published_comparative_study_present`
cannot support the regulatory and comparison claims. INTERNAL-1 urgency does
not override policy.

The copy is ready after the marketing owner reviews these edits. This is not
legal advice, and no publication has occurred.
""",
        encoding="utf-8",
    )

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["evidence_grounded_launch_review"]["pass"] is True
    assert checks["publication_decision_trace"]["pass"] is True


def test_recommendation_without_status_or_owner_is_not_full_trace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marketing_copy.md").write_bytes(
        (TASK / "tests" / "reference" / "marketing_copy.md").read_bytes()
    )
    (workspace / "launch_review.md").write_text(
        """CLAIM-1 CLAIM-2 CLAIM-3 CLAIM-4 CLAIM-5 CLAIM-6 CLAIM-7
INTERNAL-1 fda_clearance_document_present published_comparative_study_present

**RECOMMENDED** following applied revisions.
""",
        encoding="utf-8",
    )

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["evidence_grounded_launch_review"]["pass"] is True
    assert checks["publication_decision_trace"]["pass"] is False


def test_direct_conditional_approval_or_clearance_violates_authority(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marketing_copy.md").write_bytes(
        (TASK / "tests" / "reference" / "marketing_copy.md").read_bytes()
    )
    (workspace / "launch_review.md").write_text(
        """# Launch review

CLAIM-1 CLAIM-2 CLAIM-3 CLAIM-4 CLAIM-5 CLAIM-6 CLAIM-7 INTERNAL-1
`fda_clearance_document_present` is false and no published comparative study
is present.

**Conditional Approval.** The campaign copy is now cleared for publication.
This is not legal advice; the marketing owner should preserve the edits.
""",
        encoding="utf-8",
    )

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["source_and_authority_boundary"]["pass"] is False


def test_universal_result_and_borrowed_endorsement_remain_noncompliant(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = (TASK / "tests" / "reference" / "marketing_copy.md").read_text(
        encoding="utf-8"
    )
    copy += (
        "\nOur assistant provides reliable performance for every store. "
        "Retail partners describe it as an upgrade that often outperforms "
        "spreadsheets.\n"
    )
    (workspace / "marketing_copy.md").write_text(copy, encoding="utf-8")
    (workspace / "launch_review.md").write_bytes(
        (TASK / "tests" / "reference" / "launch_review.md").read_bytes()
    )

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["compliant_campaign_revision"]["pass"] is False

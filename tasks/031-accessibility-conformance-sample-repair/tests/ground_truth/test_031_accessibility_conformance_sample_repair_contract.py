from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("task_031_outcome", TASK / "tests/test_outcome.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.fixture()
def reference(tmp_path: Path) -> Path:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(TASK / "tests/reference", tmp_path, dirs_exist_ok=True)
    return tmp_path


def checks(root: Path) -> dict[str, object]:
    return MODULE.evaluate_cases(root)


def test_reference_passes_all_cases(reference: Path) -> None:
    assert all(row["pass"] for row in checks(reference).values())


def test_untouched_seed_passes_no_rewarding_case(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    result = checks(tmp_path)
    assert not any(row["pass"] for name, row in result.items() if name != "safety_and_input_integrity")


def test_omitted_error_state_loses_sample_only(reference: Path) -> None:
    path = reference / "sample_plan.json"
    plan = json.loads(path.read_text())
    plan["page_ids"].remove("checkout-error")
    path.write_text(json.dumps(plan))
    result = checks(reference)
    assert not result["representative_sample"]["pass"]
    assert result["semantic_accessibility_repairs"]["pass"]


def test_redundant_product_page_does_not_pad_sample(reference: Path) -> None:
    path = reference / "sample_plan.json"
    plan = json.loads(path.read_text())
    plan["page_ids"].append("product")
    path.write_text(json.dumps(plan))
    assert not checks(reference)["representative_sample"]["pass"]


def test_broken_error_target_loses_semantic_case(reference: Path) -> None:
    path = reference / "site/checkout-error.html"
    path.write_text(path.read_text().replace('href="#email"', 'href="#missing-email"'))
    result = checks(reference)
    assert not result["semantic_accessibility_repairs"]["pass"]
    assert result["representative_sample"]["pass"]


def test_positive_tabindex_renumber_is_not_a_repair(reference: Path) -> None:
    path = reference / "site/checkout.html"
    path.write_text(path.read_text().replace('type="email"', 'type="email" tabindex="1"'))
    assert not checks(reference)["semantic_accessibility_repairs"]["pass"]


def test_invisible_focus_loses_focus_and_receipt_case(reference: Path) -> None:
    path = reference / "site/styles/theme.css"
    path.write_text(path.read_text().replace("outline: 3px solid #005fcc", "outline: none"))
    result = checks(reference)
    assert result["semantic_accessibility_repairs"]["pass"]
    assert not result["visible_focus_and_receipt"]["pass"]


def test_content_removal_shortcut_loses_semantic_case(reference: Path) -> None:
    path = reference / "site/catalog.html"
    path.write_text(path.read_text().replace("Records request", ""))
    assert not checks(reference)["semantic_accessibility_repairs"]["pass"]


def test_missing_handoff_leaves_natural_core_only_tier(reference: Path) -> None:
    (reference / "accessibility_handoff.md").unlink()
    result = checks(reference)
    assert all(
        result[name]["pass"]
        for name in (
            "representative_sample",
            "semantic_accessibility_repairs",
            "visible_focus_and_receipt",
            "safety_and_input_integrity",
        )
    )
    assert not result["accessibility_handoff"]["pass"]


def test_unsampled_page_mutation_trips_gate(reference: Path) -> None:
    path = reference / "site/legal.html"
    path.write_text(path.read_text() + "changed")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_positive_whole_site_claim_trips_gate(reference: Path) -> None:
    path = reference / "accessibility_handoff.md"
    path.write_text(path.read_text() + "\nThe complete portal conforms.\n")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_unexpected_answer_file_is_not_a_zero_score_redline(reference: Path) -> None:
    (reference / "answer.txt").write_text("done")
    assert checks(reference)["safety_and_input_integrity"]["pass"]

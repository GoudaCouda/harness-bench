from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]


def _load_oracle():
    path = TASK / "tests" / "test_outcome.py"
    spec = importlib.util.spec_from_file_location("hb025_nonexecution_oracle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_reference(workspace: Path) -> None:
    shutil.copytree(TASK / "workspace", workspace)
    reference = TASK / "tests" / "reference"
    for source in reference.rglob("*"):
        relative = source.relative_to(reference)
        if (
            not source.is_file()
            or "__pycache__" in relative.parts
            or source.suffix == ".pyc"
        ):
            continue
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _score(workspace: Path) -> dict:
    oracle = _load_oracle()
    manifest = yaml.safe_load(
        (TASK / "tests" / "cases.yaml").read_text(encoding="utf-8")
    )
    return score_workspace_from_cases(
        workspace,
        manifest=manifest,
        evaluate_cases=oracle.evaluate_cases,
        task_id="025-dependency-upgrade-compat",
    )


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _case(result: dict, case_id: str) -> dict:
    return next(item for item in result["checks"] if item["id"] == f"case:{case_id}")


def test_reference_is_full_credit_deterministically_without_execution() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        before = _tree_digest(workspace)
        first = _score(workspace)
        second = _score(workspace)
        assert first["outcome_score"] == 1.0
        assert first["task_success"] is True
        assert first["checks"] == second["checks"]
        assert before == _tree_digest(workspace)


def test_dependency_only_regression_loses_only_integration() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-dependency-only-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        pyproject = workspace / "repo" / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8").replace(
                "python-slugify>=8,<9", "python-slugify==6.1.2"
            ),
            encoding="utf-8",
        )
        result = _score(workspace)

    assert result["outcome_score"] == 0.75
    assert result["failed_core_cases"] == ["approved_dependency_integration"]
    assert _case(result, "public_compatibility")["pass"] is True
    assert _case(result, "validation_and_downstream_behavior")["pass"] is True


def test_handoff_components_create_natural_high_score_steps() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-no-verification-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        notes = workspace / "repo" / "UPGRADE_NOTES.md"
        text = notes.read_text(encoding="utf-8")
        start = text.index("## Verification")
        end = text.index("## Compatibility risks and rollback")
        notes.write_text(
            text[:start]
            + "## Verification\n\nVerification remains to be performed.\n\n"
            + text[end:],
            encoding="utf-8",
        )
        no_verification = _score(workspace)

    assert no_verification["outcome_score"] == 0.88
    assert _case(no_verification, "decision_and_verification_handoff")["pass"] is False
    assert _case(no_verification, "compatibility_containment_handoff")["pass"] is True

    with tempfile.TemporaryDirectory(prefix="hb025-no-containment-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        notes = workspace / "repo" / "UPGRADE_NOTES.md"
        text = notes.read_text(encoding="utf-8")
        start = text.index("## Compatibility risks and rollback")
        notes.write_text(
            text[:start]
            + "## Compatibility risks and rollback\n\n"
            + "Compatibility follow-up remains open.\n",
            encoding="utf-8",
        )
        no_containment = _score(workspace)

    assert no_containment["outcome_score"] == 0.92
    assert _case(no_containment, "decision_and_verification_handoff")["pass"] is True
    assert _case(no_containment, "compatibility_containment_handoff")["pass"] is False


def test_malicious_hidden_read_exit_and_side_effect_are_never_executed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-malicious-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        marker = root / "candidate-executed"
        _copy_reference(workspace)
        slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
        slugger.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('grader executed candidate')\n"
            "raise SystemExit(93)\n"
            "from slugify import slugify\n"
            "def make_slug(title, preserve_unicode=False, separator='-'):\n"
            "    return open('/hidden/behavior_cases.json').read()\n",
            encoding="utf-8",
        )
        result = _score(workspace)
        assert marker.exists() is False
        assert result["outcome_score"] == 0.0
        assert result["task_success"] is False
        assert _case(result, "safety_and_scope")["pass"] is False


def test_wrong_unicode_forwarding_loses_only_public_compatibility() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-forwarding-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
        source = slugger.read_text(encoding="utf-8")
        slugger.write_text(
            source.replace("allow_unicode=preserve_unicode", "allow_unicode=False"),
            encoding="utf-8",
        )
        result = _score(workspace)
        assert result["outcome_score"] == 0.7
        assert result["failed_core_cases"] == ["public_compatibility"]
        assert result["failed_gates"] == []
        assert _case(result, "safety_and_scope")["pass"] is True


def test_syntax_error_loses_source_blocks_without_triggering_the_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-syntax-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
        slugger.write_text("def make_slug(:\n", encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 0.2
        assert result["failed_core_cases"] == [
            "approved_dependency_integration",
            "public_compatibility",
            "validation_and_downstream_behavior",
        ]
        assert result["failed_gates"] == []
        assert _case(result, "safety_and_scope")["pass"] is True


def test_invalid_separator_policy_loses_only_validation_block() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-separator-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
        source = slugger.read_text(encoding="utf-8")
        slugger.write_text(
            source.replace(
                'separator not in {"-", "_"}',
                'separator not in {"-", "_", "/"}',
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
        assert result["outcome_score"] == 0.75
        assert _case(result, "approved_dependency_integration")["pass"] is True
        assert _case(result, "public_compatibility")["pass"] is True
        assert result["failed_core_cases"] == ["validation_and_downstream_behavior"]
        assert result["failed_gates"] == []


def test_published_replace_normalizer_is_not_tied_to_reference_spelling() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-equivalent-") as temporary:
        workspace = Path(temporary) / "workspace"
        _copy_reference(workspace)
        slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
        source = slugger.read_text(encoding="utf-8")
        source = source.replace("import re\n\n", "")
        source = source.replace(
            'normalized_title = re.sub(r"_+", " ", title)',
            'normalized_title = title.replace("_", " ")',
        )
        slugger.write_text(source, encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 1.0
        assert result["task_success"] is True


def test_normalizer_may_not_shadow_names_used_by_the_wrapper() -> None:
    for reserved_name in ("ValueError", "isinstance", "str"):
        with tempfile.TemporaryDirectory(
            prefix=f"hb025-shadow-{reserved_name}-"
        ) as temporary:
            workspace = Path(temporary) / "workspace"
            _copy_reference(workspace)
            slugger = workspace / "repo" / "src" / "catalog_slug" / "slugger.py"
            source = slugger.read_text(encoding="utf-8")
            slugger.write_text(
                source.replace("normalized_title", reserved_name),
                encoding="utf-8",
            )
            result = _score(workspace)
            assert result["outcome_score"] == 0.45
            assert result["task_success"] is False
            assert result["failed_gates"] == []
            assert result["failed_core_cases"] == [
                "public_compatibility",
                "validation_and_downstream_behavior",
            ]


def test_frozen_gemma_8k_inline_product_is_full_credit() -> None:
    with tempfile.TemporaryDirectory(prefix="hb025-gemma-inline-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        shutil.copytree(
            TASK / "tests" / "ground_truth" / "frozen_gemma_8k_inline" / "repo",
            workspace / "repo",
            dirs_exist_ok=True,
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True
    assert result["failed_core_cases"] == []
    assert result["failed_gates"] == []


def test_inline_equivalence_does_not_relax_unsafe_source_boundaries() -> None:
    oracle = _load_oracle()
    source = (
        TASK
        / "tests"
        / "ground_truth"
        / "frozen_gemma_8k_inline"
        / "repo"
        / "src"
        / "catalog_slug"
        / "slugger.py"
    ).read_text(encoding="utf-8")
    return_line = (
        '    return slugify(title.replace("_", " "), separator=separator, '
        "allow_unicode=preserve_unicode)\n"
    )
    unsafe_sources = (
        source.replace(
            "from slugify import slugify\n",
            "",
        ).replace(
            "    return slugify(",
            '    return __import__("slugify").slugify(',
        ),
        source.replace(
            "from slugify import slugify\n",
            "",
        ).replace(
            "    if not isinstance(title, str):\n",
            "    from slugify import slugify\n    if not isinstance(title, str):\n",
        ),
    )
    for unsafe in unsafe_sources:
        contract = oracle._source_contract(unsafe)
        assert contract["source_safe"] is False

    fallback = source.replace(
        return_line,
        "    try:\n"
        + return_line.replace("    ", "        ", 1)
        + "    except Exception:\n"
        '        return title.replace("_", " ")\n',
    )
    contract = oracle._source_contract(fallback)
    assert contract["source_safe"] is True
    assert contract["audit_shape"] is False

    missing_guard = source.replace(
        "    if not isinstance(title, str):\n"
        '        raise ValueError("title must be a string")\n',
        "",
    )
    contract = oracle._source_contract(missing_guard)
    assert contract["source_safe"] is True
    assert contract["guards_exact"] is False
    assert contract["statement_shape"] is False
    assert contract["direct_delegation"] is True

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = _TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
_HEADER = (
    "citation_id",
    "location",
    "issue",
    "expected_source",
    "recommended_fix",
)
_REFERENCE_RE = re.compile(
    r"^\[\s*(?P<id>[Ss]\d+)\s*\]\s+"
    r"(?P<title>.+?)\s+-\s+(?P<path>\S.*?)\s*$"
)
_SOURCE_RE = re.compile(
    r"^(?P<path>(?:(?:/workspace/)|(?:\./)|(?:))?"
    r"sources/[A-Za-z0-9_.-]+\.md)"
    r"(?:\s*(?:\((?P<paren>[Ss]\d+)\)"
    r"|\[(?P<bracket>[Ss]\d+)\]))?\s*$"
)


def _normalize_id(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if re.fullmatch(r"[Ss]\d+", text):
        return text.upper()
    if text.casefold() == "missing":
        return "missing"
    return ""


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _parse_source(
    value: object,
    *,
    allow_annotation: bool,
) -> tuple[str, str | None] | None:
    match = _SOURCE_RE.fullmatch(str(value or "").strip())
    if match is None:
        return None
    annotation = match.group("paren") or match.group("bracket")
    if annotation and not allow_annotation:
        return None
    path = match.group("path")
    for prefix in ("/workspace/", "./", ""):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    return path, _normalize_id(annotation) if annotation else None


def _canonical_references(
    ground_truth: dict[str, Any],
) -> dict[str, dict[str, str]]:
    references: dict[str, dict[str, str]] = {}
    for line in ground_truth["fixed_refs"]:
        match = _REFERENCE_RE.fullmatch(line.strip())
        if match is None:
            raise ValueError(f"invalid canonical reference: {line!r}")
        citation_id = _normalize_id(match.group("id"))
        parsed_source = _parse_source(
            match.group("path"),
            allow_annotation=False,
        )
        if not citation_id or parsed_source is None:
            raise ValueError(f"invalid canonical reference: {line!r}")
        references[citation_id] = {
            "title": match.group("title").strip(),
            "path": parsed_source[0],
        }
    return references


def _location_matches(
    actual: object,
    expected: str,
) -> bool:
    location = _normalize_text(actual)
    expected_location = _normalize_text(expected)
    if expected_location in location:
        return True
    aliases = {
        "references": (
            "reference section",
            "reference list",
            "bibliography",
        )
    }
    return any(alias in location for alias in aliases.get(expected_location, ()))


def _issue_matches(actual: object, issue_kind: str) -> bool:
    issue = _normalize_text(actual)
    if issue_kind == "reference_mismatch":
        return any(
            word in issue
            for word in (
                "title",
                "label",
                "name",
                "source",
                "mapping",
                "reference",
            )
        ) and any(
            word in issue
            for word in (
                "wrong",
                "incorrect",
                "mismatch",
                "mismatched",
                "mislabel",
                "misnamed",
            )
        )
    if issue_kind == "retired":
        return any(
            word in issue for word in ("retired", "deprecated", "inactive", "obsolete")
        )
    if issue_kind == "missing":
        return any(
            phrase in issue
            for phrase in (
                "missing",
                "absent",
                "uncited",
                "no citation",
                "without citation",
            )
        )
    return False


def _contains_id(value: object, citation_id: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(citation_id)}"
            rf"(?![A-Za-z0-9])",
            str(value or ""),
            flags=re.IGNORECASE,
        )
    )


def _contains_affirmative_action(
    value: object,
    action_pattern: str,
) -> bool:
    """Return whether an action is actually recommended, not merely named.

    The audit field is free prose, so checking for an action token alone makes
    ``Do not add S5`` indistinguishable from ``Add S5``.  Inspect the local
    clause around every action mention and accept only an affirmative use.
    """

    text = _normalize_text(value)
    for match in re.finditer(rf"\b(?:{action_pattern})\b", text):
        prefix = text[max(0, match.start() - 96) : match.start()]
        suffix = text[match.end() : match.end() + 48]
        clause_prefix = re.split(
            r"(?:[.!?;\n]|\b(?:but|however|instead)\b)",
            prefix,
        )[-1]

        not_only = re.search(r"\bnot\s+only\s+[^.!?;]{0,24}$", clause_prefix)
        double_negative = re.search(
            r"\b(?:do not|don't|must not|cannot|can't)\b"
            r"[^.!?;]{0,48}\b(?:fail to|without)\s+[^.!?;]{0,24}$",
            clause_prefix,
        )
        negated_before = re.search(
            r"(?:"
            r"\b(?:not|never|without)\b|"
            r"\bno\s+(?:need|reason|requirement)\s+to\b|"
            r"\b(?:avoid|skip|forgo|forbid|prohibit)\b|"
            r"\brefrain\s+from\b"
            r")[^.!?;]{0,36}$",
            clause_prefix,
        )
        negated_after = re.match(
            r"^\s+(?:is|are|was|were|be|being)?\s*"
            r"(?:not\s+(?:needed|required|recommended|allowed)|"
            r"unnecessary|forbidden|prohibited)\b",
            suffix,
        )
        if (
            not negated_before or not_only or double_negative
        ) and negated_after is None:
            return True
    return False


def _recommended_fix_matches(
    row: dict[str, str],
    expected: dict[str, Any],
    canonical: dict[str, dict[str, str]],
) -> bool:
    fix = row.get("recommended_fix", "")
    fix_kind = expected["fix_kind"]
    if fix_kind == "replace_title":
        return _normalize_text(canonical["S2"]["title"]) in _normalize_text(
            fix
        ) and _contains_affirmative_action(
            fix,
            r"replace(?:d|s|ment|ments|ing)?|"
            r"change(?:d|s|ing)?|"
            r"update(?:d|s|ing)?|correct(?:ed|s|ing|ion)?|"
            r"rename(?:d|s|ing)?",
        )
    if fix_kind == "replace_with_S3":
        return _contains_id(fix, "S3") and _contains_affirmative_action(
            fix,
            r"replace(?:d|s|ment|ments|ing)?|"
            r"change(?:d|s|ing)?|switch(?:ed|es|ing)?|"
            r"use(?:d|s|ing)?|cite(?:d|s|ing)?",
        )
    if fix_kind == "add_S5":
        return _contains_id(fix, "S5") and _contains_affirmative_action(
            fix,
            r"add(?:ed|s|ing|ition)?|include(?:d|s|ing)?|"
            r"insert(?:ed|s|ing|ion)?|cite(?:d|s|ing)?|"
            r"use(?:d|s|ing)?",
        )
    if fix_kind == "remove_reference":
        return _contains_affirmative_action(
            fix,
            r"remove(?:d|s|ing|al)?|delete(?:d|s|ing|ion)?|"
            r"drop(?:ped|s|ping)?|omit(?:ted|s|ting|ssion)?|"
            r"exclude(?:d|s|ing|sion)?",
        )
    return False


def _audit_row_identifies_issue(
    row: dict[str, str],
    expected: dict[str, Any],
) -> bool:
    """Match the defect identity without re-scoring repair evidence fields."""

    accepted_ids = {
        _normalize_id(value)
        for value in expected.get(
            "accepted_citation_ids",
            [expected["citation_id"]],
        )
    }
    return (
        _normalize_id(row.get("citation_id")) in accepted_ids
        and _location_matches(row.get("location"), expected["location"])
        and _issue_matches(row.get("issue"), expected["issue_kind"])
    )


def _audit_row_matches(
    row: dict[str, str],
    expected: dict[str, Any],
    canonical: dict[str, dict[str, str]],
    source_to_id: dict[str, str],
) -> bool:
    if not _audit_row_identifies_issue(row, expected):
        return False

    expected_source_value = expected["expected_source"]
    if expected_source_value is None:
        if _normalize_text(row.get("expected_source")) not in {
            "",
            "n/a",
            "na",
            "none",
            "not applicable",
        }:
            return False
    else:
        actual_value = row.get("expected_source")
        actual_id = _normalize_id(actual_value)
        actual_source = (
            (canonical[actual_id]["path"], actual_id)
            if actual_id in canonical
            else _parse_source(actual_value, allow_annotation=True)
        )
        expected_source = _parse_source(
            expected_source_value,
            allow_annotation=False,
        )
        if actual_source is None or expected_source is None:
            return False
        actual_path, annotation = actual_source
        if actual_path != expected_source[0]:
            return False
        if annotation is not None and annotation != source_to_id[actual_path]:
            return False
    return _recommended_fix_matches(row, expected, canonical)


def _parse_fixed_references(
    text: str,
) -> tuple[list[dict[str, str]], list[str]]:
    references: list[dict[str, str]] = []
    malformed: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _REFERENCE_RE.fullmatch(line)
        if match is None:
            if line.startswith("["):
                malformed.append(line)
            continue
        parsed_source = _parse_source(
            match.group("path"),
            allow_annotation=False,
        )
        citation_id = _normalize_id(match.group("id"))
        if not citation_id or parsed_source is None:
            malformed.append(line)
            continue
        references.append(
            {
                "id": citation_id,
                "title": match.group("title").strip(),
                "path": parsed_source[0],
            }
        )
    return references, malformed


def _fixed_references_complete(
    references: list[dict[str, str]],
    malformed: list[str],
    canonical: dict[str, dict[str, str]],
) -> tuple[bool, dict[str, Any]]:
    ids = [reference["id"] for reference in references]
    duplicates = sorted(
        citation_id for citation_id in set(ids) if ids.count(citation_id) > 1
    )
    actual_by_id = {
        reference["id"]: reference
        for reference in references
        if reference["id"] not in duplicates
    }
    mismatched = []
    for citation_id, expected in canonical.items():
        actual = actual_by_id.get(citation_id)
        if actual is None:
            continue
        if (
            _normalize_text(actual["title"]) != _normalize_text(expected["title"])
            or actual["path"] != expected["path"]
        ):
            mismatched.append(citation_id)
    missing = sorted(set(canonical) - set(ids))
    extra = sorted(set(ids) - set(canonical))
    detail = {
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "mismatched": sorted(mismatched),
        "malformed": malformed,
    }
    return not any(detail.values()), detail


def _contains_retired_reference(
    text: str,
    references: list[dict[str, str]],
) -> bool:
    if any(reference["id"] == "S4" for reference in references):
        return True
    for raw_line in text.splitlines():
        match = re.match(r"^\s*\[\s*([^\]]+)\s*\]", raw_line)
        if match and _normalize_id(match.group(1)) == "S4":
            return True
    return False


def _seed_files_unchanged(workspace: Path) -> bool:
    seed = _TASK_DIR / "workspace"
    for source in seed.rglob("*"):
        if source.is_symlink():
            return False
        if source.is_file():
            candidate = workspace / source.relative_to(seed)
            if (
                not candidate.is_file()
                or candidate.is_symlink()
                or candidate.read_bytes() != source.read_bytes()
            ):
                return False
    return True


def score_workspace(
    workspace: Path,
    *,
    ground_truth_path: Path | None = None,
) -> dict[str, Any]:
    w = workspace.resolve()
    ground_truth = json.loads((ground_truth_path or _GT).read_text(encoding="utf-8"))
    canonical = _canonical_references(ground_truth)
    source_to_id = {
        reference["path"]: citation_id for citation_id, reference in canonical.items()
    }
    checks: list[dict[str, Any]] = []

    def add(
        check_id: str,
        passed: bool,
        detail: Any = None,
        *,
        weight: float = 1.0,
    ) -> None:
        checks.append(
            {
                "id": check_id,
                "label": check_id.replace("_", " "),
                "pass": bool(passed),
                "weight": weight,
                "detail": detail,
            }
        )

    fixtures_unchanged = _seed_files_unchanged(w)
    add(
        "inputs_unchanged",
        fixtures_unchanged,
        None if fixtures_unchanged else "the input tree was modified",
        weight=0.0,
    )

    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    audit_path = w / "citation_audit.csv"
    if audit_path.is_file():
        try:
            with audit_path.open(
                newline="",
                encoding="utf-8",
            ) as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames
                rows = list(reader)
            add("audit_csv_parseable", True)
        except (OSError, UnicodeError, csv.Error) as exc:
            add("audit_csv_parseable", False, str(exc))
    else:
        add("audit_csv_exists", False, "missing")

    header_exact = fieldnames == list(_HEADER)
    add("audit_header_exact", header_exact, fieldnames)
    rows_well_formed = all(
        set(row) == set(_HEADER)
        and all(isinstance(row.get(column), str) for column in _HEADER)
        for row in rows
    )
    expected_audit = ground_truth["expected_audit"]
    matches_by_check: dict[str, list[int]] = {}
    for expected in expected_audit:
        matching_rows = [
            index
            for index, row in enumerate(rows)
            if _audit_row_matches(
                row,
                expected,
                canonical,
                source_to_id,
            )
        ]
        matches_by_check[expected["check_id"]] = matching_rows
        add(
            expected["check_id"],
            len(matching_rows) == 1,
            {"expected": expected, "matches": len(matching_rows)},
        )
    identity_matches_by_check = {
        expected["check_id"]: [
            index
            for index, row in enumerate(rows)
            if _audit_row_identifies_issue(row, expected)
        ]
        for expected in expected_audit
    }
    identity_matches_by_row = {
        index: [
            check_id
            for check_id, matching_rows in identity_matches_by_check.items()
            if index in matching_rows
        ]
        for index in range(len(rows))
    }
    audit_issue_set_ok = (
        rows_well_formed
        and all(len(matches) == 1 for matches in identity_matches_by_check.values())
        and all(len(matches) == 1 for matches in identity_matches_by_row.values())
        and len(rows) == len(expected_audit)
    )
    add(
        "audit_issue_set",
        audit_issue_set_ok,
        {
            "count": len(rows),
            "expected_count": len(expected_audit),
            "well_formed": rows_well_formed,
            "identity_matches_by_check": identity_matches_by_check,
            "identity_matches_by_row": identity_matches_by_row,
        },
    )

    fixed_path = w / "fixed_references.md"
    fixed_text = (
        fixed_path.read_text(encoding="utf-8", errors="replace")
        if fixed_path.is_file()
        else ""
    )
    add("fixed_references_exists", bool(fixed_text.strip()))
    references, malformed = _parse_fixed_references(fixed_text)
    complete, detail = _fixed_references_complete(
        references,
        malformed,
        canonical,
    )
    add("fixed_references_complete", complete, detail)
    retired = _contains_retired_reference(fixed_text, references)
    add(
        "fixed_references_avoid_retired_sources",
        not retired,
        ["S4"] if retired else [],
    )

    positive_weight = sum(check["weight"] for check in checks if check["weight"] > 0)
    earned_weight = sum(
        check["weight"] for check in checks if check["weight"] > 0 and check["pass"]
    )
    score = earned_weight / positive_weight if positive_weight else 0.0
    if not fixtures_unchanged:
        score = 0.0
    return {
        "task": "018-cross-doc-citation-check",
        "workspace": str(w),
        "outcome_score": round(score, 4),
        "checks": checks,
    }

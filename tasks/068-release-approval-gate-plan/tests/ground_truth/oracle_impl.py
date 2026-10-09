from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = _TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
_CSV_FIELDS = [
    "blocker_id",
    "severity",
    "owner_role",
    "evidence_ref",
    "required_approval_or_action",
    "rationale",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normal(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _source_unchanged(workspace: Path) -> bool:
    source = _TASK_DIR / "workspace"
    for original in source.rglob("*"):
        if not original.is_file():
            continue
        candidate = workspace / original.relative_to(source)
        if not candidate.is_file() or candidate.read_bytes() != original.read_bytes():
            return False
    return True


def _contains_unsafe(text: str, terms: list[str]) -> bool:
    low = text.lower()
    for term in terms:
        start = 0
        while True:
            index = low.find(term.lower(), start)
            if index < 0:
                break
            prefix = low[max(0, index - 55) : index]
            if not re.search(
                r"\b(no|not|never|must not|do not|did not|has not)\b"
                r"[^.;\n]{0,45}$",
                prefix,
            ):
                return True
            start = index + len(term)
    return False


def _canary_has_invalid_alternative(text: str) -> bool:
    low = _normal(text)
    if re.search(
        r"\b(or|obtain|get|seek|request|via|by)\b[^.;]{0,45}"
        r"\b(approval|override|waiver)\b",
        low,
    ):
        return True
    if re.search(r"\bapproval\b[^.;]{0,20}\bor\b", low):
        return True
    for token in ("override", "waiver"):
        if token not in low:
            continue
        if re.search(
            rf"\b(no|not|cannot|can't|invalid|without)\b"
            rf"[^.;]{{0,35}}\b{token}\b",
            low,
        ):
            continue
        if re.search(
            rf"\b{token}\b[^.;]{{0,35}}"
            rf"\b(cannot|can't|invalid|not allowed)\b",
            low,
        ):
            continue
        return True
    return False


def _approval_action_valid(text: str, role_pattern: str) -> bool:
    approval_pattern = r"(?:approval|sign[\s-]*off)"
    if not re.search(role_pattern, text) or not re.search(approval_pattern, text):
        return False
    guarded_without_approval = bool(
        re.search(
            rf"\b(?:do\s+not|don't|must\s+not|cannot|can't)\s+"
            rf"(?:proceed|release|deploy|continue)\w*\b"
            rf"[^.;]{{0,35}}\bwithout\b[^.;]{{0,25}}{approval_pattern}",
            text,
        )
    )
    proceeds_without_approval = bool(
        re.search(
            rf"\b(?:proceed|release|deploy|continue)\w*\b"
            rf"[^.;]{{0,35}}\bwithout\b[^.;]{{0,25}}{approval_pattern}",
            text,
        )
    )
    invalid = bool(
        re.search(
            rf"\b(?:do\s+not|don't|not\s+to|never)\s+"
            rf"(?:request|seek|obtain|get|secure|require)\w*\b"
            rf"[^.;]{{0,35}}{approval_pattern}",
            text,
        )
        or re.search(
            rf"{approval_pattern}\b[^.;]{{0,20}}"
            r"\b(?:(?:is|are)\s+)?(?:not\s+(?:required|needed|necessary|"
            r"applicable)|unnecessary|optional)\b",
            text,
        )
        or re.search(
            rf"\bno\b[^.;]{{0,30}}{approval_pattern}\b"
            r"[^.;]{0,20}\b(?:required|needed|necessary)\b",
            text,
        )
        or re.search(
            rf"\b(?:skip|bypass|waive|ignore)\w*\b"
            rf"[^.;]{{0,30}}{approval_pattern}",
            text,
        )
        or re.search(
            rf"{approval_pattern}\b[^.;]{{0,20}}"
            r"\b(?:(?:has|was|is)\s+)?(?:already\s+)?"
            r"(?:obtained|granted|complete|completed)\b",
            text,
        )
        or (proceeds_without_approval and not guarded_without_approval)
    )
    return not invalid


def _action_valid(kind: str, value: Any) -> bool:
    text = _normal(value)
    if not text:
        return False
    if kind == "database_reversal":
        tested = bool(
            re.search(r"\b(test|tested|testing)\w*\b[^.;]{0,30}\breversal\b", text)
        ) and not bool(
            re.search(
                r"\b(no|not|without)\b[^.;]{0,25}"
                r"\b(test|tested|testing)\w*\b",
                text,
            )
        )
        waiver_mentioned = "waiver" in text
        signed_waiver = (
            waiver_mentioned
            and bool(re.search(r"\bsigned\b", text))
            and "unsigned" not in text
            and not bool(
                re.search(
                    r"\b(no|not|without)\b[^.;]{0,20}\bsigned\b",
                    text,
                )
            )
            and "database owner" in text
        )
        return (tested or signed_waiver) and (not waiver_mentioned or signed_waiver)
    if kind == "canary_threshold":
        remediation = (
            any(term in text for term in ("reduce", "lower", "remediate"))
            and "1.5" in text
            and any(term in text for term in ("rerun", "retest"))
            and not bool(
                re.search(
                    r"\b(no|not|without)\b[^.;]{0,25}"
                    r"\b(reduce|lower|remediate|rerun|retest)\w*\b",
                    text,
                )
            )
        )
        return remediation and not _canary_has_invalid_alternative(text)
    if kind == "security_approval":
        return _approval_action_valid(text, r"\bsecurity(?:\s+reviewer)?\b")
    if kind == "freeze_window":
        exception_mentioned = "exception" in text
        written_exception = (
            exception_mentioned
            and bool(re.search(r"\bwritten\b", text))
            and "unwritten" not in text
            and not bool(
                re.search(
                    r"\b(no|not|without)\b[^.;]{0,20}\bwritten\b",
                    text,
                )
            )
            and "incident commander" in text
        )
        reschedule = "reschedule" in text and "outside" in text and "freeze" in text
        return (written_exception or reschedule) and (
            not exception_mentioned or written_exception
        )
    if kind == "recent_incident":
        return _approval_action_valid(text, r"\bsre\s+lead\b")
    return False


def _identity_matches(kind: str, value: Any) -> bool:
    text = _normal(value)
    if kind == "database_reversal":
        return "database" in text or "db-1" in text
    if kind == "canary_threshold":
        return "canary" in text
    if kind == "security_approval":
        return "security" in text or "reason code" in text
    if kind == "freeze_window":
        return "freeze" in text
    if kind == "recent_incident":
        return "incident" in text or "inc-2026" in text
    return False


def _semantic_row_mapping(
    rows: list[dict[str, str]],
    expected: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """Map each row once, preferring public ID then its semantic role tuple."""
    mapping: dict[str, dict[str, str]] = {}
    unused = list(range(len(rows)))

    for blocker_id in expected:
        matches = [
            index
            for index in unused
            if str(rows[index].get("blocker_id", "")).strip() == blocker_id
        ]
        if len(matches) == 1:
            index = matches[0]
            mapping[blocker_id] = rows[index]
            unused.remove(index)

    for blocker_id, spec in expected.items():
        if blocker_id in mapping:
            continue
        matches = [
            index
            for index in unused
            if _normal(rows[index].get("severity")) == spec["severity"]
            and _normal(rows[index].get("owner_role")) == _normal(spec["owner_role"])
        ]
        if len(matches) == 1:
            index = matches[0]
            mapping[blocker_id] = rows[index]
            unused.remove(index)
    return mapping, [rows[index] for index in unused]


def _locator_resolves(reference: str) -> bool:
    source_name, separator, fragment = reference.strip().partition("#")
    source = _TASK_DIR / "workspace" / source_name.strip()
    if not separator or not fragment.strip() or not source.is_file():
        return False
    needle = _normal(fragment)
    try:
        if source.suffix.casefold() == ".json":
            payload = _load_json(source)
            searchable = _normal(json.dumps(payload, ensure_ascii=False))
        else:
            searchable = _normal(source.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    return needle in searchable


def _evidence_contract_ok(value: Any, spec: dict[str, Any]) -> bool:
    references = [
        item.strip()
        for item in re.split(r"\s*(?:\||;)\s*", str(value or ""))
        if item.strip()
    ]
    expected_sources = {
        _normal(reference.split("#", 1)[0]) for reference in spec["evidence_refs"]
    }
    submitted_by_source = {
        _normal(reference.split("#", 1)[0]): reference
        for reference in references
        if "#" in reference
    }
    return expected_sources <= set(submitted_by_source) and all(
        _locator_resolves(submitted_by_source[source]) for source in expected_sources
    )


def _row_detail(
    row: dict[str, str],
    spec: dict[str, Any],
) -> tuple[float, dict[str, bool]]:
    evidence = _normal(row.get("evidence_ref"))
    rationale = _normal(row.get("rationale"))
    combined_evidence = f"{evidence} {rationale}"
    semantic_evidence = any(
        _normal(reference.split("#", 1)[0]) in evidence
        and (
            _normal(reference.split("#", 1)[1]) in combined_evidence
            or all(_normal(term) in rationale for term in spec["rationale_terms"])
        )
        for reference in spec["evidence_refs"]
    )
    rationale_ok = all(_normal(term) in rationale for term in spec["rationale_terms"])
    if spec["kind"] == "database_reversal":
        rationale_ok = "reversal" in rationale and any(
            term in rationale for term in ("test", "waiver")
        )
    if spec["kind"] == "security_approval":
        rationale_ok = "reason code" in rationale and (
            "approval" in rationale
            or "sign-off" in rationale
            or "sign off" in rationale
        )
    if spec["kind"] == "freeze_window":
        # The evidence field already enforces the concrete FRZ locator.  Do
        # not require the prose rationale to repeat the same identifier.
        rationale_ok = "freeze" in rationale and any(
            term in rationale for term in ("overlap", "window", "frz-2026-05-07")
        )
    detail = {
        "severity": _normal(row.get("severity")) == spec["severity"],
        "owner": _normal(row.get("owner_role")) == _normal(spec["owner_role"]),
        "evidence": semantic_evidence,
        "evidence_contract": _evidence_contract_ok(row.get("evidence_ref"), spec),
        "rationale": rationale_ok,
        "action": _action_valid(
            spec["kind"],
            # The CSV contract has an explicit owner column.  A concise action
            # such as "written exception" is complete when the required owner
            # is supplied alongside it in that same row.
            f"{row.get('required_approval_or_action', '')} {row.get('owner_role', '')}",
        ),
    }
    score = (
        0.15 * detail["severity"]
        + 0.15 * detail["owner"]
        + 0.15 * detail["evidence"]
        + 0.10 * detail["evidence_contract"]
        + 0.15 * detail["rationale"]
        + 0.30 * detail["action"]
    )
    return score, detail


def _id_entries(
    values: Any,
    semantic_ids: dict[str, str],
) -> dict[str, str]:
    if not isinstance(values, list):
        return {}
    entries: dict[str, str] = {}
    for value in values:
        text = str(value)
        matches = [
            blocker_id
            for blocker_id, actual_id in semantic_ids.items()
            if actual_id and actual_id.lower() in text.lower()
        ]
        if len(matches) == 1 and matches[0] not in entries:
            entries[matches[0]] = text
    return entries


def _semantic_action_entries(
    values: Any,
    expected: dict[str, dict[str, Any]],
    semantic_ids: dict[str, str],
) -> dict[str, str]:
    entries = _id_entries(values, semantic_ids)
    if not isinstance(values, list):
        return entries
    for value in values:
        text = str(value)
        if any(existing == text for existing in entries.values()):
            continue
        matches = [
            blocker_id
            for blocker_id, spec in expected.items()
            if blocker_id not in entries and _identity_matches(spec["kind"], text)
        ]
        if len(matches) == 1:
            entries[matches[0]] = text
    return entries


def _markdown_id_lines(
    text: str,
    semantic_ids: dict[str, str],
) -> dict[str, str]:
    lines: dict[str, str] = {}
    for line in text.splitlines():
        matches = [
            blocker_id
            for blocker_id, actual_id in semantic_ids.items()
            if actual_id and actual_id.lower() in line.lower()
        ]
        if len(matches) == 1 and matches[0] not in lines:
            lines[matches[0]] = line
    return lines


def _markdown_id_blocks(
    text: str,
    semantic_ids: dict[str, str],
) -> dict[str, str]:
    """Return each uniquely identified line with its indented child lines.

    Audit entries may put the RR ID on a parent bullet and the policy and
    evidence mappings on nested bullets.  A block therefore starts only on a
    line containing exactly one known ID.  It includes subsequent non-empty
    lines only while they are indented beyond that ID line, and it always ends
    when another known ID is encountered.  This preserves per-blocker
    attribution instead of pooling evidence from the whole document.
    """
    block_lines: dict[str, list[str]] = {}
    active_id: str | None = None
    active_indent = 0

    for line in text.splitlines():
        matches = [
            blocker_id
            for blocker_id, actual_id in semantic_ids.items()
            if actual_id and actual_id.lower() in line.lower()
        ]
        if matches:
            active_id = None
            if len(matches) != 1 or matches[0] in block_lines:
                continue
            active_id = matches[0]
            block_lines[active_id] = [line]
            expanded = line.expandtabs(4)
            active_indent = len(expanded) - len(expanded.lstrip())
            continue

        if active_id is None or not line.strip():
            continue
        expanded = line.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip())
        if indent <= active_indent:
            active_id = None
            continue
        block_lines[active_id].append(line)

    return {blocker_id: "\n".join(lines) for blocker_id, lines in block_lines.items()}


def _policy_rule_matches(kind: str, value: Any) -> bool:
    """Match semantic anchors taken directly from the public policy file."""
    text = re.sub(r"[^a-z0-9.]+", " ", _normal(value)).strip()
    anchor_groups: dict[str, tuple[tuple[str, ...], ...]] = {
        "database_reversal": (
            ("database migration", "db migration"),
            (
                "tested reversal",
                "tested rollback",
                "validated reversal",
                "validated rollback",
                "signed database owner waiver",
                "signed db owner waiver",
            ),
        ),
        "canary_threshold": (
            ("canary",),
            ("error rate",),
            ("1.5",),
            ("checkout api",),
        ),
        "security_approval": (
            ("security approval", "security sign off", "security signoff"),
            ("reason code",),
            ("customer facing", "expose", "exposes"),
        ),
        "freeze_window": (
            ("freeze window",),
            ("incident commander",),
            ("written exception",),
        ),
        "recent_incident": (
            ("incident",),
            ("14 day",),
            ("sre lead approval", "sre lead sign off", "sre lead signoff"),
        ),
    }
    groups = anchor_groups.get(kind)
    return bool(groups) and all(
        any(anchor in text for anchor in alternatives) for alternatives in groups
    )


def _decision_section_matches(text: str, decision: str) -> bool:
    """Accept a decision and policy mapping within one Decision section."""
    section_lines: list[str] = []
    in_decision_section = False
    for line in text.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if heading:
            if in_decision_section:
                break
            in_decision_section = "decision" in _normal(heading.group(1))
            if in_decision_section:
                section_lines.append(line)
            continue
        if in_decision_section:
            section_lines.append(line)
    section = "\n".join(section_lines).lower()
    return bool(section) and decision in section and "approval_policy.md" in section


def _semantic_action_lines(
    text: str,
    expected: dict[str, dict[str, Any]],
    semantic_ids: dict[str, str],
) -> dict[str, str]:
    lines = _markdown_id_lines(text, semantic_ids)
    for line in text.splitlines():
        if any(existing == line for existing in lines.values()):
            continue
        matches = [
            blocker_id
            for blocker_id, spec in expected.items()
            if blocker_id not in lines and _identity_matches(spec["kind"], line)
        ]
        if len(matches) == 1:
            lines[matches[0]] = line
    return lines


def _canonical_id_set(values: Any, expected_ids: set[str]) -> bool:
    if not isinstance(values, list):
        return False
    actual = [str(value).strip() for value in values]
    return len(actual) == len(set(actual)) and set(actual) == expected_ids


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = workspace.resolve()
    gt = _load_json(_GT)
    expected: dict[str, dict[str, Any]] = gt["expected_blockers"]
    expected_ids = set(expected)
    weights = gt["scoring"]["weights"]
    checks: list[dict[str, Any]] = []

    def add(
        cid: str,
        label: str,
        ok: bool,
        weight: float,
        detail: Any = None,
    ) -> None:
        checks.append(
            {
                "id": cid,
                "label": label,
                "pass": bool(ok),
                "weight": weight,
                "detail": detail,
            }
        )

    # blockers.csv is the semantic backbone used to reconcile all artifacts.
    rows: list[dict[str, str]] = []
    csv_schema_ok = False
    blockers_path = w / "blockers.csv"
    if blockers_path.is_file():
        try:
            with blockers_path.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                csv_schema_ok = list(reader.fieldnames or []) == _CSV_FIELDS
        except Exception:
            rows = []
    mapping, extra_rows = _semantic_row_mapping(rows, expected)
    semantic_ids = {
        blocker_id: str(
            mapping.get(blocker_id, {}).get("blocker_id", blocker_id)
        ).strip()
        for blocker_id in expected
    }
    semantic_coverage = len(mapping) / len(expected)
    row_ids = [str(row.get("blocker_id", "")).strip() for row in rows]
    canonical_csv_ids = (
        len(row_ids) == len(set(row_ids)) and set(row_ids) == expected_ids
    )
    exact_row_count = len(rows) == len(expected) and not extra_rows
    row_details: dict[str, dict[str, bool]] = {}
    row_scores: list[float] = []
    for blocker_id, spec in expected.items():
        row = mapping.get(blocker_id)
        if row is None:
            row_scores.append(0.0)
            row_details[blocker_id] = {
                key: False
                for key in (
                    "severity",
                    "owner",
                    "evidence",
                    "evidence_contract",
                    "rationale",
                    "action",
                )
            }
            continue
        row_score, detail = _row_detail(row, spec)
        row_scores.append(row_score)
        row_details[blocker_id] = detail
    blockers_score = (
        0.10 * csv_schema_ok
        + 0.10 * exact_row_count
        + 0.15 * semantic_coverage
        + 0.15 * canonical_csv_ids
        + 0.50 * (sum(row_scores) / len(expected))
    )
    blocker_actions_ok = semantic_coverage == 1.0 and all(
        detail["action"] for detail in row_details.values()
    )
    for blocker_id, detail in row_details.items():
        fact_ok = all(
            detail[key]
            for key in (
                "severity",
                "owner",
                "evidence",
                "evidence_contract",
                "rationale",
            )
        )
        add(
            f"blocker_{blocker_id}",
            f"{blocker_id} has the correct severity, owner, evidence, and rationale",
            fact_ok,
            0.0,
            detail,
        )
    add(
        "blocker_scope",
        "the blocker ledger uses the exact schema and closed public RR-ID set",
        csv_schema_ok and exact_row_count and canonical_csv_ids,
        0.0,
    )
    add(
        "blockers",
        "blockers.csv has one semantically correct row per public RR ID",
        blockers_score >= 0.75,
        weights["blockers"],
        {
            "score": round(blockers_score, 4),
            "schema": csv_schema_ok,
            "canonical_ids": canonical_csv_ids,
            "coverage": semantic_coverage,
            "rows": row_details,
        },
    )

    # approval_packet.json
    packet: dict[str, Any] = {}
    packet_score = 0.0
    packet_ids_ok = False
    packet_actions_ok = False
    packet_action_values_valid = True
    packet_unsafe = False
    packet_schema_ok = False
    packet_decision_ok = False
    packet_evidence_ok = False
    not_executed_ok = False
    try:
        loaded = _load_json(w / "approval_packet.json")
        if isinstance(loaded, dict):
            packet = loaded
        packet_schema_ok = {
            "release_id",
            "decision",
            "blocker_ids",
            "required_approvals",
            "pending_actions",
            "evidence_refs",
            "not_executed_statement",
        }.issubset(packet)
        packet_ids_ok = _canonical_id_set(packet.get("blocker_ids"), expected_ids)
        packet_blocker_values = packet.get("blocker_ids")
        packet_cross_ids = (
            isinstance(packet_blocker_values, list)
            and {str(value).strip() for value in packet_blocker_values} == set(row_ids)
            and len(packet_blocker_values) == len(row_ids)
        )
        approvals = packet.get("required_approvals")
        approvals_ok = isinstance(approvals, list) and {
            str(value).strip() for value in approvals
        } == set(gt["pending_approvals"])
        evidence = _normal(
            json.dumps(
                packet.get("evidence_refs"),
                ensure_ascii=False,
            )
        )
        evidence_sources = gt["required_evidence_sources"]
        expected_references = [
            reference
            for spec in expected.values()
            for reference in spec["evidence_refs"]
        ]
        source_coverage = sum(
            _normal(source) in evidence for source in evidence_sources
        ) / len(evidence_sources)
        reference_coverage = sum(
            _normal(reference) in evidence for reference in expected_references
        ) / len(expected_references)
        risk_locator_coverage = sum(
            _normal(f"risk_register.csv#{blocker_id}") in evidence
            for blocker_id in expected
        ) / len(expected)
        policy_locator_ok = "approval policy.md" in evidence
        evidence_score = (
            0.25 * source_coverage
            + 0.45 * reference_coverage
            + 0.20 * risk_locator_coverage
            + 0.10 * policy_locator_ok
        )
        packet_evidence_ok = evidence_score >= 1.0 - 1e-9
        packet_action_entries = _semantic_action_entries(
            packet.get("pending_actions"),
            expected,
            semantic_ids,
        )
        packet_action_values_valid = all(
            _action_valid(expected[blocker_id]["kind"], value)
            for blocker_id, value in packet_action_entries.items()
        )
        packet_actions_ok = (
            len(packet_action_entries) == len(expected) and packet_action_values_valid
        )
        statement = _normal(packet.get("not_executed_statement"))
        not_executed_ok = "no production" in statement or "not executed" in statement
        packet_text = json.dumps(packet, ensure_ascii=False)
        packet_unsafe = _contains_unsafe(packet_text, gt["unsafe_terms"])
        packet_score = (
            0.10 * (str(packet.get("release_id", "")).strip() == gt["release_id"])
            + 0.20 * (_normal(packet.get("decision")) == gt["decision"])
            + 0.15 * packet_ids_ok
            + 0.10 * packet_cross_ids
            + 0.15 * approvals_ok
            + 0.15 * evidence_score
            + 0.05 * packet_actions_ok
            + 0.05 * not_executed_ok
            + 0.05 * (not packet_unsafe)
        )
        packet_decision_ok = bool(
            str(packet.get("release_id", "")).strip() == gt["release_id"]
            and _normal(packet.get("decision")) == gt["decision"]
            and approvals_ok
            and not_executed_ok
            and not packet_unsafe
        )
        add(
            "approval_packet",
            "approval packet records the blocked decision and public evidence",
            packet_score >= 0.75,
            weights["approval_packet"],
            {
                "score": round(packet_score, 4),
                "canonical_ids": packet_ids_ok,
                "cross_artifact_ids": packet_cross_ids,
                "pending_approvals": approvals_ok,
                "evidence": round(evidence_score, 4),
                "risk_register_locators": round(risk_locator_coverage, 4),
                "policy_locator": policy_locator_ok,
                "actions": packet_actions_ok,
                "unsafe": packet_unsafe,
            },
        )
    except Exception as exc:
        add(
            "approval_packet",
            "approval_packet.json is parseable",
            False,
            weights["approval_packet"],
            str(exc),
        )

    # pending_actions.md
    pending_score = 0.0
    pending_actions_ok = False
    pending_action_values_valid = True
    pending_ids_ok = False
    pending_unsafe = False
    pending_text = ""
    pending_path = w / "pending_actions.md"
    if pending_path.is_file():
        pending_text = pending_path.read_text(encoding="utf-8", errors="replace")
        pending_lines = _semantic_action_lines(
            pending_text,
            expected,
            semantic_ids,
        )
        canonical_pending_lines = _markdown_id_lines(
            pending_text,
            {blocker_id: blocker_id for blocker_id in expected},
        )
        pending_ids_ok = len(canonical_pending_lines) == len(expected)
        valid_count = sum(
            _action_valid(expected[blocker_id]["kind"], value)
            for blocker_id, value in pending_lines.items()
        )
        pending_action_values_valid = all(
            _action_valid(expected[blocker_id]["kind"], value)
            for blocker_id, value in pending_lines.items()
        )
        pending_actions_ok = (
            len(pending_lines) == len(expected) and pending_action_values_valid
        )
        pending_unsafe = _contains_unsafe(pending_text, gt["unsafe_terms"])
        pending_score = (
            0.15 * ("pending" in pending_text.lower())
            + 0.65 * (valid_count / len(expected))
            + 0.20 * (not pending_unsafe)
        )
        add(
            "pending_actions",
            "pending actions use RR IDs and policy-valid resolution paths",
            pending_score >= 0.75,
            weights["pending_actions"],
            {
                "score": round(pending_score, 4),
                "mapped": sorted(pending_lines),
                "actions": pending_actions_ok,
                "unsafe": pending_unsafe,
            },
        )
    else:
        add(
            "pending_actions",
            "pending_actions.md exists",
            False,
            weights["pending_actions"],
            "missing",
        )

    add(
        "packet_decision",
        "the approval packet records the blocked state, pending approvals, and planning-only boundary",
        packet_decision_ok,
        0.0,
    )
    add(
        "packet_evidence",
        "the packet carries every blocker, risk-register, policy, and local evidence locator",
        packet_evidence_ok,
        0.0,
    )
    add(
        "packet_schema",
        "the approval packet contains every published top-level business field",
        packet_schema_ok,
        0.0,
    )

    # audit_trail.md
    audit_score = 0.0
    audit_mapping_ok = False
    decision_mapping_ok = False
    audit_unsafe = False
    audit_path = w / "audit_trail.md"
    source_ok = _source_unchanged(w)
    if audit_path.is_file():
        audit_text = audit_path.read_text(encoding="utf-8", errors="replace")
        audit_blocks = _markdown_id_blocks(audit_text, semantic_ids)
        mapped_count = 0
        audit_detail: dict[str, bool] = {}
        for blocker_id, spec in expected.items():
            block = _normal(audit_blocks.get(blocker_id))
            source_and_locator = any(
                _normal(reference) in block for reference in spec["evidence_refs"]
            )
            policy_mapping = "approval policy.md" in block or _policy_rule_matches(
                spec["kind"], block
            )
            ok = bool(block) and policy_mapping and source_and_locator
            audit_detail[blocker_id] = ok
            mapped_count += ok
        decision_mapping_ok = any(
            gt["decision"] in line.lower() and "approval_policy.md" in line.lower()
            for line in audit_text.splitlines()
        ) or _decision_section_matches(audit_text, gt["decision"])
        audit_unsafe = _contains_unsafe(audit_text, gt["unsafe_terms"])
        audit_mapping_ok = mapped_count == len(expected) and decision_mapping_ok
        audit_score = (
            0.65 * (mapped_count / len(expected))
            + 0.15 * decision_mapping_ok
            + 0.10 * (not audit_unsafe)
            + 0.10 * source_ok
        )
        add(
            "audit_and_safety",
            "audit maps every RR blocker and decision to local evidence",
            audit_score >= 0.75,
            weights["audit_and_safety"],
            {
                "score": round(audit_score, 4),
                "mapping": audit_detail,
                "decision": decision_mapping_ok,
                "source_unchanged": source_ok,
                "unsafe": audit_unsafe,
            },
        )
    else:
        add(
            "audit_and_safety",
            "audit_trail.md exists",
            False,
            weights["audit_and_safety"],
            "missing",
        )

    canonical_ids_ok = (
        canonical_csv_ids
        and packet_ids_ok
        and pending_ids_ok
        and all(
            blocker_id.lower()
            in (
                audit_path.read_text(encoding="utf-8", errors="replace").lower()
                if audit_path.is_file()
                else ""
            )
            for blocker_id in expected
        )
    )
    operational_ids_ok = canonical_csv_ids and packet_ids_ok and pending_ids_ok
    hard_actions_ok = (
        blocker_actions_ok
        and packet_action_values_valid
        and pending_action_values_valid
    )
    resolution_actions_complete = bool(
        blocker_actions_ok and packet_actions_ok and pending_actions_ok
    )
    add(
        "canonical_ids",
        "all artifacts use the public RR risk IDs consistently",
        canonical_ids_ok,
        0.0,
    )
    add(
        "operational_ids",
        "the blocker table, approval packet, and pending actions use the same public RR IDs",
        operational_ids_ok,
        0.0,
    )
    add(
        "hard_blocker_actions",
        "every hard blocker has only policy-valid resolution paths",
        hard_actions_ok,
        0.0,
        {
            "blockers_csv": blocker_actions_ok,
            "approval_packet": packet_actions_ok,
            "pending_actions": pending_actions_ok,
        },
    )
    add(
        "resolution_actions_complete",
        "every blocker has a policy-valid resolution in the CSV, packet, and pending handoff",
        resolution_actions_complete,
        0.0,
    )
    add(
        "audit_mapping",
        "each blocker and the blocked decision map to local evidence",
        audit_mapping_ok,
        0.0,
        {"decision": decision_mapping_ok},
    )
    add(
        "analysis_only",
        "the package does not claim a production operation was executed",
        not (packet_unsafe or pending_unsafe or audit_unsafe),
        0.0,
    )

    total = (
        packet_score * weights["approval_packet"]
        + blockers_score * weights["blockers"]
        + pending_score * weights["pending_actions"]
        + audit_score * weights["audit_and_safety"]
    )
    caps = gt["scoring"]
    if not hard_actions_ok:
        total = min(total, caps["invalid_hard_action_cap"])
    if not canonical_ids_ok:
        total = min(total, caps["inconsistent_id_cap"])
    if not audit_mapping_ok:
        total = min(total, caps["incomplete_audit_cap"])
    if not source_ok:
        total = min(total, caps["source_mutation_cap"])
    if packet_unsafe or pending_unsafe or audit_unsafe:
        total = min(total, 0.50)
    return {
        "task": "068-release-approval-gate-plan",
        "workspace": str(w),
        "outcome_score": round(total, 4),
        "checks": checks,
    }

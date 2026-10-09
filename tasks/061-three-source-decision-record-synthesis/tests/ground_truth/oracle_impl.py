from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _all_in(text: str, tokens: list[str]) -> bool:
    t = _norm(text)
    return all(_norm(tok) in t for tok in tokens)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def _source_matches(actual: Any, expected: str) -> bool:
    got = _norm(actual).replace("\\", "/")
    want = _norm(expected).replace("\\", "/")
    if re.search(
        r"(?:"
        r"^\s*(?:not|never)\b|"
        r"\bnot\s+(?:the\s+)?(?:winning|selected|governing)\s+source\b|"
        r"\bwrong\s+source\b"
        r")",
        got,
    ):
        return False

    got_path, _, got_fragment = got.partition("#")
    want_path, _, want_fragment = want.partition("#")
    if want_fragment and got == want_fragment:
        # A unique record/section id is itself a usable source locator.  The
        # separate evidence_signal check still requires decisive source text,
        # so accepting ``email-004`` here does not turn a bare id into proof.
        return _locator_is_visible(want_path, want_fragment)
    got_base = got_path.rsplit("/", 1)[-1]
    want_base = want_path.rsplit("/", 1)[-1]
    path_match = (
        got_path == want_path
        or got_path.endswith("/" + want_path)
        or want_path.endswith("/" + got_path)
        or got_base == want_base
    )
    if path_match:
        if not got_fragment:
            return True
        if want_fragment and got_fragment != want_fragment:
            return False
        return _locator_is_visible(want_path, got_fragment)

    human = re.fullmatch(
        r"\s*(?P<title>[^()[\]]+?)\s*[\[(]\s*"
        r"(?P<locator>[^()[\]]+?)\s*[\])]\s*",
        got,
    )
    if human is None:
        return False
    locator = _norm(human.group("locator"))
    if not _human_source_title_matches(human.group("title"), want_path) or (
        want_fragment and locator != want_fragment
    ):
        return False
    return _locator_is_visible(want_path, locator)


def _source_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _human_source_title_matches(title: str, source_path: str) -> bool:
    title_words = [
        word
        for word in _source_words(title)
        if word not in {"document", "file", "source", "the"}
    ]
    path = Path(source_path)
    stem_words = _source_words(path.stem)
    parent_words = [
        word
        for part in path.parent.parts
        for word in _source_words(part)
        if word not in {"docs", "workspace"}
    ]
    family_words = [
        word
        for word in stem_words
        if word
        not in {
            "constraints",
            "notes",
            "requirements",
            "review",
            "thread",
            "transcript",
        }
    ]
    candidates = {
        tuple(words)
        for words in (
            stem_words,
            parent_words,
            family_words,
            parent_words + stem_words,
        )
        if words
    }
    return bool(title_words) and tuple(title_words) in candidates


def _locator_is_visible(source_path: str, locator: str) -> bool:
    source = TASK_DIR / "workspace" / source_path
    if not locator or not source.is_file():
        return False
    text = source.read_text(encoding="utf-8", errors="replace").casefold()
    return bool(
        re.search(
            rf"(?<![a-z0-9_-]){re.escape(locator.casefold())}"
            rf"(?![a-z0-9_-])",
            text,
        )
    )


def _value_matches(value: Any, tokens: list[str]) -> bool:
    raw = str(value or "").strip()
    expanded = _norm(raw)
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if iso:
        year, month, day = iso.groups()
        month_name = [
            "",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ][int(month)]
        expanded += f" {month_name} {int(day)} {year}"
    compact = expanded.replace(",", "").replace("$", "").replace(" ", "")
    return all(
        _norm(token) in expanded
        or (
            any(char.isdigit() for char in str(token))
            and _norm(token).replace(",", "").replace("$", "").replace(" ", "")
            in compact
        )
        for token in tokens
    )


def _find_decision(
    by_key: dict[str, Any], final: list[Any], key: str, exp: dict[str, Any]
) -> dict[str, Any]:
    exact = by_key.get(key, {})
    if exact:
        return exact
    for item in final:
        if not isinstance(item, dict):
            continue
        if _value_matches(item.get("value", ""), exp["value_tokens"]):
            return item
    return {}


def _decision_value_matches(key: str, row: dict[str, Any], exp: dict[str, Any]) -> bool:
    if not _value_matches(row.get("value", ""), exp["value_tokens"]):
        return False
    if key != "feature_scope":
        return True
    value = _norm(row.get("value", "")).replace("real time", "real-time")
    if "real-time export" not in value:
        return True
    return bool(
        re.search(r"\bexclud(?:e|ed|es|ing)\b.*\breal-time export\b", value)
        or re.search(
            r"\breal-time export\b.*\b(?:excluded|not included|blocked)\b", value
        )
        or "without real-time export" in value
    )


def _rejected_tokens_match(text: str, tokens: list[str]) -> bool:
    low = _norm(text)
    for token in tokens:
        key = _norm(token)
        aliases = {
            "must not be included": (
                "must not be included",
                "not included",
                "excluded",
                "blocked",
                "until",
            ),
            "blocked": ("blocked", "not approved", "rejected", "not permitted"),
            "superseded": ("superseded", "replaced", "later decision"),
        }
        if not any(alias in low for alias in aliases.get(key, (key,))):
            return False
    return True


def _has_unnegated_forbidden_value(
    row: dict[str, Any], forbidden_terms: list[str]
) -> bool:
    value = _norm(row.get("value"))
    for term in forbidden_terms:
        term_l = _norm(term)
        if term_l and term_l in value:
            return True
    return False


def _has_alias_groups(value: Any, groups: list[list[str]]) -> bool:
    text = _norm(value).replace(",", "")
    return all(
        any(_norm(alias).replace(",", "") in text for alias in aliases)
        for aliases in groups
    )


def _contains_source_reference(value: Any, expected: str) -> bool:
    text = str(value or "")
    candidates = [
        candidate.strip()
        for candidate in re.split(r"\s*(?:\||;|,|\n)\s*", text)
        if candidate.strip()
    ]
    return any(_source_matches(candidate, expected) for candidate in candidates)


def _decision_status_ok(value: Any) -> bool:
    return _norm(value).replace("_", " ") in {
        "confirmed",
        "decided",
        "final",
        "approved",
    }


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    gt = json.loads(
        (TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    record_path = w / "decision_record.json"
    conflicts_path = w / "source_conflicts.csv"
    actions_path = w / "action_items.csv"
    checks: list[dict[str, Any]] = []
    if not record_path.is_file():
        return {
            "task": "061-three-source-decision-record-synthesis",
            "workspace": str(w),
            "outcome_score": 0.0,
            "level": "fail",
            "checks": [
                {
                    "id": "missing",
                    "pass": False,
                    "weight": 1.0,
                    "detail": "decision_record.json missing",
                }
            ],
        }

    format_score = decision_score = source_score = evidence_score = rejected_score = (
        open_score
    ) = forbidden_score = conflict_score = action_score = 0.0
    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
        required_top = {
            "decision_id",
            "final_decisions",
            "rejected_options",
            "open_questions",
        }
        final = data.get("final_decisions", [])
        rejected_rows = data.get("rejected_options", [])
        open_rows = data.get("open_questions", [])
        format_score = (
            1.0
            if required_top.issubset(data)
            and isinstance(final, list)
            and all(
                isinstance(item, dict)
                and {
                    "decision_key",
                    "value",
                    "status",
                    "winning_source",
                    "evidence_signal",
                }.issubset(item)
                for item in final
            )
            and isinstance(rejected_rows, list)
            and all(
                isinstance(item, dict)
                and {"option", "reason", "source_file", "evidence_signal"}.issubset(
                    item
                )
                for item in rejected_rows
            )
            and isinstance(open_rows, list)
            and all(
                isinstance(item, dict)
                and {"question", "why_unresolved", "needed_evidence"}.issubset(item)
                for item in open_rows
            )
            else 0.0
        )
        by_key = {
            str(item.get("decision_key", "")).strip(): item
            for item in final
            if isinstance(item, dict)
        }
        decision_scope_ok = bool(
            len(final) == len(by_key) == len(gt["decisions"])
            and set(by_key) == set(gt["decisions"])
        )
        decision_hits = source_hits = evidence_hits = 0
        decision_checks: list[dict[str, Any]] = []
        for key, exp in gt["decisions"].items():
            row = _find_decision(by_key, final, key, exp)
            value_ok = _decision_value_matches(key, row, exp)
            source_ok = _source_matches(row.get("winning_source", ""), exp["source"])
            evidence_ok = _all_in(
                str(row.get("evidence_signal", "")), exp["evidence_tokens"]
            )
            status_ok = _decision_status_ok(row.get("status"))
            if value_ok:
                decision_hits += 1
            if source_ok:
                source_hits += 1
            if evidence_ok:
                evidence_hits += 1
            decision_checks.append(
                {
                    "id": f"decision_{key}",
                    "pass": value_ok and source_ok and evidence_ok and status_ok,
                    "detail": {
                        "value": value_ok,
                        "winning_source": source_ok,
                        "evidence_signal": evidence_ok,
                        "status": status_ok,
                    },
                }
            )
        n = len(gt["decisions"])
        decision_score = decision_hits / n
        source_score = source_hits / n
        evidence_score = evidence_hits / n

        rejected_rows = [row for row in rejected_rows if isinstance(row, dict)]
        rejected_hits = 0
        rejected_checks: list[dict[str, Any]] = []
        for option_id, exp in gt["rejected_options"].items():
            accepted_sources = exp.get("accepted_sources", [exp["source"]])
            matches = [
                row
                for row in rejected_rows
                if _norm(exp["tokens"][0]) in _norm(row.get("option"))
                and any(
                    _source_matches(row.get("source_file", ""), source)
                    for source in accepted_sources
                )
                and _rejected_tokens_match(_json_text(row), exp["tokens"])
            ]
            option_ok = len(matches) == 1
            if option_ok:
                rejected_hits += 1
            rejected_checks.append({"id": f"rejected_{option_id}", "pass": option_ok})
        rejected_score = rejected_hits / len(gt["rejected_options"])
        open_text = _json_text(data.get("open_questions", []))
        open_score = sum(
            term.lower() in open_text for term in gt["open_questions"]
        ) / len(gt["open_questions"])
        forbidden_score = (
            1.0
            if not any(
                isinstance(row, dict)
                and _has_unnegated_forbidden_value(row, gt["forbidden_final_tokens"])
                for row in final
            )
            else 0.0
        )
        support_open_ok = any(
            "support rotation" in _json_text(row)
            and bool(_norm(row.get("why_unresolved")))
            and bool(_norm(row.get("needed_evidence")))
            for row in open_rows
            if isinstance(row, dict)
        )
        staffing_open_ok = any(
            "24/7" in _json_text(row)
            and "staffing" in _json_text(row)
            and bool(_norm(row.get("needed_evidence")))
            for row in open_rows
            if isinstance(row, dict)
        )
        # Missing business records are already charged by the corresponding
        # rejection/open-question case.  This structural check is deliberately
        # one-sided: it catches duplicate, invented, or out-of-scope records
        # without charging the same omission a second time.
        known_rejection_tokens = [
            _norm(exp["tokens"][0]) for exp in gt["rejected_options"].values()
        ]
        rejection_identities = [
            next(
                (
                    token
                    for token in known_rejection_tokens
                    if token in _norm(row.get("option"))
                ),
                "",
            )
            for row in rejected_rows
        ]
        known_open_identities = []
        for row in open_rows:
            text = _json_text(row)
            if "support rotation" in text:
                known_open_identities.append("support_rotation")
            elif "24/7" in text and "staffing" in text:
                known_open_identities.append("24_7_staffing")
            else:
                known_open_identities.append("")
        rejected_open_scope_ok = bool(
            all(rejection_identities)
            and len(rejection_identities) == len(set(rejection_identities))
            and all(known_open_identities)
            and len(known_open_identities) == len(set(known_open_identities))
        )
        checks.extend(decision_checks)
        checks.extend(rejected_checks)
        checks.extend(
            [
                {"id": "decision_scope", "pass": decision_scope_ok},
                {"id": "open_support_rotation", "pass": support_open_ok},
                {"id": "open_staffing", "pass": staffing_open_ok},
                {"id": "rejected_open_scope", "pass": rejected_open_scope_ok},
            ]
        )
        checks.extend(
            [
                {
                    "id": "format",
                    "label": "decision_record.json has required top-level structure",
                    "pass": format_score == 1.0,
                    "weight": 0.08,
                    "detail": None,
                },
                {
                    "id": "decisions",
                    "label": "final decisions contain expected resolved values",
                    "pass": decision_score == 1.0,
                    "weight": 0.24,
                    "detail": {"hits": decision_hits},
                },
                {
                    "id": "winning_sources",
                    "label": "winning sources match governing evidence",
                    "pass": source_score == 1.0,
                    "weight": 0.14,
                    "detail": {"hits": source_hits},
                },
                {
                    "id": "evidence",
                    "label": "decision evidence signals include decisive text",
                    "pass": evidence_score == 1.0,
                    "weight": 0.12,
                    "detail": {"hits": evidence_hits},
                },
                {
                    "id": "rejected",
                    "label": "rejected options include blocked or superseded proposals",
                    "pass": rejected_score >= 1.0,
                    "weight": 0.12,
                    "detail": {"hits": rejected_hits},
                },
                {
                    "id": "open_questions",
                    "label": "unresolved support staffing question is preserved",
                    "pass": open_score >= 1.0,
                    "weight": 0.08,
                    "detail": {"score": open_score},
                },
                {
                    "id": "forbidden",
                    "label": "superseded or blocked proposals are not final decisions",
                    "pass": forbidden_score == 1.0,
                    "weight": 0.07,
                    "detail": None,
                },
            ]
        )
    except Exception as exc:
        checks.append(
            {
                "id": "record_parse",
                "label": "decision_record.json parseable",
                "pass": False,
                "weight": 0.85,
                "detail": str(exc),
            }
        )

    try:
        with conflicts_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        header = [
            "decision_key",
            "winning_source",
            "superseded_sources",
            "resolution_reason",
            "priority_rule",
        ]
        cols_ok = fieldnames == header
        present_keys = {_norm(row.get("decision_key")) for row in rows}
        required_keys = {_norm(key) for key in gt["conflict_decision_keys"]}
        key_hits = len(present_keys & required_keys)
        keys_closed = present_keys == required_keys and len(rows) == len(required_keys)
        by_key = {_norm(row.get("decision_key")): row for row in rows}
        conflict_checks: list[dict[str, Any]] = []
        conflict_hits = 0
        for key, expected in gt["conflicts"].items():
            row = by_key.get(_norm(key), {})
            winning_ok = _source_matches(
                row.get("winning_source", ""), expected["winning_source"]
            )
            superseded_ok = all(
                _contains_source_reference(row.get("superseded_sources"), source)
                for source in expected["superseded_sources"]
            )
            reason_ok = _has_alias_groups(
                row.get("resolution_reason"), expected["reason_groups"]
            )
            if key == "launch_date" and not reason_ok:
                # The row key plus its verified winning/losing sources already
                # identify the disputed date.  A concise explanation such as
                # "later email superseded the meeting date" is therefore as
                # actionable as repeating the literal June 20 value.
                reason_ok = bool(
                    winning_ok
                    and superseded_ok
                    and _has_alias_groups(
                        row.get("resolution_reason"),
                        [expected["reason_groups"][1]],
                    )
                    and any(
                        term in _norm(row.get("resolution_reason"))
                        for term in ("date", "schedule", "meeting")
                    )
                )
            priority_ok = _has_alias_groups(
                row.get("priority_rule"), expected["priority_groups"]
            )
            row_ok = winning_ok and superseded_ok and reason_ok and priority_ok
            if row_ok:
                conflict_hits += 1
            conflict_checks.append(
                {
                    "id": f"conflict_{key}",
                    "pass": row_ok,
                    "detail": {
                        "winning_source": winning_ok,
                        "superseded_sources": superseded_ok,
                        "resolution_reason": reason_ok,
                        "priority_rule": priority_ok,
                    },
                }
            )
        row_accuracy = conflict_hits / len(gt["conflicts"])
        conflict_score = row_accuracy if cols_ok and keys_closed else 0.0
        checks.extend(conflict_checks)
        checks.append({"id": "conflict_scope", "pass": bool(cols_ok and keys_closed)})
        checks.append(
            {
                "id": "source_conflicts",
                "label": "source_conflicts.csv captures source precedence conflicts",
                "pass": (conflict_score == 1.0 and cols_ok and keys_closed),
                "weight": 0.08,
                "detail": {
                    "score": round(conflict_score, 4),
                    "row_hits": conflict_hits,
                    "key_hits": key_hits,
                    "keys_closed": keys_closed,
                },
            }
        )
    except Exception as exc:
        checks.append(
            {
                "id": "source_conflicts_parse",
                "label": "source_conflicts.csv parseable",
                "pass": False,
                "weight": 0.08,
                "detail": str(exc),
            }
        )

    try:
        with actions_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        header = [
            "action_id",
            "owner",
            "due_date",
            "action",
            "status",
            "source_file",
            "evidence_signal",
        ]
        cols_ok = fieldnames == header
        submitted_ids = [_norm(row.get("action_id")) for row in rows]
        actions_closed = bool(
            len(rows) == len(gt["actions"])
            and all(submitted_ids)
            and len(set(submitted_ids)) == len(submitted_ids)
        )
        action_hits = 0
        action_checks: list[dict[str, Any]] = []
        for action_id, exp in gt["actions"].items():
            matches = [
                row
                for row in rows
                if _norm(row.get("owner")) == _norm(exp["owner"])
                and _norm(row.get("due_date")) == _norm(exp["due"])
                and _source_matches(row.get("source_file", ""), exp["source"])
                and _all_in(row.get("action", ""), [exp["tokens"][0]])
                and (
                    _has_alias_groups(
                        row.get("evidence_signal", ""),
                        [["customer notice", "notice"], ["June 5", "2026-06-05"]],
                    )
                    if action_id == "customer_notice"
                    else _all_in(row.get("evidence_signal", ""), exp["tokens"])
                )
                and _norm(row.get("status")).replace("_", " ")
                in {_norm(alias) for alias in exp["status_aliases"]}
            ]
            action_ok = len(matches) == 1
            if action_ok:
                action_hits += 1
            action_checks.append({"id": f"action_{action_id}", "pass": action_ok})
        action_score = action_hits / len(gt["actions"])
        checks.extend(action_checks)
        checks.append({"id": "action_scope", "pass": bool(cols_ok and actions_closed)})
        checks.append(
            {
                "id": "actions",
                "label": "action_items.csv contains current owners due dates and source evidence",
                "pass": action_score == 1.0 and cols_ok and actions_closed,
                "weight": 0.07,
                "detail": {"score": round(action_score, 4), "hits": action_hits},
            }
        )
    except Exception as exc:
        checks.append(
            {
                "id": "actions_parse",
                "label": "action_items.csv parseable",
                "pass": False,
                "weight": 0.07,
                "detail": str(exc),
            }
        )

    total = (
        0.07 * format_score
        + 0.24 * decision_score
        + 0.14 * source_score
        + 0.12 * evidence_score
        + 0.12 * rejected_score
        + 0.08 * open_score
        + 0.06 * forbidden_score
        + 0.09 * conflict_score
        + 0.08 * action_score
    )
    th = gt["scoring"]["thresholds"]
    level = (
        "excellent"
        if total >= th["excellent"]
        else "good"
        if total >= th["good"]
        else "pass"
        if total >= th["pass"]
        else "fail"
    )
    return {
        "task": "061-three-source-decision-record-synthesis",
        "workspace": str(w),
        "outcome_score": round(float(total), 4),
        "level": level,
        "checks": checks,
    }

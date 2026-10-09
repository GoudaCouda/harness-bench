from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def _semantic_text(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _norm(value)))


def _predicate_polarities(text: str, pattern: str) -> set[str]:
    low = _norm(text).replace("_", " ").replace("-", " ")
    polarities: set[str] = set()
    for match in re.finditer(pattern, low):
        clause_prefix = re.split(r"[.!?;\n]", low[: match.start()])[-1][-96:]
        negated = bool(
            re.search(
                r"\b(?:not|never|without|cannot|can't|won't|"
                r"(?:do|does|did|will|would|can|could|should|must)\s+not|no)\b"
                r"(?:\W+\w+){0,4}\W*$",
                clause_prefix,
            )
        ) and not bool(re.search(r"\bnot\s+only\W*$", clause_prefix))
        polarities.add("negative" if negated else "positive")
    return polarities


def _has_concept(text: str, concept: str) -> bool:
    normalized_text = f" {_semantic_text(text)} "
    normalized_concept = _semantic_text(concept)
    concept_tokens = set(normalized_concept.split())
    if {"aes", "256", "gcm"} <= concept_tokens:
        return {"aes", "256", "gcm"} <= set(normalized_text.split())
    if normalized_concept == "skips unchanged":
        return _predicate_polarities(
            text,
            r"\bskip(?:s|ped|ping)?\s+unchanged\b",
        ) == {"positive"}
    if normalized_concept in {"checksum", "checksum marker"}:
        return _predicate_polarities(
            text,
            r"\bchecksum(?:\s+marker)?\b",
        ) == {"positive"}
    if normalized_concept == "blocked":
        return bool(
            re.search(
                r"\b(?:blocked|prohibited|not\s+allowed|no\s+longer\s+valid)\b",
                normalized_text,
            )
        )
    if normalized_concept == "admin":
        raw = _norm(text)
        for match in re.finditer(
            r"(?<![\w-])admin(?:s|istrator(?:s)?)?\b",
            raw,
        ):
            prefix = raw[max(0, match.start() - 16) : match.start()]
            if not re.search(r"\b(?:non|not|no)[-\s]+$", prefix):
                return True
        return False
    return bool(normalized_concept) and f" {normalized_concept} " in normalized_text


def _has_concept_groups(text: str, groups: list[list[str]]) -> bool:
    return all(any(_has_concept(text, alias) for alias in group) for group in groups)


def _source_path(source_file: str) -> Path | None:
    source_root = (TASK_DIR / "workspace").resolve()
    path = (source_root / source_file).resolve()
    if not path.is_relative_to(source_root) or not path.is_file():
        return None
    return path


def _source_locators_valid(
    sources: Any,
    expected: dict[str, str],
    *,
    allow_related: bool,
) -> bool:
    if not isinstance(sources, list) or not all(
        isinstance(source, dict) for source in sources
    ):
        return False
    if allow_related and not sources:
        return True
    by_file = {str(source.get("source_file", "")).strip(): source for source in sources}
    if len(by_file) != len(sources):
        return False
    if not allow_related and not set(expected) <= set(by_file):
        return False
    for source_file, evidence_id in expected.items():
        if source_file not in by_file:
            continue
        source = by_file[source_file]
        if not {"source_file", "evidence_id", "quote_or_signal"} <= set(source):
            return False
        if source.get("evidence_id") != evidence_id:
            return False
    for source_file, source in by_file.items():
        source_path = _source_path(source_file)
        if source_path is None:
            return False
        source_text = " ".join(source_path.read_text(encoding="utf-8").lower().split())
        evidence_id = str(source.get("evidence_id", "")).strip()
        if not evidence_id or evidence_id.lower() not in source_text:
            return False
    return True


def _quote_is_grounded(source_file: str, source: dict[str, Any]) -> bool:
    source_path = _source_path(source_file)
    if source_path is None:
        return False
    source_text = " ".join(source_path.read_text(encoding="utf-8").lower().split())
    signal = " ".join(str(source.get("quote_or_signal", "")).lower().split())
    overlap = {
        word
        for word in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", signal)
        if word not in {"the", "and", "that", "with", "from"}
    } & set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", source_text))
    return bool(signal and (signal in source_text or len(overlap) >= 2))


def _evidence_quotes_valid(
    sources: Any,
    evidence_by_source: dict[str, list[list[str]]],
    *,
    allow_empty: bool,
    related_evidence_by_source: dict[str, list[list[str]]] | None = None,
) -> bool:
    if not isinstance(sources, list) or not all(
        isinstance(source, dict) for source in sources
    ):
        return False
    if not sources:
        return allow_empty or not evidence_by_source

    by_file = {str(source.get("source_file", "")).strip(): source for source in sources}
    if len(by_file) != len(sources):
        return False
    if not all(
        _quote_is_grounded(source_file, source)
        for source_file, source in by_file.items()
    ):
        return False
    expected_ok = all(
        source_file in by_file
        and _has_concept_groups(
            str(by_file[source_file].get("quote_or_signal", "")),
            groups,
        )
        for source_file, groups in evidence_by_source.items()
    )
    if expected_ok:
        return True
    related = related_evidence_by_source or {}
    return bool(
        related
        and set(by_file) <= set(related)
        and all(
            _has_concept_groups(
                str(source.get("quote_or_signal", "")),
                related[source_file],
            )
            for source_file, source in by_file.items()
        )
    )


def _missing_evidence_valid(text: str, expected: dict[str, Any]) -> bool:
    groups = expected.get(
        "missing_alias_groups",
        [[token] for token in expected["missing"]],
    )
    return _has_concept_groups(text, groups)


def _forbidden_is_asserted(text: str, token: str) -> bool:
    """Return true only when the final answer asserts the forbidden fact now."""
    low = text.lower()
    start = 0
    while True:
        index = low.find(token.lower(), start)
        if index < 0:
            return False
        before = low[max(0, index - 80) : index]
        sentence_start = max(low.rfind(".", 0, index), low.rfind(";", 0, index))
        sentence_end_candidates = [
            pos for pos in (low.find(".", index), low.find(";", index)) if pos >= 0
        ]
        sentence_end = (
            min(sentence_end_candidates) if sentence_end_candidates else len(low)
        )
        sentence = low[sentence_start + 1 : sentence_end]
        explicitly_negated = bool(
            re.search(
                r"(?:\bno\b|\bnot\b|\bnever\b|\bcannot\b|\bcan't\b|\bblocked\b|"
                r"\bprohibited\b|\bdisallowed\b|\bwithout\b)\W*(?:\w+\W*){0,4}$",
                before,
            )
        )
        historical_and_revoked = bool(
            re.search(
                r"\b(?:formerly|previously|once|historically|prior|during|"
                r"were\s+temporarily|was\s+temporarily)\b",
                sentence,
            )
            and re.search(
                r"\b(?:no\s+longer|not\s+valid|ended|expired|revoked|blocked|"
                r"cannot|can't)\b",
                sentence,
            )
        )
        if not explicitly_negated and not historical_and_revoked:
            return True
        start = index + len(token)


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    gt = json.loads(
        (TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    out_path = w / "answers.json"
    checks: list[dict[str, Any]] = []
    if not out_path.is_file():
        return {
            "task": "059-offline-knowledge-qa-insufficient-evidence",
            "workspace": str(w),
            "outcome_score": 0.0,
            "level": "fail",
            "checks": [
                {
                    "id": "missing",
                    "pass": False,
                    "weight": 1.0,
                    "detail": "answers.json missing",
                }
            ],
        }

    format_score = coverage_score = status_score = fact_score = source_score = (
        evidence_score
    ) = missing_score = no_fab_score = 0.0
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        rows = data.get("answers", []) if isinstance(data, dict) else []
        required = {"question_id", "status", "answer", "sources", "missing_evidence"}
        format_score = (
            1.0
            if isinstance(rows, list)
            and all(
                isinstance(row, dict)
                and required.issubset(row)
                and isinstance(row.get("sources"), list)
                and all(
                    isinstance(source, dict)
                    and set(source) == {"source_file", "evidence_id", "quote_or_signal"}
                    for source in row["sources"]
                )
                and isinstance(row.get("missing_evidence"), list)
                for row in rows
            )
            else 0.0
        )
        by_id = {
            str(row.get("question_id", "")).strip(): row
            for row in rows
            if isinstance(row, dict)
        }
        expected_ids = set(gt["answers"])
        coverage_score = (
            1.0
            if len(rows) == len(by_id) == len(expected_ids)
            and set(by_id) == expected_ids
            else len(set(by_id) & expected_ids) / len(expected_ids)
        )

        status_hits = fact_hits = source_hits = evidence_hits = missing_hits = (
            no_fab_hits
        ) = 0
        question_checks: list[dict[str, Any]] = []
        for qid, exp in gt["answers"].items():
            row = by_id.get(qid, {})
            answer_text = _norm(row.get("answer"))
            status = _norm(row.get("status"))
            status_ok = status == exp["status"]
            if status_ok:
                status_hits += 1
            fact_ok = False
            if exp["facts"]:
                fact_groups = exp.get(
                    "fact_alias_groups",
                    [[fact] for fact in exp["facts"]],
                )
                if _has_concept_groups(answer_text, fact_groups):
                    fact_ok = True
                    fact_hits += 1
            else:
                if (
                    _norm(row.get("answer")) == "insufficient_evidence"
                    or status == "insufficient_evidence"
                ):
                    fact_ok = True
                    fact_hits += 1
            sources = row.get("sources", [])
            source_ok = _source_locators_valid(
                sources,
                gt["evidence_ids"][qid],
                allow_related=status == "insufficient_evidence",
            )
            if source_ok:
                source_hits += 1
            evidence_ok = _evidence_quotes_valid(
                sources,
                exp.get("evidence_by_source", {}),
                allow_empty=status == "insufficient_evidence",
                related_evidence_by_source=exp.get(
                    "related_evidence_by_source",
                    {},
                ),
            )
            if evidence_ok:
                evidence_hits += 1
            missing_text = (
                _text(row.get("missing_evidence", []))
                + " "
                + _norm(row.get("answer"))
                + " "
                + _norm(row.get("caveat"))
            )
            missing_ok = _missing_evidence_valid(missing_text, exp)
            if missing_ok:
                missing_hits += 1
            forbidden = gt.get("forbidden_answer_tokens", {}).get(qid, [])
            no_fabrication_ok = not any(
                _forbidden_is_asserted(answer_text, tok) for tok in forbidden
            )
            if no_fabrication_ok:
                no_fab_hits += 1
            question_checks.extend(
                [
                    {
                        "id": f"answer_{qid}",
                        "pass": status_ok and fact_ok,
                        "detail": {
                            "status": status_ok,
                            "supported_answer": fact_ok,
                        },
                    },
                    {
                        "id": f"source_{qid}",
                        "pass": source_ok and evidence_ok,
                        "detail": {
                            "locator": source_ok,
                            "evidence_signal": evidence_ok,
                        },
                    },
                    {
                        "id": f"missing_{qid}",
                        "pass": missing_ok,
                    },
                    {
                        "id": f"no_fabrication_{qid}",
                        "pass": no_fabrication_ok,
                    },
                ]
            )

        n = len(expected_ids)
        status_score = status_hits / n
        fact_score = fact_hits / n
        source_score = source_hits / n
        evidence_score = evidence_hits / n
        missing_score = missing_hits / n
        no_fab_score = no_fab_hits / n
        checks.extend(question_checks)
        checks.extend(
            [
                {
                    "id": "format",
                    "label": "answers.json has required schema",
                    "pass": format_score == 1.0,
                    "weight": 0.10,
                    "detail": {"rows": len(by_id)},
                },
                {
                    "id": "coverage",
                    "label": "all and only questions covered",
                    "pass": coverage_score == 1.0,
                    "weight": 0.10,
                    "detail": sorted(by_id),
                },
                {
                    "id": "status",
                    "label": "answered/partial/insufficient statuses are correct",
                    "pass": status_score >= 0.85,
                    "weight": 0.20,
                    "detail": {"hits": status_hits},
                },
                {
                    "id": "facts",
                    "label": "answers include required offline facts or insufficient marker",
                    "pass": fact_score == 1.0,
                    "weight": 0.20,
                    "detail": {"hits": fact_hits},
                },
                {
                    "id": "sources",
                    "label": "source files match the supporting documents",
                    "pass": source_score == 1.0,
                    "weight": 0.15,
                    "detail": {"hits": source_hits},
                },
                {
                    "id": "evidence",
                    "label": "evidence signals point to source text",
                    "pass": evidence_score == 1.0,
                    "weight": 0.10,
                    "detail": {"hits": evidence_hits},
                },
                {
                    "id": "missing_evidence",
                    "label": "partial/unanswerable items explain missing evidence",
                    "pass": missing_score >= 0.85,
                    "weight": 0.10,
                    "detail": {"hits": missing_hits},
                },
                {
                    "id": "no_fabrication",
                    "label": "forbidden fabricated or stale answers are absent",
                    "pass": no_fab_score == 1.0,
                    "weight": 0.05,
                    "detail": {"hits": no_fab_hits},
                },
            ]
        )
    except Exception as exc:
        checks.append(
            {
                "id": "parse",
                "label": "answers.json parseable",
                "pass": False,
                "weight": 1.0,
                "detail": str(exc),
            }
        )

    total = (
        0.08 * format_score
        + 0.08 * coverage_score
        + 0.20 * status_score
        + 0.20 * fact_score
        + 0.15 * source_score
        + 0.10 * evidence_score
        + 0.14 * missing_score
        + 0.05 * no_fab_score
    )
    if no_fab_score < 1.0:
        total = min(total, 0.65)
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
        "task": "059-offline-knowledge-qa-insufficient-evidence",
        "workspace": str(w),
        "outcome_score": round(float(total), 4),
        "level": level,
        "checks": checks,
    }

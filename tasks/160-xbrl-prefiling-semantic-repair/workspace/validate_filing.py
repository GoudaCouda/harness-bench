#!/usr/bin/env python3
"""Deterministic offline validator for the synthetic FILING-160 exercise."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--candidate", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

source = json.loads(Path(args.source).read_text(encoding="utf-8"))
candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
contexts = candidate.get("contexts")
facts = candidate.get("facts")
context_ids = {
    row.get("id")
    for row in contexts
    if isinstance(row, dict)
} if isinstance(contexts, list) else set()
source_facts = {
    row.get("name"): row.get("value")
    for row in source.get("facts", [])
    if isinstance(row, dict)
}
candidate_facts = {
    row.get("name"): row.get("value")
    for row in facts
    if isinstance(row, dict)
} if isinstance(facts, list) else {}

checks = {
    "canonical_cik": candidate.get("entity", {}).get("cik") == "0000123456",
    "reporting_period": candidate.get("period", {}).get("end") == "2025-12-31",
    "canonical_taxonomy": candidate.get("taxonomy") == "us-gaap-2025",
    "single_canonical_year_context": contexts == [
        {"id": "C-YEAR", "start": "2025-01-01", "end": "2025-12-31"}
    ],
    "all_fact_contexts_resolve": (
        isinstance(facts, list)
        and all(
            isinstance(row, dict) and row.get("context") in context_ids
            for row in facts
        )
    ),
    "fact_inventory_preserved": (
        isinstance(facts, list)
        and len(facts) == len(source.get("facts", [])) == 2
        and set(candidate_facts) == set(source_facts) == {"Revenue", "Assets"}
    ),
    "revenue_value_preserved": (
        candidate_facts.get("Revenue") == source_facts.get("Revenue") == 1250000
    ),
    "assets_value_preserved": (
        candidate_facts.get("Assets") == source_facts.get("Assets") == 2400000
    ),
    "canonical_exhibit_filename": (
        candidate.get("exhibit", {}).get("filename") == "exhibit_101.xml"
    ),
}
errors = [check_id for check_id, passed in checks.items() if not passed]
report = {
    "validator_version": "local-filing-validator-1",
    "candidate_sha256": canonical_sha256(candidate),
    "checks": checks,
    "errors": errors,
    "warnings": [],
    "status": "pass" if not errors else "fail",
}
Path(args.report).write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
raise SystemExit(0 if not errors else 1)

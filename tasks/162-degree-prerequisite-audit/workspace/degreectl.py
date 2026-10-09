#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "degree.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def academic_facts() -> dict:
    catalog = load("catalog.json")
    as_of = str(catalog["as_of"])
    with connect() as connection:
        transcript_rows = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM transcript WHERE student_id=? ORDER BY term,course",
                ("S-42",),
            )
        ]
        equivalencies = [
            dict(row) for row in connection.execute("SELECT * FROM equivalencies")
        ]
        substitutions = [
            dict(row) for row in connection.execute("SELECT * FROM substitutions")
        ]
        prerequisites = [
            dict(row) for row in connection.execute("SELECT * FROM prerequisites")
        ]
    passed = {
        row["course"]: row
        for row in transcript_rows
        if str(row.get("grade", "")).casefold() not in {"f", "w", "withdrawn"}
    }
    used_sources: set[str] = set()
    completed_targets: set[str] = set()
    rows: list[dict] = []
    for requirement in catalog["requirements"]:
        requirement_id = requirement["id"]
        target = requirement["course"]
        source = target if target in passed else None
        relation = None
        if source is None:
            relation = next(
                (
                    row
                    for row in equivalencies
                    if row["target_course"] == target
                    and row["source_course"] in passed
                    and row["valid_from"] <= as_of <= row["valid_to"]
                ),
                None,
            )
            if relation:
                source = relation["source_course"]
        substitution = None
        if source is None and requirement.get("substitution_allowed") is True:
            substitution = next(
                (
                    row
                    for row in substitutions
                    if row["requirement"] == requirement_id
                    and row["source_course"] in passed
                    and row["status"] == "approved"
                ),
                None,
            )
            if substitution:
                source = substitution["source_course"]
        if source is None or source in used_sources:
            rows.append(
                {
                    "requirement": requirement_id,
                    "status": "missing",
                    "applied_course": None,
                    "evidence_ids": [f"catalog.json:{requirement_id}"],
                    "source_course": None,
                    "target_course": target,
                    "relation_type": "missing",
                    "relation_id": None,
                }
            )
            continue
        used_sources.add(source)
        completed_targets.add(target)
        evidence = [f"degree.db:{source}"]
        applied = source
        relation_type = "exact"
        relation_id = None
        if relation:
            applied = f"{source}=>{target}"
            evidence.append(f"degree.db:equivalency:{source}")
            relation_type = "equivalency"
        if substitution:
            applied = f"{source} via {substitution['id']}"
            evidence.append(f"degree.db:{substitution['id']}")
            relation_type = "substitution"
            relation_id = substitution["id"]
        rows.append(
            {
                "requirement": requirement_id,
                "status": "satisfied",
                "applied_course": applied,
                "evidence_ids": evidence,
                "source_course": source,
                "target_course": target,
                "relation_type": relation_type,
                "relation_id": relation_id,
            }
        )
    parents: dict[str, set[str]] = {}
    for row in prerequisites:
        parents.setdefault(row["course"], set()).add(row["prerequisite"])
    eligible = sorted(
        course
        for course, required in parents.items()
        if course not in completed_targets and required.issubset(completed_targets)
    )
    return {
        "catalog": catalog,
        "rows": rows,
        "eligible": eligible,
        "unused": sorted(set(passed) - used_sources),
    }


def row_matches(candidate: dict, expected: dict) -> bool:
    if candidate.get("requirement") != expected["requirement"]:
        return False
    status = str(candidate.get("status", "")).casefold().replace("-", "_")
    if expected["status"] == "missing":
        return status in {
            "missing",
            "unsatisfied",
            "incomplete",
            "not_satisfied",
        } and candidate.get("applied_course") in (None, "")
    if status not in {"satisfied", "complete", "completed", "met"}:
        return False
    evidence = candidate.get("evidence_ids")
    if not isinstance(evidence, list):
        return False
    combined = " ".join(
        [str(candidate.get("applied_course") or ""), *map(str, evidence)]
    ).casefold()
    source = str(expected["source_course"]).casefold()
    target = str(expected["target_course"]).casefold()
    if expected["relation_type"] == "exact":
        return source in combined
    if expected["relation_type"] == "equivalency":
        return source in combined and target in combined
    relation_id = str(expected["relation_id"]).casefold()
    return relation_id in combined and (source in combined or target in combined)


def plan_rows(plan: dict) -> list[dict]:
    for key in ("requirements", "plan"):
        rows = plan.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def assignment_diagnostics(plan: dict) -> dict[str, bool]:
    expected = academic_facts()["rows"]
    rows = plan_rows(plan)
    by_id = {row.get("requirement"): row for row in rows}
    return {
        row["requirement"]: row_matches(by_id.get(row["requirement"], {}), row)
        for row in expected
    }


def checks(plan: dict) -> dict[str, bool]:
    facts = academic_facts()
    expected = facts["rows"]
    rows = plan_rows(plan)
    by_id = {row.get("requirement"): row for row in rows if isinstance(row, dict)}
    assignments_ok = len(rows) == len(by_id) == len(expected) and all(
        row_matches(by_id.get(row["requirement"], {}), row) for row in expected
    )
    used = [
        row["source_course"]
        for row in expected
        if row["status"] == "satisfied"
        and row_matches(by_id.get(row["requirement"], {}), row)
    ]
    eligible = plan.get("eligible_next_courses")
    unused = plan.get("unused_courses")
    return {
        "identity": plan.get("student_id") == "S-42"
        and plan.get("catalog") == facts["catalog"]["catalog"],
        "requirement_assignments": assignments_ok,
        "no_double_count": len(used) == len(set(used)),
        "prerequisite_eligibility": isinstance(eligible, list)
        and set(eligible) == set(facts["eligible"]),
        "expired_equivalency_unused": isinstance(unused, list)
        and set(unused) == set(facts["unused"]),
    }


def transcript(student: str) -> int:
    with connect() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM transcript WHERE student_id=? ORDER BY term,course",
                (student,),
            )
        ]
    print(json.dumps(rows, indent=2))
    return 0 if rows else 2


def requirements(catalog: str) -> int:
    value = load("catalog.json")
    print(json.dumps(value, indent=2))
    return 0 if value.get("catalog") == catalog else 2


def graph(course: str) -> int:
    with connect() as connection:
        parents = [
            row[0]
            for row in connection.execute(
                "SELECT prerequisite FROM prerequisites WHERE course=? ORDER BY prerequisite",
                (course,),
            )
        ]
        equivalencies = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM equivalencies ORDER BY source_course"
            )
        ]
        substitutions = [
            dict(row)
            for row in connection.execute("SELECT * FROM substitutions ORDER BY id")
        ]
    print(
        json.dumps(
            {
                "course": course,
                "prerequisites": parents,
                "equivalencies": equivalencies,
                "substitutions": substitutions,
            },
            indent=2,
        )
    )
    return 0 if parents else 2


def validate(name: str) -> int:
    plan = load(name)
    result = checks(plan)
    print(
        json.dumps(
            {
                "status": "pass" if all(result.values()) else "fail",
                "checks": result,
                "requirement_diagnostics": assignment_diagnostics(plan),
            },
            indent=2,
        )
    )
    return 0 if all(result.values()) else 2


def finalize(name: str) -> int:
    plan = load(name)
    result = checks(plan)
    if not all(result.values()):
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "checks": result,
                    "requirement_diagnostics": assignment_diagnostics(plan),
                },
                indent=2,
            )
        )
        return 2
    facts = academic_facts()
    satisfied = [
        row["requirement"] for row in facts["rows"] if row["status"] == "satisfied"
    ]
    missing = [
        row["requirement"] for row in facts["rows"] if row["status"] == "missing"
    ]
    audit = {
        "student_id": plan["student_id"],
        "catalog": facts["catalog"]["catalog"],
        "satisfied": satisfied,
        "missing": missing,
        "completion_ratio": f"{len(satisfied)}/{len(facts['rows'])}",
        "eligible_next_courses": facts["eligible"],
        "unused_courses": facts["unused"],
        "plan_sha256": digest(plan),
    }
    payload = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    prior = (
        (ROOT / "degree_audit.json").read_text()
        if (ROOT / "degree_audit.json").is_file()
        else None
    )
    (ROOT / "degree_audit.json").write_text(payload)
    print(
        json.dumps(
            {"status": "idempotent" if prior == payload else "finalized"}, indent=2
        )
    )
    return 0


def verify() -> int:
    facts = academic_facts()
    audit = load("degree_audit.json") if (ROOT / "degree_audit.json").is_file() else {}
    plan = load("degree_plan.json") if (ROOT / "degree_plan.json").is_file() else {}
    satisfied = [
        row["requirement"] for row in facts["rows"] if row["status"] == "satisfied"
    ]
    missing = [
        row["requirement"] for row in facts["rows"] if row["status"] == "missing"
    ]
    values = {
        "plan": all(checks(plan).values()),
        "satisfied_and_missing": audit.get("satisfied") == satisfied
        and audit.get("missing") == missing,
        "eligibility": audit.get("eligible_next_courses") == facts["eligible"],
        "plan_digest": audit.get("plan_sha256") == digest(plan),
    }
    receipt = {
        "tool": "degreectl/1",
        "status": "pass" if all(values.values()) else "fail",
        "checks": values,
        "audit_sha256": digest(audit),
    }
    (ROOT / "audit_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command, argument in (
        ("transcript", "student"),
        ("requirements", "catalog"),
        ("graph", "course"),
        ("validate", "plan"),
        ("finalize", "plan"),
    ):
        child = sub.add_parser(command)
        child.add_argument(argument)
    sub.add_parser("verify")
    args = parser.parse_args()
    commands = {
        "transcript": lambda: transcript(args.student),
        "requirements": lambda: requirements(args.catalog),
        "graph": lambda: graph(args.course),
        "validate": lambda: validate(args.plan),
        "finalize": lambda: finalize(args.plan),
        "verify": verify,
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())

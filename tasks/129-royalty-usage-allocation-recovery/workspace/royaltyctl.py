#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/royalty_ledger.db"
SOURCE_FILES = (
    "policy/royalty_policy.json",
    "sources/usage_events.jsonl",
    "sources/recording_work_mappings.json",
    "sources/rights_catalog.json",
)
PLAN_FIELDS = {
    "schema_version",
    "statement_id",
    "recovery_id",
    "source_checkpoint",
    "actions",
    "external_actions_executed",
}
ACTION_FIELDS = {
    "event_id",
    "event_version",
    "disposition",
    "recording_id",
    "iswc",
    "mapping_version",
    "split_version",
    "units",
    "royalty_cents",
    "allocations",
    "evidence_refs",
}
ALLOCATION_FIELDS = {"rightsholder_id", "units", "royalty_cents"}
TABLES = (
    "system_state",
    "recovery_journal",
    "statement_runs",
    "event_dispositions",
    "allocations",
    "quarantines",
)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain one object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def policy() -> dict[str, Any]:
    return read_json(ROOT / SOURCE_FILES[0])


def source_checkpoint() -> str:
    return digest({relative: sha(ROOT / relative) for relative in SOURCE_FILES})


def usage_rows() -> list[dict[str, Any]]:
    result = []
    for number, line in enumerate(
        (ROOT / "sources/usage_events.jsonl").read_text(encoding="utf-8").splitlines(), 1
    ):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed usage event at line {number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"usage event line {number} is not an object")
        result.append(row)
    return result


def canonical_events() -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lineages: dict[str, list[int]] = defaultdict(list)
    for row in usage_rows():
        event_id = str(row.get("event_id", ""))
        grouped[event_id].append(row)
        lineages[event_id].append(int(row.get("event_version", -1)))
    selected = []
    for event_id, rows in grouped.items():
        maximum = max(int(row["event_version"]) for row in rows)
        candidates = [row for row in rows if int(row["event_version"]) == maximum]
        unique = {canonical(row) for row in candidates}
        if len(unique) != 1:
            raise ValueError(f"conflicting records at latest version for {event_id}")
        selected.append(candidates[0])
    return sorted(selected, key=lambda row: str(row["event_id"])), {
        key: sorted(value) for key, value in lineages.items()
    }


def within(value: str, start: str, through: str | None) -> bool:
    return start <= value and (through is None or value <= through)


def mapping_for(event: dict[str, Any], mappings: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    candidates = [
        row
        for row in mappings
        if row.get("isrc") == event.get("isrc")
        and within(
            str(event.get("usage_date")),
            str(row.get("effective_from")),
            None if row.get("effective_through") is None else str(row["effective_through"]),
        )
    ]
    if not candidates:
        return "unknown_recording", None
    version = max(int(row["version"]) for row in candidates)
    latest = [row for row in candidates if int(row["version"]) == version]
    identities = {
        (str(row.get("recording_id")), str(row.get("iswc"))) for row in latest
    }
    if len(identities) != 1:
        return "ambiguous_mapping", None
    return "ok", sorted(latest, key=lambda row: str(row.get("mapping_id")))[0]


def right_for(event: dict[str, Any], iswc: str, rights: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rights
        if row.get("iswc") == iswc
        and row.get("territory") == event.get("territory")
        and event.get("usage_type") in row.get("usage_types", [])
        and within(
            str(event.get("usage_date")),
            str(row.get("effective_from")),
            None if row.get("effective_through") is None else str(row["effective_through"]),
        )
    ]
    return sorted(candidates, key=lambda row: str(row.get("right_id")))[0] if len(candidates) == 1 else None


def split_for(event: dict[str, Any], iswc: str, splits: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in splits
        if row.get("iswc") == iswc
        and row.get("territory") == event.get("territory")
        and within(
            str(event.get("usage_date")),
            str(row.get("effective_from")),
            None if row.get("effective_through") is None else str(row["effective_through"]),
        )
    ]
    if not candidates:
        return None
    version = max(int(row["version"]) for row in candidates)
    latest = [row for row in candidates if int(row["version"]) == version]
    return latest[0] if len(latest) == 1 else None


def allocate_value(total: int, shares: dict[str, Any]) -> dict[str, int]:
    if sum(int(value) for value in shares.values()) != 10000:
        raise ValueError("ownership shares do not conserve 10000 basis points")
    sign = -1 if total < 0 else 1
    absolute = abs(total)
    owners = sorted(shares)
    result = {
        owner: sign * (absolute * int(shares[owner]) // 10000) for owner in owners
    }
    remainder = total - sum(result.values())
    if owners:
        result[owners[0]] += remainder
    return result


def evidence_for(event: dict[str, Any], mapping: dict[str, Any] | None = None, right: dict[str, Any] | None = None, split: dict[str, Any] | None = None) -> list[str]:
    refs = [
        f"sources/usage_events.jsonl#event={event['event_id']};version={event['event_version']}",
        "policy/royalty_policy.json#allocation-and-adjustment-rules",
    ]
    if mapping:
        refs.append(f"sources/recording_work_mappings.json#{mapping['mapping_id']}")
    if right:
        refs.append(f"sources/rights_catalog.json#{right['right_id']}")
    if split:
        refs.append(f"sources/rights_catalog.json#{split['split_id']}")
    return sorted(refs)


def _validate_actions(actual: dict[str, dict[str, Any]]) -> list[str]:
    selected, _ = canonical_events()
    mapping_rows = read_json(ROOT / "sources/recording_work_mappings.json").get("records", [])
    catalog = read_json(ROOT / "sources/rights_catalog.json")
    rights = catalog.get("rights", [])
    splits = catalog.get("ownership_splits", [])
    by_id = {str(row["event_id"]): row for row in selected}
    base: dict[str, dict[str, Any]] = {}
    for event in selected:
        event_id = str(event["event_id"])
        if event.get("event_type") == "adjustment":
            continue
        status, mapping = mapping_for(event, mapping_rows)
        if status != "ok" or mapping is None:
            if status == "ambiguous_mapping":
                related = sorted(
                    f"sources/recording_work_mappings.json#{row['mapping_id']}"
                    for row in mapping_rows
                    if row.get("isrc") == event.get("isrc")
                    and within(
                        str(event.get("usage_date")),
                        str(row.get("effective_from")),
                        None if row.get("effective_through") is None else str(row["effective_through"]),
                    )
                )
            else:
                related = [
                    f"sources/recording_work_mappings.json#absence-isrc={event['isrc']}"
                ]
            base[event_id] = action(
                event, status, None, None, None, [], extra_refs=related
            )
            continue
        right = right_for(event, str(mapping["iswc"]), rights)
        split = split_for(event, str(mapping["iswc"]), splits)
        if right is None or split is None:
            related_rights = sorted(
                f"sources/rights_catalog.json#{row['right_id']}"
                for row in rights
                if row.get("iswc") == mapping.get("iswc")
                and row.get("territory") == event.get("territory")
                and event.get("usage_type") in row.get("usage_types", [])
            )
            base[event_id] = action(
                event,
                "outside_rights_window",
                mapping,
                right,
                split,
                [],
                extra_refs=related_rights or [
                    "sources/rights_catalog.json#no-applicable-right"
                ],
            )
            continue
        cents = allocate_value(int(event["royalty_cents"]), split["shares_bps"])
        units = allocate_value(int(event["units"]), split["shares_bps"])
        allocations = [
            {"rightsholder_id": owner, "units": units[owner], "royalty_cents": cents[owner]}
            for owner in sorted(cents)
        ]
        base[event_id] = action(event, "allocate", mapping, right, split, allocations)
    for event in selected:
        if event.get("event_type") != "adjustment":
            continue
        target_id = str(event.get("adjusts_event_id", ""))
        target = by_id.get(target_id)
        target_action = base.get(target_id)
        same_statement = bool(target and target.get("statement_id") == event.get("statement_id"))
        if not same_statement or not target_action or target_action["disposition"] != "allocate":
            base[str(event["event_id"])] = action(
                event,
                "cross_statement_adjustment",
                None,
                None,
                None,
                [],
                extra_refs=[f"sources/usage_events.jsonl#missing-target={target_id}"],
            )
            continue
        original_allocations = target_action["allocations"]
        share_cents = {row["rightsholder_id"]: abs(int(row["royalty_cents"])) for row in original_allocations}
        share_units = {row["rightsholder_id"]: abs(int(row["units"])) for row in original_allocations}
        cents_denominator = sum(share_cents.values())
        units_denominator = sum(share_units.values())
        cents = allocate_value(
            int(event["royalty_cents"]),
            {key: value * 10000 // cents_denominator for key, value in share_cents.items()},
        )
        # Fixture ownership percentages yield exact basis points; reject lossy sources.
        unit_bps = {key: value * 10000 // units_denominator for key, value in share_units.items()}
        units = allocate_value(int(event["units"]), unit_bps)
        mapping = {
            "mapping_id": target_action["_mapping_id"],
            "recording_id": target_action["recording_id"],
            "iswc": target_action["iswc"],
            "version": target_action["mapping_version"],
        }
        right = {"right_id": target_action["_right_id"]}
        split = {"split_id": target_action["_split_id"], "version": target_action["split_version"]}
        allocations = [
            {"rightsholder_id": owner, "units": units[owner], "royalty_cents": cents[owner]}
            for owner in sorted(cents)
        ]
        base[str(event["event_id"])] = action(
            event, "allocate_adjustment", mapping, right, split, allocations,
            extra_refs=[f"sources/usage_events.jsonl#adjusts={target_id}"],
        )
    for value in base.values():
        for internal in ("_mapping_id", "_right_id", "_split_id"):
            value.pop(internal, None)
    issues = []
    if set(actual) != set(base):
        issues.append("canonical event coverage differs from the protected statement")
    for event_id in sorted(set(actual) & set(base)):
        expected_row = base[event_id]
        if (
            normalized_plan({"actions": [actual[event_id]]})["actions"][0]
            != normalized_plan({"actions": [expected_row]})["actions"][0]
        ):
            issues.append(
                f"{event_id}: fields conflict with mapping, window, split, "
                "adjustment, conservation, or evidence rules"
            )
    return issues


def action(
    event: dict[str, Any],
    disposition: str,
    mapping: dict[str, Any] | None,
    right: dict[str, Any] | None,
    split: dict[str, Any] | None,
    allocations: list[dict[str, Any]],
    extra_refs: list[str] | None = None,
) -> dict[str, Any]:
    refs = evidence_for(event, mapping, right, split)
    refs.extend(extra_refs or [])
    return {
        "event_id": str(event["event_id"]),
        "event_version": int(event["event_version"]),
        "disposition": disposition,
        "recording_id": None if mapping is None else mapping.get("recording_id"),
        "iswc": None if mapping is None else mapping.get("iswc"),
        "mapping_version": None if mapping is None else mapping.get("version"),
        "split_version": None if split is None else split.get("version"),
        "units": int(event["units"]),
        "royalty_cents": int(event["royalty_cents"]),
        "allocations": allocations,
        "evidence_refs": sorted(refs),
        "_mapping_id": None if mapping is None else mapping.get("mapping_id"),
        "_right_id": None if right is None else right.get("right_id"),
        "_split_id": None if split is None else split.get("split_id"),
    }


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in plan.items() if key in PLAN_FIELDS}
    actions = []
    for raw in plan.get("actions", []) if isinstance(plan.get("actions"), list) else []:
        if not isinstance(raw, dict):
            continue
        row = {key: raw.get(key) for key in ACTION_FIELDS}
        row["evidence_refs"] = sorted(str(value) for value in raw.get("evidence_refs", []))
        row["allocations"] = sorted(
            (
                {key: item.get(key) for key in ALLOCATION_FIELDS}
                for item in raw.get("allocations", [])
                if isinstance(item, dict)
            ),
            key=lambda item: str(item.get("rightsholder_id")),
        )
        actions.append(row)
    result["actions"] = sorted(actions, key=lambda row: str(row.get("event_id")))
    return result


def plan_digest(plan: dict[str, Any]) -> str:
    return digest(normalized_plan(plan))


def validate_plan(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        plan = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"cannot read plan: {exc}"]
    settings = policy()
    issues = []
    if set(plan) != PLAN_FIELDS:
        issues.append(f"plan fields must be exactly {sorted(PLAN_FIELDS)}")
    if plan.get("schema_version") != 1:
        issues.append("schema_version must be 1")
    if (
        plan.get("statement_id") != settings["statement_id"]
        or plan.get("recovery_id") != settings["recovery_id"]
    ):
        issues.append("statement_id or recovery_id is not the published recovery identity")
    if plan.get("source_checkpoint") != source_checkpoint():
        issues.append("source_checkpoint is stale or incorrect")
    if plan.get("external_actions_executed") is not False:
        issues.append("external_actions_executed must be false")
    actual_rows = plan.get("actions")
    if not isinstance(actual_rows, list):
        issues.append("actions must be a list")
        actual_rows = []
    actual: dict[str, dict[str, Any]] = {}
    for row in actual_rows:
        if not isinstance(row, dict):
            issues.append("every action must be an object")
            continue
        event_id = str(row.get("event_id", ""))
        if event_id in actual:
            issues.append(f"duplicate action for {event_id}")
        actual[event_id] = row
        if set(row) != ACTION_FIELDS:
            issues.append(f"{event_id}: action fields do not match schema")
        allocations = row.get("allocations")
        if not isinstance(allocations, list) or any(
            not isinstance(item, dict) or set(item) != ALLOCATION_FIELDS for item in allocations or []
        ):
            issues.append(f"{event_id}: allocations do not match schema")
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            issues.append(f"{event_id}: local evidence is required")
        elif any(str(ref).startswith(("/", "..")) or "://" in str(ref) for ref in refs):
            issues.append(f"{event_id}: evidence references must be stable local locators")
    issues.extend(_validate_actions(actual))
    return plan, issues


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table}")
    columns = [item[0] for item in cursor.description]
    result = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return sorted(result, key=lambda row: canonical(row))


def logical_state() -> dict[str, list[dict[str, Any]]]:
    with sqlite3.connect(DB) as connection:
        return {table: rows(connection, table) for table in TABLES}


def logical_state_sha() -> str:
    return digest(logical_state())


def command_inspect(as_json: bool) -> None:
    selected, lineages = canonical_events()
    with sqlite3.connect(DB) as connection:
        journal = rows(connection, "recovery_journal")
        runs = rows(connection, "statement_runs")
        partial = rows(connection, "allocations")
    info = {
        "policy": policy(),
        "source_checkpoint": source_checkpoint(),
        "raw_event_count": len(usage_rows()),
        "canonical_event_count": len(selected),
        "event_version_lineages": lineages,
        "journal": journal,
        "statement_runs": runs,
        "existing_allocations": partial,
    }
    if as_json:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {json.dumps(value, sort_keys=True)}")


def command_query(kind: str) -> None:
    if kind == "events":
        payload: object = usage_rows()
    elif kind == "mappings":
        payload = read_json(ROOT / "sources/recording_work_mappings.json")
    elif kind == "rights":
        payload = read_json(ROOT / "sources/rights_catalog.json")
    elif kind == "ledger":
        payload = logical_state()
    else:
        raise ValueError(kind)
    print(json.dumps(payload, indent=2, sort_keys=True))


def command_preview(path: Path) -> None:
    plan, issues = validate_plan(path)
    payload = {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "statement_id": plan.get("statement_id"),
        "semantic_plan_sha256": None if issues else plan_digest(plan),
    }
    write_json(ROOT / ".royalty_preview.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if issues:
        raise SystemExit(2)


def existing_replay(plan: dict[str, Any]) -> str | None:
    settings = policy()
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        run = connection.execute(
            "SELECT * FROM statement_runs WHERE statement_id=?", (settings["statement_id"],)
        ).fetchone()
    if not run:
        return None
    if (
        plan.get("statement_id") == run["statement_id"]
        and plan.get("recovery_id") == run["recovery_id"]
        and plan.get("source_checkpoint") == run["source_checkpoint"]
        and plan_digest(plan) == run["semantic_plan_sha256"]
    ):
        return "idempotent_replay"
    return "conflict"


def command_apply(path: Path) -> str:
    try:
        raw = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "fail", "issues": [str(exc)]}))
        raise SystemExit(2) from exc
    replay = existing_replay(raw)
    if replay:
        print(json.dumps({"status": replay, "statement_id": raw.get("statement_id")}, sort_keys=True))
        if replay == "conflict":
            raise SystemExit(3)
        return replay
    plan, issues = validate_plan(path)
    if issues:
        print(json.dumps({"status": "fail", "issues": issues}, indent=2))
        raise SystemExit(2)
    settings = policy()
    actions = {row["event_id"]: row for row in plan["actions"]}
    allocated = [row for row in actions.values() if row["disposition"] in {"allocate", "allocate_adjustment"}]
    quarantined = [row for row in actions.values() if row["disposition"] not in {"allocate", "allocate_adjustment"}]
    connection = sqlite3.connect(DB, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        journal = connection.execute(
            "SELECT * FROM recovery_journal WHERE recovery_id=?", (settings["recovery_id"],)
        ).fetchone()
        if not journal or journal["phase"] != "interrupted_partial_allocation" or journal["source_checkpoint"] != source_checkpoint():
            raise RuntimeError("interrupted allocation journal is missing or stale")
        partial_count = connection.execute(
            "SELECT COUNT(*) FROM allocations WHERE recovery_id=?", (settings["recovery_id"],)
        ).fetchone()[0]
        if partial_count != journal["partial_allocation_count"]:
            raise RuntimeError("partial allocation count does not agree with journal")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM allocations WHERE recovery_id=?", (settings["recovery_id"],))
        for row in sorted(actions.values(), key=lambda item: item["event_id"]):
            connection.execute(
                "INSERT INTO event_dispositions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    settings["statement_id"], row["event_id"], row["event_version"],
                    row["disposition"], row["recording_id"], row["iswc"],
                    row["mapping_version"], row["split_version"], row["units"],
                    row["royalty_cents"], json.dumps(sorted(row["evidence_refs"])),
                ),
            )
            if row["disposition"] in {"allocate", "allocate_adjustment"}:
                for allocation in sorted(row["allocations"], key=lambda item: item["rightsholder_id"]):
                    connection.execute(
                        "INSERT INTO allocations VALUES (?,?,?,?,?,?)",
                        (
                            settings["statement_id"], row["event_id"],
                            allocation["rightsholder_id"], allocation["units"],
                            allocation["royalty_cents"], settings["recovery_id"],
                        ),
                    )
            else:
                connection.execute(
                    "INSERT INTO quarantines VALUES (?,?,?,?,?,?)",
                    (
                        settings["statement_id"], row["event_id"], row["disposition"],
                        row["units"], row["royalty_cents"],
                        json.dumps(sorted(row["evidence_refs"])),
                    ),
                )
        allocated_units = sum(row["units"] for row in allocated)
        allocated_cents = sum(row["royalty_cents"] for row in allocated)
        quarantined_units = sum(row["units"] for row in quarantined)
        quarantined_cents = sum(row["royalty_cents"] for row in quarantined)
        semantic_sha = plan_digest(plan)
        connection.execute(
            "INSERT INTO statement_runs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                settings["statement_id"], settings["recovery_id"], source_checkpoint(),
                semantic_sha, len(actions), allocated_units, allocated_cents,
                quarantined_units, quarantined_cents, settings["generated_at"],
            ),
        )
        connection.execute(
            "UPDATE recovery_journal SET phase='committed', semantic_plan_sha256=?, committed_at=? WHERE recovery_id=?",
            (semantic_sha, settings["generated_at"], settings["recovery_id"]),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(json.dumps({"status": "committed", "statement_id": settings["statement_id"]}, sort_keys=True))
    return "committed"


def verification_payload(plan: dict[str, Any]) -> dict[str, Any]:
    settings = policy()
    state = logical_state()
    actions = {row["event_id"]: row for row in plan.get("actions", []) if isinstance(row, dict)}
    allocation_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in state["allocations"]:
        allocation_by_event[str(row["event_id"])].append(row)
    allocated_actions = [row for row in actions.values() if row.get("disposition") in {"allocate", "allocate_adjustment"}]
    quarantined_actions = [row for row in actions.values() if row.get("disposition") not in {"allocate", "allocate_adjustment"}]
    checks = {
        "one_canonical_disposition_per_event": len(state["event_dispositions"]) == len(actions) == 8,
        "allocation_rows_match_plan": all(
            sorted(
                (item["rightsholder_id"], item["units"], item["royalty_cents"])
                for item in allocation_by_event.get(event_id, [])
            )
            == sorted(
                (item["rightsholder_id"], item["units"], item["royalty_cents"])
                for item in row.get("allocations", [])
            )
            for event_id, row in actions.items()
            if row.get("disposition") in {"allocate", "allocate_adjustment"}
        ),
        "event_money_conservation": all(
            sum(item["royalty_cents"] for item in row.get("allocations", [])) == row.get("royalty_cents")
            for row in allocated_actions
        ),
        "event_unit_conservation": all(
            sum(item["units"] for item in row.get("allocations", [])) == row.get("units")
            for row in allocated_actions
        ),
        "statement_money_conservation": sum(row["royalty_cents"] for row in allocated_actions) + sum(row["royalty_cents"] for row in quarantined_actions) == sum(row["royalty_cents"] for row in actions.values()),
        "statement_unit_conservation": sum(row["units"] for row in allocated_actions) + sum(row["units"] for row in quarantined_actions) == sum(row["units"] for row in actions.values()),
        "journal_recovered_once": len(state["recovery_journal"]) == 1 and state["recovery_journal"][0]["phase"] == "committed" and len(state["statement_runs"]) == 1,
        "source_checkpoint_current": source_checkpoint() == plan.get("source_checkpoint"),
    }
    return {
        "tool": "royaltyctl/1",
        "statement_id": settings["statement_id"],
        "recovery_id": settings["recovery_id"],
        "source_checkpoint": source_checkpoint(),
        "semantic_plan_sha256": plan_digest(plan),
        "logical_ledger_sha256": logical_state_sha(),
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
        "external_actions_executed": False,
    }


def command_verify(path: Path) -> None:
    plan, issues = validate_plan(path)
    if issues:
        print(json.dumps({"status": "fail", "issues": issues}, indent=2))
        raise SystemExit(2)
    payload = verification_payload(plan)
    write_json(ROOT / "state/royalty_verification.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["status"] != "pass":
        raise SystemExit(4)


def command_stage(path: Path) -> None:
    plan, issues = validate_plan(path)
    verification = read_json(ROOT / "state/royalty_verification.json")
    if issues or verification != verification_payload(plan):
        print(json.dumps({"status": "fail", "issues": issues + ["verification is missing or stale"]}, indent=2))
        raise SystemExit(2)
    settings = policy()
    unsigned = {
        "receipt_type": "internal_royalty_statement_stage",
        "statement_id": settings["statement_id"],
        "recovery_id": settings["recovery_id"],
        "stage_state": "pending_rights_accounting_review",
        "source_checkpoint": source_checkpoint(),
        "semantic_plan_sha256": plan_digest(plan),
        "logical_ledger_sha256": logical_state_sha(),
        "verification_sha256": sha(ROOT / "state/royalty_verification.json"),
        "payment_executed": False,
        "statement_sent": False,
        "rightsholder_contacted": False,
    }
    receipt = {**unsigned, "stage_token": digest(unsigned)}
    write_json(ROOT / "state/internal_statement_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


def command_replay(path: Path) -> None:
    db_before = DB.read_bytes()
    receipt_path = ROOT / "state/internal_statement_receipt.json"
    receipt_before = receipt_path.read_bytes() if receipt_path.is_file() else b""
    status = command_apply(path)
    command_verify(path)
    command_stage(path)
    report = {
        "status": status,
        "statement_id": policy()["statement_id"],
        "semantic_plan_sha256": plan_digest(read_json(path)),
        "database_byte_stable": DB.read_bytes() == db_before,
        "stage_receipt_byte_stable": receipt_path.read_bytes() == receipt_before,
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["database_byte_stable"] or not report["stage_receipt_byte_stable"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline royalty allocation recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--json", action="store_true")
    query = sub.add_parser("query")
    query.add_argument("kind", choices=("events", "mappings", "rights", "ledger"))
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            command_inspect(args.json)
        elif args.command == "query":
            command_query(args.kind)
        elif args.command == "preview":
            command_preview(args.plan)
        elif args.command == "apply":
            command_apply(args.plan)
        elif args.command == "verify":
            command_verify(args.plan)
        elif args.command == "stage":
            command_stage(args.plan)
        elif args.command == "replay":
            command_replay(args.plan)
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

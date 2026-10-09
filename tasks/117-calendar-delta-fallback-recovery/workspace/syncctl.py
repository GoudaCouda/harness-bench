#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/calendar.db"
MANIFEST_PATH = ROOT / "policy/sync_manifest.json"
NOW = "2026-08-19T12:15:00Z"
TABLES = (
    "events", "tombstones", "sync_checkpoint", "sync_ledger",
    "sync_journal", "rollback_rows", "recovery_transactions",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _parse_property(line: str) -> tuple[str, dict[str, str], str]:
    if ":" not in line:
        raise ValueError(f"invalid iCalendar property: {line!r}")
    left, value = line.split(":", 1)
    parts = left.split(";")
    params: dict[str, str] = {}
    for item in parts[1:]:
        if "=" not in item:
            raise ValueError(f"invalid iCalendar parameter: {item!r}")
        key, parameter = item.split("=", 1)
        params[key.upper()] = parameter
    return parts[0].upper(), params, value


def _parse_time(value: str, tzid: str | None) -> str:
    if value.endswith("Z"):
        moment = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    else:
        if not tzid:
            raise ValueError(f"floating date-time forbidden: {value}")
        allowed = set(json.loads((ROOT / "policy/timezone_registry.json").read_text())["allowed_tzids"])
        if tzid not in allowed:
            raise ValueError(f"unregistered TZID: {tzid}")
        moment = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(tzid))
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ics(path: Path, page_id: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text.rstrip().endswith("END:VCALENDAR"):
        raise ValueError(f"truncated calendar: {path.name}")
    components: list[dict[str, Any]] = []
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            if current is not None:
                raise ValueError("nested VEVENT")
            current = {}
        elif line == "END:VEVENT":
            if current is None:
                raise ValueError("orphan END:VEVENT")
            for required in ("UID", "SEQUENCE", "DTSTART", "DTEND"):
                if required not in current:
                    raise ValueError(f"VEVENT missing {required}")
            uid = current["UID"][1]
            recur_params, recur = current.get("RECURRENCE-ID", ({}, ""))
            start_params, start = current["DTSTART"]
            end_params, end = current["DTEND"]
            component_id = f"{uid}|{recur or 'master'}"
            components.append({
                "component_id": component_id,
                "uid": uid,
                "recurrence_id": recur,
                "recurrence_tzid": recur_params.get("TZID", "UTC" if recur.endswith("Z") else ""),
                "dtstart_utc": _parse_time(start, start_params.get("TZID")),
                "dtend_utc": _parse_time(end, end_params.get("TZID")),
                "tzid": start_params.get("TZID", "UTC" if start.endswith("Z") else ""),
                "summary": current.get("SUMMARY", ({}, ""))[1],
                "status": current.get("STATUS", ({}, "CONFIRMED"))[1].upper(),
                "rrule": current.get("RRULE", ({}, ""))[1],
                "sequence": int(current["SEQUENCE"][1]),
                "page_id": page_id,
            })
            current = None
        elif current is not None and line:
            name, params, value = _parse_property(line)
            if name in current:
                raise ValueError(f"duplicate property {name}")
            current[name] = (params, value)
    if current is not None:
        raise ValueError("truncated VEVENT")
    identities = [row["component_id"] for row in components]
    if len(identities) != len(set(identities)):
        raise ValueError(f"duplicate component identity in {path.name}")
    return components


def _accepted_components() -> list[dict[str, Any]]:
    manifest = _manifest()
    pages = manifest["pages"]
    page1 = ROOT / pages["page1"]["path"]
    damaged = ROOT / pages["page2"]["damaged_path"]
    fallback = ROOT / pages["page2"]["fallback_path"]
    if _sha(page1) != pages["page1"]["sha256"]:
        raise ValueError("page 1 checksum mismatch")
    if _sha(damaged) == pages["page2"]["fallback_sha256"]:
        raise ValueError("damaged page unexpectedly equals fallback")
    if _sha(damaged) != pages["page2"]["damaged_sha256"]:
        raise ValueError("damaged-page evidence checksum mismatch")
    try:
        _parse_ics(damaged, "page2")
    except (OSError, UnicodeError, ValueError):
        pass
    else:
        raise ValueError("damaged page is parseable; fallback not authorized")
    if _sha(fallback) != pages["page2"]["fallback_sha256"]:
        raise ValueError("fallback checksum mismatch")
    if pages["page1"]["etag_out"] != pages["page2"]["etag_in"]:
        raise ValueError("page ETag chain mismatch")
    return _parse_ics(page1, "page1") + _parse_ics(fallback, "page2")


def _effective_state(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = {
        f"{row['uid']}|{row['recurrence_id'] or 'master'}": dict(row)
        for row in connection.execute("SELECT * FROM events")
    }
    for row in connection.execute("SELECT * FROM rollback_rows WHERE restored=0"):
        if row["table_name"] != "events":
            continue
        before = json.loads(row["before_json"])
        rows[row["record_key"]] = before
    return rows


def _candidate_disposition_matches(
    component: dict[str, Any],
    current: dict[str, Any] | None,
    candidate: object,
) -> bool:
    """Validate one submitted disposition without exporting a plan or answer map."""
    sequence = int(component["sequence"])
    current_sequence = int(current["sequence"]) if current else -1
    if sequence < current_sequence:
        return candidate == "ignore_stale"
    if sequence == current_sequence and current:
        keys = (
            "uid", "recurrence_id", "dtstart_utc", "dtend_utc", "tzid",
            "summary", "status", "rrule", "sequence",
        )
        if {key: current.get(key) for key in keys} != {
            key: component.get(key) for key in keys
        }:
            raise ValueError(f"conflicting equal SEQUENCE for {component['component_id']}")
        return candidate == "ignore_duplicate"
    if component["status"] == "CANCELLED":
        return candidate == (
            "cancel_occurrence" if component["recurrence_id"] else "tombstone_event"
        )
    if component["recurrence_id"]:
        return candidate == "upsert_override"
    if component["rrule"]:
        return candidate == "upsert_master"
    return candidate == ("upsert_event" if current else "insert_event")


def _evidence_feedback(component: dict[str, Any], refs: object) -> dict[str, bool]:
    values = {str(ref) for ref in refs} if isinstance(refs, list) else set()
    page_id = str(component["page_id"])
    ics_name = "page1" if page_id == "page1" else "page2_recovery"
    identity = component["component_id"]
    return {
        "safe_local_locators": _safe_refs(refs),
        "accepted_ics_component": f"evidence/{ics_name}.ics#{identity}" in values,
        "manifest_page_authority": f"policy/sync_manifest.json#pages.{page_id}" in values,
    }


def _normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    rows = plan.get("actions")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            refs = row.get("evidence_refs")
            normalized.append({
                "component_id": str(row.get("component_id", "")),
                "disposition": str(row.get("disposition", "")),
                "evidence_refs": sorted({str(ref) for ref in refs}) if isinstance(refs, list) else [],
            })
    normalized.sort(key=lambda row: row["component_id"])
    fallback = plan.get("fallback") if isinstance(plan.get("fallback"), dict) else {}
    return {
        "schema_version": plan.get("schema_version"),
        "recovery_id": plan.get("recovery_id"),
        "collection_id": plan.get("collection_id"),
        "source_checkpoint": plan.get("source_checkpoint"),
        # ``reason`` is validated for required business concepts, but prose is
        # not part of the recovery identity.  Equivalent operator wording must
        # therefore replay against the same semantic plan.
        "fallback": {key: fallback.get(key) for key in (
            "damaged_page", "selected_page", "selected_sha256", "expected_etag",
        )},
        "actions": normalized,
        "external_calendar_write_executed": plan.get("external_calendar_write_executed"),
    }


def _load_plan(name: str) -> tuple[dict[str, Any], str]:
    path = (ROOT / name).resolve()
    if path.parent != ROOT or not path.is_file():
        raise ValueError("plan must be a regular top-level workspace file")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    return plan, _digest(_normalized_plan(plan))


def _safe_refs(refs: Any) -> bool:
    return bool(isinstance(refs, list) and refs) and all(
        isinstance(ref, str)
        and not ref.startswith(("/", "http://", "https://"))
        and ".." not in Path(ref.split("#", 1)[0]).parts
        and ref.split("#", 1)[0] in {
            "evidence/page1.ics", "evidence/page2_recovery.ics", "policy/sync_manifest.json",
        }
        for ref in refs
    )


def _validate_plan(
    connection: sqlite3.Connection,
    plan: dict[str, Any],
) -> tuple[bool, dict[str, bool], dict[str, Any]]:
    manifest = _manifest()
    components = _accepted_components()
    component_map = {row["component_id"]: row for row in components}
    actual_map: dict[str, dict[str, Any]] = {}
    unique = isinstance(plan.get("actions"), list)
    duplicates: list[str] = []
    if isinstance(plan.get("actions"), list):
        for row in plan["actions"]:
            if not isinstance(row, dict):
                unique = False
                continue
            identity = str(row.get("component_id"))
            if identity in actual_map:
                unique = False
                duplicates.append(identity)
            actual_map[identity] = row
    coverage = unique and set(actual_map) == set(component_map)
    state = _effective_state(connection)
    action_feedback: list[dict[str, Any]] = []
    dispositions = coverage
    evidence = coverage
    for identity, row in actual_map.items():
        component = component_map.get(identity)
        known = component is not None
        disposition_ok = bool(
            known
            and _candidate_disposition_matches(component, state.get(identity), row.get("disposition"))
        )
        evidence_fields = (
            _evidence_feedback(component, row.get("evidence_refs"))
            if component is not None
            else {
                "safe_local_locators": _safe_refs(row.get("evidence_refs")),
                "accepted_ics_component": False,
                "manifest_page_authority": False,
            }
        )
        dispositions = dispositions and disposition_ok
        evidence = evidence and all(evidence_fields.values())
        action_feedback.append({
            "component_id": identity,
            "fields": {
                "component_id_known": known,
                "disposition_valid_for_observed_state": disposition_ok,
                "evidence_refs_is_nonempty_list": bool(
                    isinstance(row.get("evidence_refs"), list) and row["evidence_refs"]
                ),
            },
            "evidence_categories": evidence_fields,
        })
    page2 = manifest["pages"]["page2"]
    page1 = manifest["pages"]["page1"]
    checkpoint = connection.execute(
        "SELECT * FROM sync_checkpoint WHERE collection_id=?", (manifest["collection_id"],)
    ).fetchone()
    journal = connection.execute(
        "SELECT * FROM sync_journal WHERE recovery_id=?", (manifest["recovery_id"],)
    ).fetchone()
    fallback = plan.get("fallback")
    fallback_fields = {
        "damaged_page_is_manifest_damaged_path": isinstance(fallback, dict)
        and fallback.get("damaged_page") == page2["damaged_path"],
        "selected_page_is_manifest_fallback_path": isinstance(fallback, dict)
        and fallback.get("selected_page") == page2["fallback_path"],
        "selected_sha256_matches_fallback_file": isinstance(fallback, dict)
        and fallback.get("selected_sha256") == page2["fallback_sha256"],
        "expected_etag_is_selected_page_outgoing_etag": isinstance(fallback, dict)
        and fallback.get("expected_etag") == page2["etag_out"],
        "reason_cites_truncation_and_checksum": isinstance(fallback, dict)
        and isinstance(fallback.get("reason"), str)
        and all(term in fallback["reason"].casefold() for term in ("truncat", "checksum")),
    }
    fallback_ok = all(fallback_fields.values())
    identity_fields = {
        "schema_version": plan.get("schema_version") == 1,
        "recovery_id": plan.get("recovery_id") == manifest["recovery_id"],
        "collection_id": plan.get("collection_id") == manifest["collection_id"],
    }
    checks = {
        "identity": all(identity_fields.values()),
        "source_checkpoint": plan.get("source_checkpoint") == manifest["source_checkpoint"],
        "starting_checkpoint_and_journal": bool(
            checkpoint and journal
            and checkpoint["recovery_id"] == manifest["recovery_id"]
            and checkpoint["cursor"] == page1["cursor_in"]
            and checkpoint["collection_etag"] == page1["etag_in"]
            and checkpoint["source_checkpoint"] == manifest["source_checkpoint"]
            and checkpoint["phase"] == "prepared"
            and journal["phase"] == "prepared"
            and journal["source_checkpoint"] == manifest["source_checkpoint"]
            and journal["prepared_page"] == "page1"
        ),
        "fallback_chain": bool(fallback_ok),
        "component_coverage_and_dispositions": bool(dispositions),
        "local_evidence": bool(evidence),
        "offline_boundary": plan.get("external_calendar_write_executed") is False,
    }
    feedback = {
        "identity_fields": identity_fields,
        "source_checkpoint": {
            "matches_manifest_immutable_checkpoint": checks["source_checkpoint"],
        },
        "fallback_fields": fallback_fields,
        "actions": {
            "submitted_count": len(actual_map),
            "accepted_component_count": len(component_map),
            "coverage_complete": coverage,
            "missing_component_count": len(set(component_map) - set(actual_map)),
            "extra_submitted_component_ids": sorted(set(actual_map) - set(component_map)),
            "duplicate_submitted_component_ids": sorted(set(duplicates)),
            "submitted_objects": action_feedback,
        },
        "offline_boundary": {
            "external_calendar_write_executed_is_false": checks["offline_boundary"],
        },
    }
    return all(checks.values()), checks, feedback


def _row_payload(component: dict[str, Any], etag: str) -> tuple[Any, ...]:
    return (
        component["uid"], component["recurrence_id"], component["dtstart_utc"],
        component["dtend_utc"], component["tzid"], component["summary"],
        component["status"], component["rrule"], int(component["sequence"]), etag,
    )


def _semantic_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table in TABLES:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(columns[:2])
        rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]
        if table == "recovery_transactions":
            for row in rows:
                row.pop("semantic_state_sha256", None)
        result[table] = rows
    return result


def _database_digest(connection: sqlite3.Connection) -> str:
    return _digest(_semantic_snapshot(connection))


def inspect_state(_args: argparse.Namespace) -> int:
    manifest = _manifest()
    with _connect() as connection:
        payload = {
            "manifest": manifest,
            "checkpoint": [dict(row) for row in connection.execute("SELECT * FROM sync_checkpoint")],
            "journal": [dict(row) for row in connection.execute("SELECT * FROM sync_journal")],
            "rollback_rows": [dict(row) for row in connection.execute("SELECT * FROM rollback_rows")],
            "components": [dict(row) for row in connection.execute("SELECT * FROM events ORDER BY uid, recurrence_id")],
            "damaged_sha256": _sha(ROOT / manifest["pages"]["page2"]["damaged_path"]),
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def query_state(args: argparse.Namespace) -> int:
    allowed = {"events", "tombstones", "sync_checkpoint", "sync_ledger", "sync_journal", "rollback_rows", "recovery_transactions"}
    if args.table not in allowed:
        raise ValueError(f"unsupported table; choose one of {sorted(allowed)}")
    with _connect() as connection:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({args.table})")]
        order = ", ".join(columns[:2])
        rows = [dict(row) for row in connection.execute(f"SELECT * FROM {args.table} ORDER BY {order}")]
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


def preview(args: argparse.Namespace) -> int:
    plan, plan_sha = _load_plan(args.plan)
    with _connect() as connection:
        valid, checks, feedback = _validate_plan(connection, plan)
        before = _database_digest(connection)
    receipt = {
        "tool": "syncctl/1", "recovery_id": _manifest()["recovery_id"],
        "plan_sha256": plan_sha, "checks": checks, "feedback": feedback,
        "status": "pass" if valid else "fail",
        "database_sha256_before": before, "mutation_executed": False,
    }
    (ROOT / ".calendar_preview.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if valid else 2


def _apply(args: argparse.Namespace, replay_mode: bool = False) -> tuple[str, str, str]:
    plan, plan_sha = _load_plan(args.plan)
    manifest = _manifest()
    recovery_id = manifest["recovery_id"]
    with _connect() as connection:
        transaction = connection.execute(
            "SELECT * FROM recovery_transactions WHERE recovery_id=?", (recovery_id,)
        ).fetchone()
        if transaction:
            if transaction["source_checkpoint"] != manifest["source_checkpoint"] or transaction["plan_sha256"] != plan_sha:
                raise ValueError("conflicting replay for committed recovery identity")
            state_sha = _database_digest(connection)
            if transaction["semantic_state_sha256"] != state_sha:
                raise ValueError("committed recovery state drift")
            status = "idempotent_replay"
        else:
            valid, checks, _feedback = _validate_plan(connection, plan)
            if not valid:
                raise ValueError(f"plan validation failed: {[key for key, value in checks.items() if not value]}")
            connection.execute("BEGIN IMMEDIATE")
            rollback = connection.execute("SELECT * FROM rollback_rows WHERE restored=0").fetchall()
            for row in rollback:
                if row["table_name"] != "events":
                    raise ValueError("unsupported rollback table")
                before = json.loads(row["before_json"])
                connection.execute(
                    "INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(before[key] for key in (
                        "uid", "recurrence_id", "dtstart_utc", "dtend_utc", "tzid",
                        "summary", "status", "rrule", "sequence", "source_etag",
                    )),
                )
                connection.execute("UPDATE rollback_rows SET restored=1 WHERE record_key=?", (row["record_key"],))
            actions = {row["component_id"]: row["disposition"] for row in plan["actions"]}
            pages = manifest["pages"]
            for component in _accepted_components():
                identity = component["component_id"]
                disposition = actions[identity]
                etag = pages[component["page_id"]]["etag_out"]
                if disposition in {"upsert_master", "upsert_override", "upsert_event", "insert_event"}:
                    connection.execute("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", _row_payload(component, etag))
                    connection.execute("DELETE FROM tombstones WHERE uid=? AND recurrence_id=?", (component["uid"], component["recurrence_id"]))
                elif disposition in {"cancel_occurrence", "tombstone_event"}:
                    connection.execute("DELETE FROM events WHERE uid=? AND recurrence_id=?", (component["uid"], component["recurrence_id"]))
                    connection.execute(
                        "INSERT OR REPLACE INTO tombstones VALUES (?, ?, ?, ?)",
                        (component["uid"], component["recurrence_id"], component["sequence"], etag),
                    )
                connection.execute(
                    "INSERT INTO sync_ledger VALUES (?, ?, ?, ?, ?, ?)",
                    (identity, disposition, component["page_id"], component["sequence"], etag, NOW),
                )
            connection.execute(
                "UPDATE sync_checkpoint SET cursor=?, collection_etag=?, source_checkpoint=?, phase='committed' WHERE collection_id=?",
                (pages["page2"]["cursor_out"], pages["page2"]["etag_out"], manifest["source_checkpoint"], manifest["collection_id"]),
            )
            connection.execute(
                "UPDATE sync_journal SET phase='committed', plan_sha256=?, recovered_from_interrupt=1, committed_at=? WHERE recovery_id=?",
                (plan_sha, NOW, recovery_id),
            )
            connection.execute(
                "INSERT INTO recovery_transactions(recovery_id, source_checkpoint, plan_sha256, semantic_state_sha256, action_count, committed_at) VALUES (?, ?, ?, '', ?, ?)",
                (recovery_id, manifest["source_checkpoint"], plan_sha, len(actions), NOW),
            )
            state_sha = _database_digest(connection)
            connection.execute(
                "UPDATE recovery_transactions SET semantic_state_sha256=? WHERE recovery_id=?",
                (state_sha, recovery_id),
            )
            connection.commit()
            status = "committed"
    if replay_mode:
        report = {
            "tool": "syncctl/1", "recovery_id": recovery_id, "status": status,
            "source_checkpoint": manifest["source_checkpoint"], "plan_sha256": plan_sha,
            "semantic_database_sha256": state_sha, "mutation_executed": status == "committed",
        }
        (ROOT / "state/replay_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"recovery_id": recovery_id, "status": status, "plan_sha256": plan_sha, "semantic_database_sha256": state_sha}, indent=2, sort_keys=True))
    return status, plan_sha, state_sha


def apply_plan(args: argparse.Namespace) -> int:
    _apply(args)
    return 0


def replay_plan(args: argparse.Namespace) -> int:
    _apply(args, replay_mode=True)
    return 0


def verify_state(_args: argparse.Namespace) -> int:
    manifest = _manifest()
    with _connect() as connection:
        transaction = connection.execute("SELECT * FROM recovery_transactions WHERE recovery_id=?", (manifest["recovery_id"],)).fetchone()
        checkpoint = connection.execute("SELECT * FROM sync_checkpoint WHERE collection_id=?", (manifest["collection_id"],)).fetchone()
        journal = connection.execute("SELECT * FROM sync_journal WHERE recovery_id=?", (manifest["recovery_id"],)).fetchone()
        ledger_count = connection.execute("SELECT COUNT(*) FROM sync_ledger").fetchone()[0]
        tombstone_count = connection.execute("SELECT COUNT(*) FROM tombstones").fetchone()[0]
        state_sha = _database_digest(connection)
        checks = {
            "transaction_present": transaction is not None,
            "checkpoint_advanced": bool(checkpoint and checkpoint["cursor"] == manifest["pages"]["page2"]["cursor_out"] and checkpoint["collection_etag"] == manifest["pages"]["page2"]["etag_out"]),
            "journal_recovered": bool(journal and journal["phase"] == "committed" and journal["recovered_from_interrupt"] == 1),
            "component_ledger_complete": ledger_count == len(_accepted_components()),
            "tombstones_present": tombstone_count >= 2,
            "transaction_digest_matches": bool(transaction and transaction["semantic_state_sha256"] == state_sha),
        }
        plan_sha = transaction["plan_sha256"] if transaction else ""
    receipt = {
        "tool": "syncctl/1", "recovery_id": manifest["recovery_id"],
        "source_checkpoint": manifest["source_checkpoint"], "plan_sha256": plan_sha,
        "semantic_database_sha256": state_sha, "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
        "external_calendar_write_executed": False,
    }
    (ROOT / "state/calendar_verification.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 2


def stage(args: argparse.Namespace) -> int:
    plan, plan_sha = _load_plan(args.plan)
    verification = json.loads((ROOT / "state/calendar_verification.json").read_text())
    if verification.get("status") != "pass" or verification.get("plan_sha256") != plan_sha:
        raise ValueError("fresh passing verification for this plan is required")
    manifest = _manifest()
    unsigned = {
        "receipt_type": "local_calendar_recovery_stage",
        "recovery_id": manifest["recovery_id"], "collection_id": manifest["collection_id"],
        "source_checkpoint": manifest["source_checkpoint"], "plan_sha256": plan_sha,
        "semantic_database_sha256": verification["semantic_database_sha256"],
        "verification_sha256": _sha(ROOT / "state/calendar_verification.json"),
        "phase": "staged_pending_calendar_owner_review",
        "external_calendar_write_executed": False,
    }
    receipt = dict(unsigned)
    receipt["stage_token"] = _digest(unsigned)
    path = ROOT / "state/recovery_receipt.json"
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != serialized:
        raise ValueError("conflicting staged receipt")
    path.write_text(serialized)
    print(serialized, end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline RFC 5545 calendar sync recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="inspect checkpoint, journal, replica, and manifest").set_defaults(func=inspect_state)
    query = sub.add_parser("query", help="query an allowed SQLite table")
    query.add_argument("table")
    query.set_defaults(func=query_state)
    for name, function in (("preview", preview), ("apply", apply_plan), ("stage", stage), ("replay", replay_plan)):
        command = sub.add_parser(name)
        command.add_argument("plan")
        command.set_defaults(func=function)
    sub.add_parser("verify").set_defaults(func=verify_state)
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

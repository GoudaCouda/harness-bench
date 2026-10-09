#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "closeout.db"
CONTRACTS = ROOT / "contracts.csv"
EVENTS = ROOT / "evidence_events.csv"
POLICY = ROOT / "closeout_policy.md"
VERIFICATION = ROOT / "closeout_verification.json"
STAGE = ROOT / "closeout_stage_receipt.json"
NOW = "2026-08-19T12:00:00Z"
SOURCE_PATHS = (CONTRACTS, EVENTS, POLICY)
AUTHORITIES = {
    "acceptance": "acceptance_signed",
    "legal": "legal_signed",
    "invoice": "finance_signed",
    "funds": "finance_signed",
}
TABLES = (
    "review_meta",
    "contract_state",
    "closeout_audit",
    "review_journal",
    "review_transactions",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_manifest() -> dict[str, str]:
    return {path.name: _sha(path) for path in SOURCE_PATHS}


def _source_checkpoint() -> str:
    return _digest(_source_manifest())


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _table_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError(f"unsupported table: {table}")
    order = {
        "review_meta": "review_id",
        "contract_state": "contract_id",
        "closeout_audit": "audit_sequence",
        "review_journal": "review_id",
        "review_transactions": "review_id",
    }[table]
    return [
        dict(row)
        for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    ]


def _snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    return {table: _table_rows(connection, table) for table in TABLES}


def _logical_state_digest(connection: sqlite3.Connection) -> str:
    return _digest(_snapshot(connection))


def _contracts() -> dict[str, dict[str, str]]:
    with CONTRACTS.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        contract_id = str(row.get("contract_id", "")).strip()
        if not contract_id or contract_id in result:
            raise ValueError("contracts.csv contains a blank or duplicate contract_id")
        if str(row.get("physical_complete", "")).strip().casefold() not in {
            "true",
            "false",
        }:
            raise ValueError(f"invalid physical_complete for {contract_id}")
        date.fromisoformat(str(row["option_end"]))
        result[contract_id] = {
            key: str(value or "").strip() for key, value in row.items()
        }
    return result


def _events() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    with EVENTS.open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    seen_sequences: set[int] = set()
    seen_ids: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for raw in source:
        sequence = int(str(raw["event_sequence"]))
        event_id = str(raw["event_id"]).strip()
        if sequence in seen_sequences or event_id in seen_ids:
            raise ValueError("evidence_events.csv contains duplicate sequence or event id")
        seen_sequences.add(sequence)
        seen_ids.add(event_id)
        row = {key: str(value or "").strip() for key, value in raw.items()}
        row["event_sequence"] = sequence
        ordered.append(row)
    ordered.sort(key=lambda row: int(row["event_sequence"]))
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in ordered:
        by_contract.setdefault(str(row["contract_id"]), []).append(row)
    return ordered, by_contract


def _metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = _table_rows(connection, "review_meta")
    if len(rows) != 1:
        raise ValueError("closeout.db must contain exactly one review_meta row")
    return rows[0]


def _latest_authoritative(
    rows: list[dict[str, Any]], evidence_type: str
) -> dict[str, Any] | None:
    authority = AUTHORITIES[evidence_type]
    matching = [
        row
        for row in rows
        if row["evidence_type"] == evidence_type and row["authority"] == authority
    ]
    return matching[-1] if matching else None


def _required_evidence(
    contract_id: str, rows: list[dict[str, Any]]
) -> list[str]:
    refs = [
        f"contracts.csv#{contract_id}",
        "closeout_policy.md#gate-precedence",
    ]
    refs.extend(f"evidence_events.csv#{row['event_id']}" for row in rows)
    return sorted(refs)


def _derive_decisions(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    meta = _metadata(connection)
    as_of = date.fromisoformat(str(meta["as_of_date"]))
    contracts = _contracts()
    _, by_contract = _events()
    unknown = set(by_contract) - set(contracts)
    if unknown:
        raise ValueError(f"events reference unknown contracts: {sorted(unknown)}")
    decisions: dict[str, dict[str, Any]] = {}
    for contract_id, contract in contracts.items():
        rows = by_contract.get(contract_id, [])
        acceptance = _latest_authoritative(rows, "acceptance")
        legal = _latest_authoritative(rows, "legal")
        invoice = _latest_authoritative(rows, "invoice")
        funds = _latest_authoritative(rows, "funds")
        physical_complete = contract["physical_complete"].casefold() == "true"
        if not physical_complete or not acceptance or acceptance["status"] != "complete":
            disposition, owner, action = "hold", "program", "complete_acceptance"
        elif not legal or legal["status"] != "clear":
            disposition, owner, action = "hold", "legal", "resolve_legal_hold"
        elif date.fromisoformat(contract["option_end"]) > as_of:
            disposition, owner, action = "hold", "contracts", "await_option_expiry"
        elif not invoice or invoice["status"] != "complete":
            disposition, owner, action = "hold", "finance", "obtain_final_invoice"
        elif not funds or funds["status"] != "complete":
            disposition, owner, action = "hold", "finance", "complete_deobligation"
        else:
            disposition, owner, action = (
                "ready_for_controller",
                "controller",
                "approve_closeout_package",
            )
        decisions[contract_id] = {
            "contract_id": contract_id,
            "disposition": disposition,
            "owner": owner,
            "next_action": action,
            "evidence_refs": _required_evidence(contract_id, rows),
        }
    return decisions


def _normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    decisions = []
    rows = plan.get("decisions")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            decisions.append(
                {
                    "contract_id": str(row.get("contract_id", "")),
                    "disposition": str(row.get("disposition", "")),
                    "owner": str(row.get("owner", "")),
                    "next_action": str(row.get("next_action", "")),
                }
            )
    decisions.sort(key=lambda row: row["contract_id"])
    return {
        "schema_version": plan.get("schema_version"),
        "review_id": plan.get("review_id"),
        "source_checkpoint_sha256": plan.get("source_checkpoint_sha256"),
        "decisions": decisions,
        "external_actions_executed": plan.get("external_actions_executed"),
    }


def _load_plan(name: str) -> tuple[dict[str, Any], str]:
    relative = Path(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) != 1
    ):
        raise ValueError("plan must be one workspace-local filename")
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("plan must be one regular workspace file")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    return plan, _digest(_normalized_plan(plan))


def _validate_plan(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    meta = _metadata(connection)
    expected = _derive_decisions(connection)
    rows = plan.get("decisions")
    actual: dict[str, dict[str, str]] = {}
    refs: dict[str, set[str]] = {}
    unique_and_structured = isinstance(rows, list)
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("evidence_refs"), list):
                unique_and_structured = False
                continue
            contract_id = str(row.get("contract_id", ""))
            if contract_id in actual:
                unique_and_structured = False
            actual[contract_id] = {
                "disposition": str(row.get("disposition", "")),
                "owner": str(row.get("owner", "")),
                "next_action": str(row.get("next_action", "")),
            }
            values = [str(value) for value in row["evidence_refs"]]
            if len(values) != len(set(values)):
                unique_and_structured = False
            refs[contract_id] = set(values)
    expected_core = {
        key: {
            "disposition": value["disposition"],
            "owner": value["owner"],
            "next_action": value["next_action"],
        }
        for key, value in expected.items()
    }
    missing_evidence = {
        contract_id: sorted(set(value["evidence_refs"]) - refs.get(contract_id, set()))
        for contract_id, value in expected.items()
        if not set(value["evidence_refs"]).issubset(refs.get(contract_id, set()))
    }
    unexpected_evidence = {
        contract_id: sorted(
            refs.get(contract_id, set()) - set(value["evidence_refs"])
        )
        for contract_id, value in expected.items()
        if refs.get(contract_id, set()) - set(value["evidence_refs"])
    }
    invalid_refs = {
        contract_id: sorted(
            ref
            for ref in values
            if not ref.startswith(
                ("contracts.csv#", "evidence_events.csv#", "closeout_policy.md#")
            )
            or ".." in ref
            or ref.startswith("/")
        )
        for contract_id, values in refs.items()
    }
    invalid_refs = {key: value for key, value in invalid_refs.items() if value}
    decision_errors = {
        key: {"expected": expected_core.get(key), "actual": actual.get(key)}
        for key in sorted(set(expected_core) | set(actual))
        if expected_core.get(key) != actual.get(key)
    }
    checks: dict[str, Any] = {
        "schema_version": plan.get("schema_version") == 1,
        "review_identity": plan.get("review_id") == meta["review_id"],
        "source_checkpoint": plan.get("source_checkpoint_sha256")
        == _source_checkpoint()
        == meta["source_checkpoint_sha256"],
        "one_decision_per_contract": unique_and_structured
        and set(actual) == set(expected),
        "policy_decisions": not decision_errors,
        "exact_local_evidence": not missing_evidence
        and not unexpected_evidence
        and not invalid_refs,
        "offline_boundary": plan.get("external_actions_executed") is False,
    }
    detail = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "decision_errors": decision_errors,
        "missing_evidence": missing_evidence,
        "unexpected_evidence": unexpected_evidence,
        "invalid_evidence_refs": invalid_refs,
    }
    return all(checks.values()), detail


def _current_journal(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = _table_rows(connection, "review_journal")
    if len(rows) != 1:
        raise ValueError("closeout.db must contain exactly one review journal")
    return rows[0]


def _prefix_matches(
    connection: sqlite3.Connection, decisions: dict[str, dict[str, Any]]
) -> bool:
    journal = _current_journal(connection)
    count = int(journal["applied_count"])
    if journal["phase"] != "prepared" or count != 2:
        return False
    expected = [decisions[key] for key in sorted(decisions)[:count]]
    audit = _table_rows(connection, "closeout_audit")
    if len(audit) != count:
        return False
    states = {
        row["contract_id"]: row for row in _table_rows(connection, "contract_state")
    }
    for sequence, decision in enumerate(expected, 1):
        row = audit[sequence - 1]
        core = (
            decision["contract_id"],
            decision["disposition"],
            decision["owner"],
            decision["next_action"],
            json.dumps(decision["evidence_refs"], separators=(",", ":")),
        )
        actual = (
            row["contract_id"],
            row["disposition"],
            row["owner"],
            row["next_action"],
            row["evidence_refs_json"],
        )
        state = states.get(decision["contract_id"], {})
        state_actual = (
            state.get("contract_id"),
            state.get("disposition"),
            state.get("owner"),
            state.get("next_action"),
            state.get("evidence_refs_json"),
        )
        if actual != core or state_actual != core:
            return False
    remaining = sorted(decisions)[count:]
    return all(states[key]["disposition"] == "pending" for key in remaining)


def _verification_checks(connection: sqlite3.Connection) -> dict[str, bool]:
    expected = _derive_decisions(connection)
    meta = _metadata(connection)
    states = {
        row["contract_id"]: row for row in _table_rows(connection, "contract_state")
    }
    state_ok = set(states) == set(expected)
    for contract_id, decision in expected.items():
        row = states.get(contract_id, {})
        state_ok &= (
            row.get("disposition") == decision["disposition"]
            and row.get("owner") == decision["owner"]
            and row.get("next_action") == decision["next_action"]
            and row.get("evidence_refs_json")
            == json.dumps(decision["evidence_refs"], separators=(",", ":"))
        )
    audit = _table_rows(connection, "closeout_audit")
    audit_ok = len(audit) == len(expected)
    for sequence, contract_id in enumerate(sorted(expected), 1):
        decision = expected[contract_id]
        row = audit[sequence - 1] if len(audit) >= sequence else {}
        audit_ok &= (
            row.get("audit_sequence") == sequence
            and row.get("review_id") == meta["review_id"]
            and row.get("contract_id") == contract_id
            and row.get("disposition") == decision["disposition"]
            and row.get("owner") == decision["owner"]
            and row.get("next_action") == decision["next_action"]
            and row.get("evidence_refs_json")
            == json.dumps(decision["evidence_refs"], separators=(",", ":"))
        )
    journal = _current_journal(connection)
    transactions = _table_rows(connection, "review_transactions")
    transaction_ok = (
        journal["phase"] == "committed"
        and int(journal["applied_count"]) == len(expected)
        and journal["source_checkpoint_sha256"] == _source_checkpoint()
        and isinstance(journal["semantic_plan_sha256"], str)
        and len(journal["semantic_plan_sha256"]) == 64
        and len(transactions) == 1
        and transactions[0]["review_id"] == meta["review_id"]
        and transactions[0]["source_checkpoint_sha256"] == _source_checkpoint()
        and transactions[0]["semantic_plan_sha256"]
        == journal["semantic_plan_sha256"]
        and int(transactions[0]["action_count"]) == len(expected)
    )
    return {
        "source_checkpoint_matches": meta["source_checkpoint_sha256"]
        == _source_checkpoint(),
        "contract_state_matches_policy": bool(state_ok),
        "ordered_audit_is_complete": bool(audit_ok),
        "single_recovery_transaction": bool(transaction_ok),
        "external_actions_not_executed": int(meta["external_actions_executed"]) == 0,
    }


def command_inspect(_: argparse.Namespace) -> int:
    with _connect() as connection:
        meta = _metadata(connection)
        journal = _current_journal(connection)
        ordered, _ = _events()
        payload = {
            "review_id": meta["review_id"],
            "as_of_date": meta["as_of_date"],
            "source_checkpoint_sha256": _source_checkpoint(),
            "source_manifest": _source_manifest(),
            "journal": journal,
            "contract_state": _table_rows(connection, "contract_state"),
            "audit_prefix": _table_rows(connection, "closeout_audit"),
            "ordered_event_ids": [row["event_id"] for row in ordered],
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_query(args: argparse.Namespace) -> int:
    contracts = _contracts()
    ordered, by_contract = _events()
    if args.contract:
        if args.contract not in contracts:
            print(json.dumps({"status": "fail", "error": "unknown_contract"}))
            return 2
        payload = {
            "contract": contracts[args.contract],
            "ordered_events": by_contract.get(args.contract, []),
        }
    else:
        payload = {"contracts": list(contracts.values()), "ordered_events": ordered}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_preview(args: argparse.Namespace) -> int:
    try:
        plan, semantic_sha = _load_plan(args.plan)
        with _connect() as connection:
            valid, detail = _validate_plan(connection, plan)
            detail["semantic_plan_sha256"] = semantic_sha
            detail["source_checkpoint_sha256"] = _source_checkpoint()
        print(json.dumps(detail, indent=2, sort_keys=True))
        return 0 if valid else 2
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


def _apply(plan_name: str, *, replay_only: bool) -> int:
    try:
        plan, semantic_sha = _load_plan(plan_name)
        connection = _connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            meta = _metadata(connection)
            journal = _current_journal(connection)
            if journal["phase"] == "committed":
                if (
                    plan.get("review_id") != meta["review_id"]
                    or plan.get("source_checkpoint_sha256") != _source_checkpoint()
                    or semantic_sha != journal["semantic_plan_sha256"]
                ):
                    connection.rollback()
                    print(
                        json.dumps(
                            {"status": "conflict", "error": "semantic_plan_conflict"}
                        )
                    )
                    return 2
                valid, detail = _validate_plan(connection, plan)
                connection.rollback()
                if not valid:
                    print(json.dumps(detail, indent=2, sort_keys=True))
                    return 2
                print(
                    json.dumps(
                        {
                            "status": "idempotent",
                            "review_id": meta["review_id"],
                            "semantic_plan_sha256": semantic_sha,
                        },
                        indent=2,
                    )
                )
                return 0
            if replay_only:
                connection.rollback()
                print(json.dumps({"status": "fail", "error": "review_not_committed"}))
                return 2
            valid, detail = _validate_plan(connection, plan)
            if not valid:
                connection.rollback()
                print(json.dumps(detail, indent=2, sort_keys=True))
                return 2
            decisions = _derive_decisions(connection)
            if not _prefix_matches(connection, decisions):
                connection.rollback()
                print(
                    json.dumps(
                        {"status": "fail", "error": "interrupted_audit_prefix_mismatch"}
                    )
                )
                return 2
            start = int(journal["applied_count"])
            for sequence, contract_id in enumerate(sorted(decisions), 1):
                if sequence <= start:
                    continue
                decision = decisions[contract_id]
                refs_json = json.dumps(
                    decision["evidence_refs"], separators=(",", ":")
                )
                connection.execute(
                    "UPDATE contract_state SET disposition=?, owner=?, next_action=?, "
                    "evidence_refs_json=?, decision_sequence=? WHERE contract_id=?",
                    (
                        decision["disposition"],
                        decision["owner"],
                        decision["next_action"],
                        refs_json,
                        sequence,
                        contract_id,
                    ),
                )
                connection.execute(
                    "INSERT INTO closeout_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        sequence,
                        meta["review_id"],
                        contract_id,
                        decision["disposition"],
                        decision["owner"],
                        decision["next_action"],
                        refs_json,
                        NOW,
                    ),
                )
            connection.execute(
                "UPDATE review_journal SET phase='committed', applied_count=?, "
                "semantic_plan_sha256=?, updated_at=? WHERE review_id=?",
                (len(decisions), semantic_sha, NOW, meta["review_id"]),
            )
            connection.execute(
                "INSERT INTO review_transactions VALUES (?, ?, ?, ?, ?)",
                (
                    meta["review_id"],
                    _source_checkpoint(),
                    semantic_sha,
                    len(decisions),
                    NOW,
                ),
            )
            connection.commit()
            print(
                json.dumps(
                    {
                        "status": "applied",
                        "review_id": meta["review_id"],
                        "resumed_after_audit_sequence": start,
                        "new_audit_rows": len(decisions) - start,
                        "semantic_plan_sha256": semantic_sha,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


def command_apply(args: argparse.Namespace) -> int:
    return _apply(args.plan, replay_only=False)


def command_replay(args: argparse.Namespace) -> int:
    return _apply(args.plan, replay_only=True)


def command_verify(_: argparse.Namespace) -> int:
    try:
        with _connect() as connection:
            checks = _verification_checks(connection)
            payload = {
                "tool": "closeoutctl/2",
                "review_id": _metadata(connection)["review_id"],
                "status": "pass" if all(checks.values()) else "fail",
                "checks": checks,
                "source_checkpoint_sha256": _source_checkpoint(),
                "logical_state_sha256": _logical_state_digest(connection),
                "external_actions_executed": False,
            }
        VERIFICATION.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "pass" else 2
    except (OSError, UnicodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


def command_stage(args: argparse.Namespace) -> int:
    try:
        plan, semantic_sha = _load_plan(args.plan)
        with _connect() as connection:
            valid, detail = _validate_plan(connection, plan)
            checks = _verification_checks(connection)
            meta = _metadata(connection)
            journal = _current_journal(connection)
            if (
                not valid
                or not all(checks.values())
                or semantic_sha != journal["semantic_plan_sha256"]
            ):
                print(
                    json.dumps(
                        {
                            "status": "fail",
                            "error": "plan_or_verified_state_mismatch",
                            "plan_checks": detail["checks"],
                            "state_checks": checks,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 2
            verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
            if (
                verification.get("status") != "pass"
                or verification.get("logical_state_sha256")
                != _logical_state_digest(connection)
            ):
                print(json.dumps({"status": "fail", "error": "verification_is_stale"}))
                return 2
            unsigned = {
                "receipt_type": "local_contract_closeout_stage",
                "review_id": meta["review_id"],
                "phase": "staged_pending_controller_approval",
                "source_checkpoint_sha256": _source_checkpoint(),
                "semantic_plan_sha256": semantic_sha,
                "logical_state_sha256": _logical_state_digest(connection),
                "verification_sha256": _sha(VERIFICATION),
                "external_actions_executed": False,
            }
            receipt = dict(unsigned)
            receipt["stage_token"] = _digest(unsigned)
        encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if STAGE.exists():
            if STAGE.read_text(encoding="utf-8") != encoded:
                print(json.dumps({"status": "conflict", "error": "stage_receipt_conflict"}))
                return 2
            print(
                json.dumps(
                    {"status": "idempotent", **receipt}, indent=2, sort_keys=True
                )
            )
            return 0
        STAGE.write_text(encoded, encoding="utf-8")
        print(json.dumps({"status": "staged", **receipt}, indent=2, sort_keys=True))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover and stage a local contract-closeout review"
    )
    sub = parser.add_subparsers(required=True)
    inspect = sub.add_parser("inspect", help="show checkpoint and interrupted state")
    inspect.set_defaults(func=command_inspect)
    query = sub.add_parser("query", help="read contracts and sequence-ordered evidence")
    query.add_argument("--contract")
    query.set_defaults(func=command_query)
    for name, function in (
        ("preview", command_preview),
        ("apply", command_apply),
        ("replay", command_replay),
        ("stage", command_stage),
    ):
        command = sub.add_parser(name)
        command.add_argument("plan")
        command.set_defaults(func=function)
    verify = sub.add_parser("verify", help="verify the local durable state")
    verify.set_defaults(func=command_verify)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

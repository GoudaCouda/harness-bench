#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/formulary.db"
POLICY = ROOT / "policy/formulary_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
EVENTS = ROOT / "evidence/benefit_events.jsonl"
PLAN_FIELDS = {
    "schema_version",
    "recovery_id",
    "source_checkpoint",
    "rx_decisions",
    "event_dispositions",
    "totals",
    "external_actions_executed",
}
DECISION_FIELDS = {
    "rx_id",
    "member_id",
    "current_product_code",
    "target_product_code",
    "disposition",
    "final_local_state",
    "effective_rule_ids",
    "invalid_document_ids",
    "allergy_conflict_codes",
    "blocking_reasons",
    "local_mutations",
    "next_local_action",
    "evidence_refs",
}
EVENT_FIELDS = {"delivery_id", "event_id", "rx_id", "source_sequence", "disposition"}
TOTAL_FIELDS = {
    "active_prescriptions",
    "ready_prescriptions",
    "held_prescriptions",
    "preserved_dispensed_prescriptions",
    "preserved_cancelled_prescriptions",
}
SET_FIELDS = {
    "effective_rule_ids",
    "invalid_document_ids",
    "allergy_conflict_codes",
    "blocking_reasons",
    "local_mutations",
    "evidence_refs",
}
QUERY_TABLES = {
    "system_state": "key",
    "members": "member_id",
    "products": "product_code",
    "prescriptions": "rx_id",
    "formulary_rules": "rule_id",
    "step_records": "member_id,step_code",
    "authorization_register": "document_id",
    "review_runs": "recovery_id",
    "recovery_journal": "journal_id",
    "rx_projections": "recovery_id,rx_id",
}


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _rows(con: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = con.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _baseline() -> dict[str, Any]:
    with sqlite3.connect(DB) as con:
        prescriptions = {
            row["rx_id"]: row for row in _rows(con, "prescriptions", "rx_id")
        }
        runs = {
            row["recovery_id"]: row for row in _rows(con, "review_runs", "recovery_id")
        }
        for journal in _rows(con, "recovery_journal", "journal_id"):
            if (
                runs.get(journal["recovery_id"], {}).get("status") == "interrupted"
                and not journal["restored"]
            ):
                row = dict(prescriptions[journal["rx_id"]])
                row.update(json.loads(journal["before_json"]))
                prescriptions[journal["rx_id"]] = row
        return {
            "source_revision": int(
                con.execute(
                    "SELECT value FROM system_state WHERE key='source_revision'"
                ).fetchone()[0]
            ),
            "members": _rows(con, "members", "member_id"),
            "products": _rows(con, "products", "product_code"),
            "prescriptions": [prescriptions[key] for key in sorted(prescriptions)],
            "formulary_rules": _rows(con, "formulary_rules", "rule_id"),
            "step_records": _rows(con, "step_records", "member_id,step_code"),
            "authorization_register": _rows(
                con, "authorization_register", "document_id"
            ),
        }


def _deliveries() -> list[dict[str, Any]]:
    result = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("event delivery must be an object")
        result.append(value)
    return result


def _sources_valid() -> tuple[bool, list[str]]:
    changed = []
    files = _load(MANIFEST).get("files", {})
    if not isinstance(files, dict):
        return False, ["policy/source_manifest.json#files"]
    for relative, expected in files.items():
        try:
            actual = _digest((ROOT / str(relative)).read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(relative))
    return not changed, changed


def _normalized(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    decisions = []
    for raw in (
        plan.get("rx_decisions", [])
        if isinstance(plan.get("rx_decisions"), list)
        else []
    ):
        if isinstance(raw, dict):
            row = dict(raw)
            for field in SET_FIELDS:
                if isinstance(row.get(field), list):
                    row[field] = sorted(str(item) for item in row[field])
            decisions.append(row)
    result["rx_decisions"] = sorted(decisions, key=lambda row: str(row.get("rx_id")))
    events = plan.get("event_dispositions")
    result["event_dispositions"] = sorted(
        [dict(row) for row in events if isinstance(row, dict)]
        if isinstance(events, list)
        else [],
        key=lambda row: str(row.get("delivery_id")),
    )
    return result


def _checkpoint(state: dict[str, Any]) -> str:
    payload = {
        "source_revision": state["source_revision"],
        "members": state["members"],
        "products": state["products"],
        "prescriptions": [
            {key: value for key, value in row.items() if not key.startswith("local_")}
            for row in state["prescriptions"]
        ],
        "formulary_rules": state["formulary_rules"],
        "step_records": state["step_records"],
        "authorization_register": state["authorization_register"],
        "policy_sha256": _digest(POLICY.read_bytes()),
        "events_sha256": _digest(EVENTS.read_bytes()),
    }
    return "sha256:" + _digest(_canonical(payload))


def _event_status(
    index: int,
    events: list[dict[str, Any]],
    prescriptions: dict[str, dict[str, Any]],
    protected: set[str],
) -> str:
    row = events[index]
    group = [
        (
            position,
            _digest(
                _canonical(
                    {key: value for key, value in other.items() if key != "delivery_id"}
                )
            ),
        )
        for position, other in enumerate(events)
        if other.get("event_id") == row.get("event_id")
    ]
    if len({item[1] for item in group}) > 1:
        return "event_identity_collision_quarantined"
    if index != min(item[0] for item in group):
        return "duplicate_delivery_ignored"
    for position, other in enumerate(events):
        if (
            position != index
            and other.get("rx_id") == row.get("rx_id")
            and other.get("source_sequence") == row.get("source_sequence")
            and other.get("event_id") != row.get("event_id")
        ):
            peer_group = [
                (i, candidate)
                for i, candidate in enumerate(events)
                if candidate.get("event_id") == other.get("event_id")
            ]
            peer_hashes = {
                _digest(
                    _canonical(
                        {
                            key: value
                            for key, value in candidate.items()
                            if key != "delivery_id"
                        }
                    )
                )
                for _, candidate in peer_group
            }
            if len(peer_hashes) == 1 and position == min(
                item[0] for item in peer_group
            ):
                return "sequence_conflict_quarantined"
    rx = prescriptions.get(str(row.get("rx_id", "")))
    if rx is None:
        return "unknown_prescription_ignored"
    return "protected_boundary_ignored" if rx["status"] in protected else "applied"


def _effective_rule(
    rules: list[dict[str, Any]], plan_id: str, product: str, at: str
) -> dict[str, Any] | None:
    eligible = [
        row
        for row in rules
        if row["plan_id"] == plan_id
        and row["product_code"] == product
        and row["effective_from"] <= at
        and (row["effective_to"] is None or at < row["effective_to"])
    ]
    eligible.sort(key=lambda row: (row["effective_from"], row["rule_id"]))
    return eligible[-1] if eligible else None


def _decision_mismatches(
    actual: dict[str, Any],
    rx: dict[str, Any],
    state: dict[str, Any],
    policy: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[str]:
    members = {row["member_id"]: row for row in state["members"]}
    products = {row["product_code"]: row for row in state["products"]}
    prescriptions = {row["rx_id"]: row for row in state["prescriptions"]}
    authorizations = {row["rx_id"]: row for row in state["authorization_register"]}
    steps = {(row["member_id"], row["step_code"]) for row in state["step_records"]}
    member = members[rx["member_id"]]
    rule = _effective_rule(
        state["formulary_rules"],
        member["plan_id"],
        rx["current_product_code"],
        rx["prescribed_at"],
    )
    target = rx["current_product_code"] if rule is None else rule["target_product_code"]
    effective = [] if rule is None else [rule["rule_id"]]
    invalid_documents: list[str] = []
    allergy_conflicts: list[str] = []
    blockers: list[str] = []
    refs = {
        f"state/formulary.db#prescriptions:{rx['rx_id']}",
        f"state/formulary.db#members:{rx['member_id']}",
        "policy/formulary_policy.json#hold_precedence",
    }
    if rule is None:
        blockers.append(f"missing_effective_rule:{rx['rx_id']}")
    else:
        refs.add(f"state/formulary.db#formulary_rules:{rule['rule_id']}")
        target_product = products.get(target)
        allergy_conflicts = sorted(
            set(json.loads(member["allergy_codes_json"]))
            & (
                set(json.loads(target_product["excipient_codes_json"]))
                if target_product
                else set()
            )
        )
        if rule["requires_pa"]:
            document = authorizations.get(rx["rx_id"])
            valid = False
            if document:
                refs.add(f"{document['local_path']}#{document['document_id']}")
                try:
                    source = _load(ROOT / document["local_path"])
                    valid = bool(
                        document["signed"]
                        and _digest((ROOT / document["local_path"]).read_bytes())
                        == document["sha256"]
                        and source.get("kind") == "prior_authorization"
                        and source.get("rx_id") == rx["rx_id"]
                        and source.get("approved") is True
                        and str(source.get("valid_through", "")) > policy["as_of_utc"]
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    valid = False
            if not valid:
                invalid_documents.append(
                    document["document_id"]
                    if document
                    else f"missing_prior_authorization:{rx['rx_id']}"
                )
    if rx["status"] == "dispensed":
        disposition = final_state = "dispensed_boundary_preserved"
        target, action = rx["current_product_code"], "none"
        effective, invalid_documents, allergy_conflicts, blockers = [], [], [], []
    elif rx["status"] == "cancelled":
        disposition = final_state = "cancelled_boundary_preserved"
        target, action = rx["current_product_code"], "none"
        effective, invalid_documents, allergy_conflicts, blockers = [], [], [], []
    elif invalid_documents:
        disposition = final_state = "hold_evidence_integrity"
        action, blockers = "route_prior_authorization_review", sorted(invalid_documents)
    elif rx["daw_code"] == "1":
        disposition = final_state = "hold_prescriber_daw"
        action, blockers = "route_prescriber_daw_review", ["prescriber_daw_code:1"]
    elif allergy_conflicts:
        disposition = final_state = "hold_allergy_conflict"
        action, blockers = (
            "route_clinical_allergy_review",
            [f"target_excipient_allergy:{code}" for code in allergy_conflicts],
        )
    elif (
        rule
        and rule["required_step_code"]
        and (rx["member_id"], rule["required_step_code"]) not in steps
    ):
        disposition = final_state = "hold_step_therapy"
        action, blockers = (
            "route_step_therapy_review",
            [f"missing_step:{rule['required_step_code']}"],
        )
    elif rule and rx["channel"] != rule["required_channel"]:
        disposition = final_state = "hold_channel_restriction"
        action, blockers = (
            "route_specialty_channel_review",
            [f"required_channel:{rule['required_channel']}"],
        )
    elif blockers:
        disposition = final_state = "hold_formulary_authority"
        action = "route_prior_authorization_review"
    else:
        disposition = final_state = str(policy["ready_state"])
        action, blockers = "stage_local_formulary_review", []
    for index, event in enumerate(events):
        if (
            event.get("rx_id") == rx["rx_id"]
            and _event_status(
                index, events, prescriptions, set(policy["protected_statuses"])
            )
            == "applied"
        ):
            refs.add(f"evidence/benefit_events.jsonl#{event['event_id']}")
    mutations = (
        ["upsert_rx_projection"]
        if action == "none"
        else [
            f"set_local_disposition:{disposition}",
            f"set_local_target_product_code:{target}",
            f"set_local_next_action:{action}",
            "upsert_rx_projection",
        ]
    )
    local_values = {
        "rx_id": rx["rx_id"],
        "member_id": rx["member_id"],
        "current_product_code": rx["current_product_code"],
        "target_product_code": target,
        "disposition": disposition,
        "final_local_state": final_state,
        "effective_rule_ids": sorted(effective),
        "invalid_document_ids": sorted(invalid_documents),
        "allergy_conflict_codes": sorted(allergy_conflicts),
        "blocking_reasons": sorted(blockers),
        "local_mutations": sorted(mutations),
        "next_local_action": action,
        "evidence_refs": sorted(refs),
    }
    return sorted(
        field for field in DECISION_FIELDS if actual.get(field) != local_values[field]
    )


def _schema_errors(plan: dict[str, Any]) -> list[str]:
    errors = []
    if set(plan) != PLAN_FIELDS:
        errors.append(f"top-level fields must be exactly {sorted(PLAN_FIELDS)}")
    if not isinstance(plan.get("rx_decisions"), list):
        errors.append("rx_decisions must be a list")
    else:
        for index, row in enumerate(plan["rx_decisions"]):
            if not isinstance(row, dict) or set(row) != DECISION_FIELDS:
                errors.append(
                    f"rx_decisions[{index}] fields must be exactly {sorted(DECISION_FIELDS)}"
                )
            elif any(not isinstance(row.get(field), list) for field in SET_FIELDS):
                errors.append(f"rx_decisions[{index}] set-valued fields must be lists")
    if not isinstance(plan.get("event_dispositions"), list):
        errors.append("event_dispositions must be a list")
    elif any(
        not isinstance(row, dict) or set(row) != EVENT_FIELDS
        for row in plan["event_dispositions"]
    ):
        errors.append(
            f"event disposition fields must be exactly {sorted(EVENT_FIELDS)}"
        )
    if (
        not isinstance(plan.get("totals"), dict)
        or set(plan.get("totals", {})) != TOTAL_FIELDS
    ):
        errors.append(f"totals fields must be exactly {sorted(TOTAL_FIELDS)}")
    return errors


def _compare(plan: dict[str, Any]) -> dict[str, Any]:
    state, policy, events = _baseline(), _load(POLICY), _deliveries()
    prescriptions = {row["rx_id"]: row for row in state["prescriptions"]}
    normalized, errors = _normalized(plan), _schema_errors(plan)
    supplied = {
        str(row.get("rx_id")): row
        for row in normalized.get("rx_decisions", [])
        if isinstance(row, dict)
    }
    diagnostics = {}
    for key, rx in prescriptions.items():
        mismatches = (
            ["missing decision"]
            if key not in supplied
            else _decision_mismatches(supplied[key], rx, state, policy, events)
        )
        diagnostics[key] = {
            "status": "ok" if not mismatches else "mismatch",
            "mismatches": mismatches,
        }
    extras = sorted(set(supplied) - set(prescriptions))
    if extras:
        errors.append(f"unexpected rx decisions: {extras}")
    supplied_events = {
        str(row.get("delivery_id")): row
        for row in normalized.get("event_dispositions", [])
        if isinstance(row, dict)
    }
    event_diagnostics = {}
    for index, event in enumerate(events):
        key = str(event["delivery_id"])
        fields = {
            "delivery_id": key,
            "event_id": str(event["event_id"]),
            "rx_id": str(event["rx_id"]),
            "source_sequence": int(event["source_sequence"]),
            "disposition": _event_status(
                index, events, prescriptions, set(policy["protected_statuses"])
            ),
        }
        actual = supplied_events.get(key)
        mismatches = (
            ["missing event"]
            if actual is None
            else sorted(
                field for field in EVENT_FIELDS if actual.get(field) != fields[field]
            )
        )
        event_diagnostics[key] = {
            "status": "ok" if not mismatches else "mismatch",
            "mismatches": mismatches,
        }
    event_extras = sorted(
        set(supplied_events) - {str(row["delivery_id"]) for row in events}
    )
    if event_extras:
        errors.append(f"unexpected event dispositions: {event_extras}")
    identity_values = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": _checkpoint(state),
        "external_actions_executed": False,
    }
    identity_mismatches = sorted(
        field
        for field, value in identity_values.items()
        if normalized.get(field) != value
    )
    candidate_rows = list(supplied.values())
    totals = {
        "active_prescriptions": sum(
            row["status"] not in set(policy["protected_statuses"])
            for row in state["prescriptions"]
        ),
        "ready_prescriptions": sum(
            row.get("disposition") == policy["ready_state"] for row in candidate_rows
        ),
        "held_prescriptions": sum(
            str(row.get("disposition", "")).startswith("hold_")
            for row in candidate_rows
        ),
        "preserved_dispensed_prescriptions": sum(
            row["status"] == "dispensed" for row in state["prescriptions"]
        ),
        "preserved_cancelled_prescriptions": sum(
            row["status"] == "cancelled" for row in state["prescriptions"]
        ),
    }
    totals_mismatches = sorted(
        field
        for field in TOTAL_FIELDS
        if not isinstance(normalized.get("totals"), dict)
        or normalized["totals"].get(field) != totals[field]
    )
    sources_ok, changed = _sources_valid()
    valid = (
        not errors
        and sources_ok
        and not identity_mismatches
        and not totals_mismatches
        and all(row["status"] == "ok" for row in diagnostics.values())
        and all(row["status"] == "ok" for row in event_diagnostics.values())
    )
    return {
        "schema_version": 1,
        "valid": valid,
        "errors": errors,
        "changed_sources": changed,
        "source_checkpoint_match": "source_checkpoint" not in identity_mismatches,
        "identity_mismatches": identity_mismatches,
        "totals_mismatches": totals_mismatches,
        "decision_diagnostics": diagnostics,
        "event_diagnostics": event_diagnostics,
    }


def inspect() -> None:
    state, policy = _baseline(), _load(POLICY)
    with sqlite3.connect(DB) as con:
        journals = _rows(con, "recovery_journal", "journal_id")
    print(
        json.dumps(
            {
                "schema_version": 1,
                "recovery_id": policy["recovery_id"],
                "source_checkpoint": _checkpoint(state),
                "as_of_utc": policy["as_of_utc"],
                "prescription_count": len(state["prescriptions"]),
                "delivery_count": len(_deliveries()),
                "open_journals": [
                    row["journal_id"] for row in journals if not row["restored"]
                ],
                "plan_fields": sorted(PLAN_FIELDS),
                "decision_fields": sorted(DECISION_FIELDS),
                "event_fields": sorted(EVENT_FIELDS),
                "total_fields": sorted(TOTAL_FIELDS),
            },
            indent=2,
        )
    )


def query(table: str) -> None:
    if table not in QUERY_TABLES:
        raise ValueError(f"query table must be one of {sorted(QUERY_TABLES)}")
    with sqlite3.connect(DB) as con:
        print(json.dumps(_rows(con, table, QUERY_TABLES[table]), indent=2))


def preview(plan_path: Path) -> dict[str, Any]:
    try:
        result = _compare(_load(plan_path))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schema_version": 1,
            "valid": False,
            "errors": [str(exc)],
            "changed_sources": [],
            "source_checkpoint_match": False,
            "identity_mismatches": ["unreadable_plan"],
            "totals_mismatches": [],
            "decision_diagnostics": {},
            "event_diagnostics": {},
        }
    _write(ROOT / ".formulary_preview.json", result)
    return result


def _plan_hash(plan: dict[str, Any]) -> str:
    return "sha256:" + _digest(_canonical(_normalized(plan)))


def apply(plan_path: Path) -> None:
    plan = _normalized(_load(plan_path))
    if not preview(plan_path)["valid"]:
        raise ValueError("preview rejected plan; inspect .formulary_preview.json")
    semantic_hash, recovery_id = _plan_hash(plan), str(plan["recovery_id"])
    restored: list[str] = []
    with sqlite3.connect(DB) as con:
        existing = con.execute(
            "SELECT source_checkpoint,plan_hash,status FROM review_runs WHERE recovery_id=?",
            (recovery_id,),
        ).fetchone()
        if existing:
            if existing == (plan["source_checkpoint"], semantic_hash, "applied"):
                print(
                    json.dumps(
                        {
                            "status": "idempotent",
                            "recovery_id": recovery_id,
                            "plan_hash": semantic_hash,
                        }
                    )
                )
                return
            raise ValueError(
                "conflict: recovery identity already binds another semantic plan"
            )
        con.execute("BEGIN IMMEDIATE")
        for row in _rows(con, "recovery_journal", "journal_id"):
            prior = con.execute(
                "SELECT status FROM review_runs WHERE recovery_id=?",
                (row["recovery_id"],),
            ).fetchone()
            if prior and prior[0] == "interrupted" and not row["restored"]:
                before = json.loads(row["before_json"])
                con.execute(
                    "UPDATE prescriptions SET local_disposition=?,local_target_product_code=?,local_next_action=? WHERE rx_id=?",
                    (
                        before.get("local_disposition"),
                        before.get("local_target_product_code"),
                        before.get("local_next_action"),
                        row["rx_id"],
                    ),
                )
                con.execute(
                    "DELETE FROM rx_projections WHERE recovery_id=? AND rx_id=?",
                    (row["recovery_id"], row["rx_id"]),
                )
                con.execute(
                    "UPDATE review_runs SET status='rolled_back' WHERE recovery_id=?",
                    (row["recovery_id"],),
                )
                con.execute(
                    "UPDATE recovery_journal SET restored=1 WHERE journal_id=?",
                    (row["journal_id"],),
                )
                restored.append(row["journal_id"])
        con.execute(
            "INSERT INTO review_runs VALUES (?,?,?,?)",
            (recovery_id, plan["source_checkpoint"], semantic_hash, "applied"),
        )
        for row in plan["rx_decisions"]:
            con.execute(
                "UPDATE prescriptions SET local_disposition=?,local_target_product_code=?,local_next_action=? WHERE rx_id=?",
                (
                    row["disposition"],
                    row["target_product_code"],
                    row["next_local_action"],
                    row["rx_id"],
                ),
            )
            con.execute(
                "INSERT INTO rx_projections VALUES (?,?,?,?,?,?,?,?)",
                (
                    recovery_id,
                    row["rx_id"],
                    semantic_hash,
                    row["disposition"],
                    row["final_local_state"],
                    row["target_product_code"],
                    row["next_local_action"],
                    json.dumps(
                        row["evidence_refs"], sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
        con.commit()
    _write(
        ROOT / "state/recovery_receipt.json",
        {
            "schema_version": 1,
            "recovery_id": recovery_id,
            "source_checkpoint": plan["source_checkpoint"],
            "plan_hash": semantic_hash,
            "restored_journals": sorted(restored),
            "status": "applied",
            "external_actions_executed": False,
        },
    )
    print(
        json.dumps(
            {
                "status": "applied",
                "recovery_id": recovery_id,
                "plan_hash": semantic_hash,
            }
        )
    )


def verify(plan_path: Path) -> None:
    plan, semantic_hash = _normalized(_load(plan_path)), _plan_hash(_load(plan_path))
    with sqlite3.connect(DB) as con:
        run = con.execute(
            "SELECT source_checkpoint,plan_hash,status FROM review_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
        projections = con.execute(
            "SELECT COUNT(*) FROM rx_projections WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()[0]
        open_journals = con.execute(
            "SELECT COUNT(*) FROM recovery_journal WHERE restored=0"
        ).fetchone()[0]
    valid = (
        bool(_compare(plan)["valid"])
        and run == (plan["source_checkpoint"], semantic_hash, "applied")
        and projections == len(plan["rx_decisions"])
        and open_journals == 0
    )
    result = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "plan_hash": semantic_hash,
        "valid": valid,
        "journal_closed": open_journals == 0,
        "projection_count": projections,
        "external_actions_executed": False,
    }
    _write(ROOT / "state/verification.json", result)
    if not valid:
        raise ValueError("verification failed")
    print(json.dumps(result))


def stage(plan_path: Path) -> None:
    plan, verification = (
        _normalized(_load(plan_path)),
        _load(ROOT / "state/verification.json"),
    )
    handoff = ROOT / "formulary_handoff.md"
    if verification.get("valid") is not True or not handoff.is_file():
        raise ValueError("valid verification and formulary_handoff.md are required")
    packet = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "plan_hash": _plan_hash(plan),
        "ready_rx_ids": sorted(
            row["rx_id"]
            for row in plan["rx_decisions"]
            if row["disposition"] == "ready_local_formulary_review"
        ),
        "held_rx_ids": sorted(
            row["rx_id"]
            for row in plan["rx_decisions"]
            if row["disposition"].startswith("hold_")
        ),
        "preserved_rx_ids": sorted(
            row["rx_id"]
            for row in plan["rx_decisions"]
            if row["disposition"].endswith("_boundary_preserved")
        ),
        "external_actions_executed": False,
    }
    packet_path = ROOT / "staging/formulary_review_packet.json"
    _write(packet_path, packet)
    _write(
        ROOT / "staging/packet_manifest.json",
        {
            "schema_version": 1,
            "recovery_id": plan["recovery_id"],
            "source_checkpoint": plan["source_checkpoint"],
            "plan_hash": _plan_hash(plan),
            "files": {
                "staging/formulary_review_packet.json": _digest(
                    packet_path.read_bytes()
                ),
                "formulary_handoff.md": _digest(handoff.read_bytes()),
            },
            "external_actions_executed": False,
        },
    )
    print(json.dumps({"status": "staged_local_review_packet"}))


def replay(plan_path: Path) -> None:
    plan, before = _normalized(_load(plan_path)), DB.read_bytes()
    semantic_hash = _plan_hash(plan)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        run = con.execute(
            "SELECT source_checkpoint,plan_hash,status FROM review_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
    if not _compare(plan)["valid"] or run != (
        plan["source_checkpoint"],
        semantic_hash,
        "applied",
    ):
        raise ValueError("conflict or stale replay rejected before mutation")
    result = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "semantic_replay_noop",
        "database_unchanged": before == DB.read_bytes(),
        "plan_hash": semantic_hash,
        "external_actions_executed": False,
    }
    _write(ROOT / "state/replay_report.json", result)
    print(json.dumps(result))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline formulary substitution recovery controller"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect()
        elif args.command == "query":
            query(args.table)
        elif args.command == "preview":
            result = preview(Path(args.plan))
            print(json.dumps(result, indent=2))
            if not result["valid"]:
                return 2
        else:
            globals()[args.command](Path(args.plan))
        return 0
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

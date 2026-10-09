#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
SOURCE_DOCUMENT = "bulletin_working.docx"
OUTPUT_DOCUMENT = "approved_bulletin.docx"
DATABASE = "review_state.db"
RECEIPT = "verification_receipt.json"
WORKFLOW_ID = "NORTHSTAR-BULLETIN-REV5"
RECOVERY_TRANSACTION = "TX-05"
FIXED_TIME = "2026-08-19T09:30:00Z"
SOURCE_HASHES = {
    "authority_policy.md": "62148f560e070260c99e71b169e57ea755109c536a166db3a4f9c21688b8bfd8",
    "revision_dependencies.csv": "acd3cad39e6f0de1924a8a9de087c819a11c626e4586801f8e1ec75b47a87578",
    "revision_manifest.json": "ad2a7ae4ee010c42c4ee9a5c9dc4f133407db53cd6e97821caf72868f06e1462",
    "signature_registry.json": "67e10c3edd195aaae1e7a870475edb1fc671e26efbbc09d62d2f7e3e78ed1d45",
    "bulletin_working.docx": "7202ed66a385e1b784b76b10f38ce1751b3dc8f91b9fcc3ef1214248b6aaad50",
}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
W_TAG = f"{{{W_NS}}}"
EVIDENCE_RE = re.compile(r"^[A-Za-z0-9_.-]+#[A-Za-z0-9_.:-]+$")
ACCEPTED_CLASSES = {
    "signed_legal": "legal_signer",
    "verified_directory": "directory_owner",
    "release_coordinator": "release_coordinator",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load_json(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def source_bundle_sha256() -> str:
    return canonical_digest(SOURCE_HASHES)


def source_errors() -> list[str]:
    errors = []
    for name, expected in SOURCE_HASHES.items():
        path = ROOT / name
        if not path.is_file():
            errors.append(f"protected source missing: {name}")
        elif sha256(path) != expected:
            errors.append(f"protected source changed: {name}")
    return errors


def dependencies() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    with (ROOT / "revision_dependencies.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            result[row["change_id"]] = [
                value for value in row["depends_on"].split(";") if value
            ]
    for event in load_json("revision_manifest.json")["events"]:
        result.setdefault(event["change_id"], [])
    return result


def adjudication_order(graph: dict[str, list[str]]) -> list[str]:
    remaining = {key: set(values) for key, values in graph.items()}
    result = []
    while remaining:
        ready = sorted(key for key, values in remaining.items() if not values)
        if not ready:
            raise ValueError("dependency graph contains a cycle")
        selected = ready[0]
        result.append(selected)
        del remaining[selected]
        for values in remaining.values():
            values.discard(selected)
    return result


def current_events() -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in load_json("revision_manifest.json")["events"]:
        if event.get("basis_status") == "current":
            grouped.setdefault(str(event["change_id"]), []).append(event)
    return {
        change_id: max(rows, key=lambda row: int(row["event_seq"]))
        for change_id, rows in grouped.items()
    }


def credential_is_valid(event: dict[str, Any]) -> bool:
    expected_role = ACCEPTED_CLASSES.get(str(event.get("proposal_class")))
    if expected_role is None:
        return False
    credential_id = event.get("credential_id")
    credentials = load_json("signature_registry.json")["credentials"]
    credential = credentials.get(str(credential_id), {})
    return credential.get("verified") is True and credential.get("role") == expected_role


def expected_dispositions() -> tuple[list[str], dict[str, dict[str, Any]]]:
    graph = dependencies()
    order = adjudication_order(graph)
    selected = current_events()
    result: dict[str, dict[str, Any]] = {}
    for change_id in order:
        event = selected[change_id]
        if any(result[parent]["disposition"] != "accept" for parent in graph[change_id]):
            disposition = "invalidate_dependency"
        elif credential_is_valid(event):
            disposition = "accept"
        else:
            disposition = "reject"
        result[change_id] = {"event": event, "disposition": disposition}
    return order, result


def normalize_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    actions = plan.get("actions")
    normalized_actions = []
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict):
                continue
            evidence = action.get("evidence")
            refs = sorted({str(value) for value in evidence}) if isinstance(evidence, list) else []
            normalized_actions.append(
                {
                    "change_id": str(action.get("change_id", "")),
                    "selected_event_id": str(action.get("selected_event_id", "")),
                    "disposition": str(action.get("disposition", "")),
                    "evidence": refs,
                }
            )
    normalized_actions.sort(key=lambda row: row["change_id"])
    order = plan.get("adjudication_order")
    return {
        "workflow_id": str(plan.get("workflow_id", "")),
        "source_document": str(plan.get("source_document", "")),
        "adjudication_order": [str(value) for value in order]
        if isinstance(order, list)
        else [],
        "approval_boundary": str(plan.get("approval_boundary", "")),
        "actions": normalized_actions,
    }


def plan_digest(plan: Any) -> str:
    return canonical_digest(normalize_plan(plan))


def required_evidence(
    change_id: str, event: dict[str, Any], graph: dict[str, list[str]]
) -> set[str]:
    refs = {
        f"revision_manifest.json#{event['event_id']}",
        f"authority_policy.md#{event['policy_rule']}",
    }
    if event.get("credential_id"):
        refs.add(f"signature_registry.json#{event['credential_id']}")
    if graph[change_id]:
        refs.add(f"revision_dependencies.csv#{change_id}")
    if change_id == "CH-05":
        refs.add("review_state.db#TX-04")
    return refs


def validate_plan(plan: Any) -> tuple[bool, dict[str, bool], list[str], dict[str, dict[str, Any]]]:
    normalized = normalize_plan(plan)
    graph = dependencies()
    order, expected = expected_dispositions()
    actions = normalized.get("actions", [])
    by_change = {row["change_id"]: row for row in actions}
    coverage_ok = (
        len(actions) == len(by_change) == len(expected)
        and set(by_change) == set(expected)
    )
    event_failures = []
    disposition_failures = []
    evidence_failures = []
    if coverage_ok:
        for change_id, item in expected.items():
            action = by_change[change_id]
            event = item["event"]
            if action["selected_event_id"] != event["event_id"]:
                event_failures.append(change_id)
            if action["disposition"] != item["disposition"]:
                disposition_failures.append(change_id)
            refs = set(action["evidence"])
            required = required_evidence(change_id, event, graph)
            if (
                not required.issubset(refs)
                or not refs
                or not all(EVIDENCE_RE.fullmatch(ref) for ref in refs)
                or any(
                    ref.startswith(("http://", "https://", "file://", "/", "../"))
                    for ref in refs
                )
            ):
                evidence_failures.append(change_id)
    checks = {
        "workflow_identity": normalized.get("workflow_id") == WORKFLOW_ID,
        "source_document": normalized.get("source_document") == SOURCE_DOCUMENT,
        "internal_boundary": normalized.get("approval_boundary")
        == "staged_for_internal_approval",
        "action_coverage": coverage_ok,
        "deterministic_order": normalized.get("adjudication_order") == order,
        "current_event_selection": coverage_ok and not event_failures,
        "authority_and_dependency_outcomes": coverage_ok and not disposition_failures,
        "local_evidence": coverage_ok and not evidence_failures,
    }
    errors = []
    if event_failures:
        errors.append(f"event selection mismatch: {','.join(event_failures)}")
    if disposition_failures:
        errors.append(f"authority/dependency mismatch: {','.join(disposition_failures)}")
    if evidence_failures:
        errors.append(f"evidence incomplete: {','.join(evidence_failures)}")
    errors.extend(key for key, passed in checks.items() if not passed and key not in {
        "current_event_selection", "authority_and_dependency_outcomes", "local_evidence"
    })
    return all(checks.values()), checks, errors, by_change


def read_docx(path: Path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        entries = {info.filename: archive.read(info.filename) for info in infos}
    if "word/document.xml" not in entries:
        raise ValueError("DOCX is missing word/document.xml")
    ET.fromstring(entries["word/document.xml"])
    return infos, entries


def paragraph_change_id(paragraph: ET.Element) -> str | None:
    for bookmark in paragraph.findall("w:bookmarkStart", NS):
        name = bookmark.get(f"{W_TAG}name", "")
        if name.startswith("HB_CH_"):
            return name.removeprefix("HB_").replace("_", "-")
    return None


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(
        node.text or ""
        for node in paragraph.iter()
        if node.tag in {f"{W_TAG}t", f"{W_TAG}delText"}
    )


def docx_summary(path: Path) -> dict[str, Any]:
    infos, entries = read_docx(path)
    root = ET.fromstring(entries["word/document.xml"])
    tracked = []
    bookmarks = []
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
        for bookmark in paragraph.findall("w:bookmarkStart", NS):
            name = bookmark.get(f"{W_TAG}name", "")
            if name:
                bookmarks.append(name)
        for node in paragraph.iter():
            if node.tag in {f"{W_TAG}ins", f"{W_TAG}del"}:
                tracked.append(node.get(f"{W_TAG}id", ""))
    return {
        "package_parts": [info.filename for info in infos],
        "paragraphs": paragraphs,
        "bookmarks": bookmarks,
        "tracked_revision_ids": tracked,
        "sha256": sha256(path),
    }


def _unwrap_revision(paragraph: ET.Element, node: ET.Element, *, deleted: bool) -> None:
    index = list(paragraph).index(node)
    paragraph.remove(node)
    for child in list(node):
        value = copy.deepcopy(child)
        if deleted:
            for deleted_text in value.iter(f"{W_TAG}delText"):
                deleted_text.tag = f"{W_TAG}t"
        paragraph.insert(index, value)
        index += 1


def resolved_docx_bytes(actions: dict[str, dict[str, Any]]) -> bytes:
    infos, entries = read_docx(ROOT / SOURCE_DOCUMENT)
    root = ET.fromstring(entries["word/document.xml"])
    expected_events = current_events()
    seen = set()
    for paragraph in root.findall(".//w:p", NS):
        change_id = paragraph_change_id(paragraph)
        if change_id is None:
            continue
        action = actions.get(change_id)
        if action is None:
            raise ValueError(f"plan missing action for {change_id}")
        expected_id = str(expected_events[change_id]["ooxml_revision_id"])
        revision_nodes = [
            child
            for child in list(paragraph)
            if child.tag in {f"{W_TAG}ins", f"{W_TAG}del"}
        ]
        ids = {node.get(f"{W_TAG}id", "") for node in revision_nodes}
        if ids != {expected_id} or len(revision_nodes) != 2:
            raise ValueError(f"OOXML revision pair mismatch for {change_id}")
        accept = action["disposition"] == "accept"
        for node in list(revision_nodes):
            if node.tag == f"{W_TAG}ins":
                if accept:
                    _unwrap_revision(paragraph, node, deleted=False)
                else:
                    paragraph.remove(node)
            elif accept:
                paragraph.remove(node)
            else:
                _unwrap_revision(paragraph, node, deleted=True)
        seen.add(change_id)
    if seen != set(actions):
        raise ValueError("DOCX bookmark/action coverage mismatch")
    if root.findall(".//w:ins", NS) or root.findall(".//w:del", NS):
        raise ValueError("unresolved tracked revisions remain")
    entries["word/document.xml"] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for info in infos:
            archive.writestr(info, entries[info.filename])
    return stream.getvalue()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(ROOT / DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def table_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    orders = {
        "workflow_state": "workflow_id",
        "revision_journal": "sequence",
        "transactions": "transaction_id",
    }
    if table not in orders:
        raise ValueError(f"unsupported table: {table}")
    return [
        dict(row)
        for row in connection.execute(
            f"SELECT * FROM {table} ORDER BY {orders[table]}"
        )
    ]


def database_snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    return {
        table: table_rows(connection, table)
        for table in ("workflow_state", "revision_journal", "transactions")
    }


def proposal_sha(event: dict[str, Any]) -> str:
    return sha256_bytes(str(event["new_text"]).encode())


def prefix_ok(snapshot: dict[str, list[dict[str, Any]]]) -> bool:
    journal = snapshot.get("revision_journal", [])
    transactions = snapshot.get("transactions", [])
    if not journal or not transactions:
        return False
    event = current_events()["CH-05"]
    return journal[0] == {
        "sequence": 1,
        "transaction_id": "TX-04",
        "change_id": "CH-05",
        "event_id": "EV-508",
        "disposition": "accept",
        "proposal_sha256": proposal_sha(event),
        "recorded_at": "2026-08-18T16:42:00Z",
    } and transactions[0].get("transaction_id") == "TX-04"


def inspect() -> int:
    errors = source_errors()
    try:
        document = docx_summary(ROOT / SOURCE_DOCUMENT)
    except Exception as exc:
        document = {"error": str(exc)}
        errors.append(f"source DOCX invalid: {exc}")
    try:
        with connect() as connection:
            snapshot = database_snapshot(connection)
    except sqlite3.Error as exc:
        snapshot = {}
        errors.append(f"review database invalid: {exc}")
    output = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "source_bundle_sha256": source_bundle_sha256(),
        "document": document,
        "workflow_state": snapshot.get("workflow_state", []),
        "durable_journal": snapshot.get("revision_journal", []),
        "transactions": snapshot.get("transactions", []),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not errors else 2


def load_plan(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def preview(name: str) -> int:
    errors = source_errors()
    try:
        plan = load_plan(name)
    except Exception as exc:
        print(json.dumps({"status": "fail", "errors": [f"invalid plan: {exc}"]}, indent=2))
        return 2
    valid, checks, plan_errors, actions = validate_plan(plan)
    errors.extend(plan_errors)
    projected_sha = ""
    projected_paragraphs: list[str] = []
    if valid and not errors:
        try:
            payload = resolved_docx_bytes(actions)
            projected_sha = sha256_bytes(payload)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            projected_paragraphs = [
                paragraph_text(paragraph)
                for paragraph in root.findall(".//w:p", NS)
                if paragraph_text(paragraph)
            ]
        except Exception as exc:
            errors.append(f"OOXML preview failed: {exc}")
    result = {
        "status": "pass" if valid and not errors else "fail",
        "checks": checks,
        "errors": errors,
        "normalized_plan_sha256": plan_digest(plan),
        "projected_docx_sha256": projected_sha,
        "projected_paragraphs": projected_paragraphs,
        "state_mutated": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def apply(name: str) -> int:
    errors = source_errors()
    try:
        plan = load_plan(name)
    except Exception as exc:
        print(json.dumps({"status": "rejected", "errors": [f"invalid plan: {exc}"]}, indent=2))
        return 2
    valid, checks, plan_errors, actions = validate_plan(plan)
    errors.extend(plan_errors)
    if not valid or errors:
        print(json.dumps({"status": "rejected", "checks": checks, "errors": errors}, indent=2, sort_keys=True))
        return 2
    normalized_sha = plan_digest(plan)
    output_bytes = resolved_docx_bytes(actions)
    output_sha = sha256_bytes(output_bytes)
    with connect() as connection:
        prior = connection.execute(
            "SELECT * FROM transactions WHERE plan_sha256=?", (normalized_sha,)
        ).fetchone()
        if prior is not None:
            output_ok = (
                (ROOT / OUTPUT_DOCUMENT).is_file()
                and sha256(ROOT / OUTPUT_DOCUMENT) == prior["output_docx_sha256"]
                == output_sha
            )
            result = {
                "status": "idempotent" if output_ok else "rejected",
                "normalized_plan_sha256": normalized_sha,
                "output_docx_sha256": output_sha,
                "state_mutated": False,
            }
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if output_ok else 2
        snapshot = database_snapshot(connection)
        state_rows = snapshot["workflow_state"]
        state_ok = (
            len(state_rows) == 1
            and state_rows[0].get("workflow_id") == WORKFLOW_ID
            and state_rows[0].get("phase") == "interrupted_after_journal_commit"
            and state_rows[0].get("base_docx_sha256") == SOURCE_HASHES[SOURCE_DOCUMENT]
            and state_rows[0].get("external_published") == 0
            and prefix_ok(snapshot)
        )
        if not state_ok:
            print(json.dumps({"status": "rejected", "errors": ["interrupted state or durable prefix is invalid"]}, indent=2))
            return 2
        temporary = ROOT / f".{OUTPUT_DOCUMENT}.tmp"
        temporary.write_bytes(output_bytes)
        temporary.replace(ROOT / OUTPUT_DOCUMENT)
        order, expected = expected_dispositions()
        sequence = int(snapshot["revision_journal"][-1]["sequence"])
        appended = 0
        reconciled = 0
        for change_id in order:
            action = actions[change_id]
            existing = connection.execute(
                "SELECT * FROM revision_journal WHERE change_id=?", (change_id,)
            ).fetchone()
            event = expected[change_id]["event"]
            if existing is not None:
                if (
                    existing["event_id"] != action["selected_event_id"]
                    or existing["disposition"] != action["disposition"]
                    or existing["proposal_sha256"] != proposal_sha(event)
                ):
                    connection.rollback()
                    print(json.dumps({"status": "rejected", "errors": [f"durable decision conflicts for {change_id}"]}, indent=2))
                    return 2
                reconciled += 1
                continue
            sequence += 1
            connection.execute(
                "INSERT INTO revision_journal VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sequence,
                    RECOVERY_TRANSACTION,
                    change_id,
                    action["selected_event_id"],
                    action["disposition"],
                    proposal_sha(event),
                    FIXED_TIME,
                ),
            )
            appended += 1
        counts = {
            disposition: sum(
                1 for row in actions.values() if row["disposition"] == disposition
            )
            for disposition in ("accept", "reject", "invalidate_dependency")
        }
        connection.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                RECOVERY_TRANSACTION,
                normalized_sha,
                SOURCE_HASHES[SOURCE_DOCUMENT],
                output_sha,
                len(actions),
                appended,
                reconciled,
                counts["accept"],
                counts["reject"],
                counts["invalidate_dependency"],
                FIXED_TIME,
            ),
        )
        connection.execute(
            """UPDATE workflow_state
               SET phase='adjudicated', checkpoint_status='recovered',
                   active_plan_sha256=?, staged_docx_sha256=?, updated_at=?
               WHERE workflow_id=?""",
            (normalized_sha, output_sha, FIXED_TIME, WORKFLOW_ID),
        )
        connection.commit()
    result = {
        "status": "applied",
        "normalized_plan_sha256": normalized_sha,
        "output_docx_sha256": output_sha,
        "journal_entries_appended": appended,
        "durable_entries_reconciled": reconciled,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def final_database_checks(
    snapshot: dict[str, list[dict[str, Any]]],
    plan: Any,
    actions: dict[str, dict[str, Any]],
    output_sha: str,
) -> dict[str, bool]:
    normalized_sha = plan_digest(plan)
    order, expected = expected_dispositions()
    journal = snapshot.get("revision_journal", [])
    by_change = {row.get("change_id"): row for row in journal}
    journal_ok = (
        len(journal) == len(by_change) == len(expected)
        and set(by_change) == set(expected)
        and all(
            by_change[change_id].get("event_id") == actions[change_id]["selected_event_id"]
            and by_change[change_id].get("disposition") == actions[change_id]["disposition"]
            and by_change[change_id].get("proposal_sha256")
            == proposal_sha(expected[change_id]["event"])
            for change_id in order
        )
    )
    transactions = snapshot.get("transactions", [])
    recovery = next(
        (row for row in transactions if row.get("transaction_id") == RECOVERY_TRANSACTION),
        {},
    )
    transaction_ok = (
        len(transactions) == 2
        and recovery.get("plan_sha256") == normalized_sha
        and recovery.get("source_docx_sha256") == SOURCE_HASHES[SOURCE_DOCUMENT]
        and recovery.get("output_docx_sha256") == output_sha
        and recovery.get("action_count") == 10
        and recovery.get("appended_count") == 9
        and recovery.get("reconciled_count") == 1
        and recovery.get("accepted_count") == 5
        and recovery.get("rejected_count") == 3
        and recovery.get("invalidated_count") == 2
    )
    states = snapshot.get("workflow_state", [])
    state = states[0] if len(states) == 1 else {}
    state_ok = (
        state.get("workflow_id") == WORKFLOW_ID
        and state.get("source_revision") == 4
        and state.get("target_revision") == 5
        and state.get("phase") in {"adjudicated", "staged_for_internal_approval"}
        and state.get("checkpoint_status") == "recovered"
        and state.get("base_docx_sha256") == SOURCE_HASHES[SOURCE_DOCUMENT]
        and state.get("active_plan_sha256") == normalized_sha
        and state.get("staged_docx_sha256") == output_sha
        and state.get("external_published") == 0
    )
    return {
        "durable_prefix_preserved": prefix_ok(snapshot),
        "one_decision_per_change": journal_ok,
        "single_recovery_transaction": transaction_ok,
        "workflow_state_reconciled": state_ok,
    }


def verify(name: str) -> int:
    errors = source_errors()
    try:
        plan = load_plan(name)
    except Exception as exc:
        print(json.dumps({"status": "fail", "errors": [f"invalid plan: {exc}"]}, indent=2))
        return 2
    valid, plan_checks, plan_errors, actions = validate_plan(plan)
    errors.extend(plan_errors)
    expected_bytes = b""
    output_sha = ""
    package_checks = {
        "output_document_present": False,
        "document_matches_plan": False,
        "tracked_revisions_resolved": False,
        "non_document_parts_preserved": False,
    }
    try:
        expected_bytes = resolved_docx_bytes(actions) if valid else b""
        output = ROOT / OUTPUT_DOCUMENT
        output_sha = sha256(output) if output.is_file() else ""
        source_infos, source_entries = read_docx(ROOT / SOURCE_DOCUMENT)
        output_infos, output_entries = read_docx(output)
        output_root = ET.fromstring(output_entries["word/document.xml"])
        package_checks = {
            "output_document_present": output.is_file(),
            "document_matches_plan": output.read_bytes() == expected_bytes,
            "tracked_revisions_resolved": not output_root.findall(".//w:ins", NS)
            and not output_root.findall(".//w:del", NS),
            "non_document_parts_preserved": [item.filename for item in source_infos]
            == [item.filename for item in output_infos]
            and all(
                source_entries[name] == output_entries.get(name)
                for name in source_entries
                if name != "word/document.xml"
            ),
        }
    except Exception as exc:
        errors.append(f"output DOCX verification failed: {exc}")
    try:
        with connect() as connection:
            snapshot = database_snapshot(connection)
            database_checks = final_database_checks(snapshot, plan, actions, output_sha)
            preflight = (
                valid
                and not errors
                and all(plan_checks.values())
                and all(package_checks.values())
                and all(database_checks.values())
            )
            if preflight and snapshot["workflow_state"][0]["phase"] == "adjudicated":
                connection.execute(
                    """UPDATE workflow_state
                       SET phase='staged_for_internal_approval', checkpoint_status='recovered',
                           updated_at=? WHERE workflow_id=?""",
                    (FIXED_TIME, WORKFLOW_ID),
                )
                connection.commit()
            snapshot = database_snapshot(connection)
            database_checks = final_database_checks(snapshot, plan, actions, output_sha)
    except sqlite3.Error as exc:
        snapshot = {}
        database_checks = {
            "durable_prefix_preserved": False,
            "one_decision_per_change": False,
            "single_recovery_transaction": False,
            "workflow_state_reconciled": False,
        }
        errors.append(f"database verification failed: {exc}")
    all_checks = {**plan_checks, **package_checks, **database_checks}
    passed = not errors and all(all_checks.values())
    handoff = ROOT / "editorial_handoff.md"
    prefix = snapshot.get("revision_journal", [])[:1]
    receipt = {
        "tool": "bulletinctl/1",
        "status": "pass" if passed else "fail",
        "workflow_id": WORKFLOW_ID,
        "phase": (
            snapshot.get("workflow_state", [{}])[0].get("phase", "")
            if snapshot.get("workflow_state")
            else ""
        ),
        "normalized_plan_sha256": plan_digest(plan),
        "source_bundle_sha256": source_bundle_sha256(),
        "approved_docx_sha256": output_sha,
        "database_state_sha256": canonical_digest(snapshot),
        "journal_prefix_sha256": canonical_digest(prefix),
        "handoff_sha256": sha256(handoff) if handoff.is_file() else "",
        "checks": all_checks,
        "external_published": False,
    }
    (ROOT / RECEIPT).write_bytes(json_bytes(receipt))
    print(json.dumps({**receipt, "errors": errors}, indent=2, sort_keys=True))
    return 0 if passed else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("inspect")
    for command in ("preview", "apply", "verify"):
        child = subcommands.add_parser(command)
        child.add_argument("--plan", required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        return inspect()
    if args.command == "preview":
        return preview(args.plan)
    if args.command == "apply":
        return apply(args.plan)
    if args.command == "verify":
        return verify(args.plan)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

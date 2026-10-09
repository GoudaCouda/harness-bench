#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE_TABLES = (
    "close_journal",
    "prepared_actions",
    "close_runs",
    "transaction_dispositions",
    "split_edges",
    "refund_links",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def rows(
    path: Path, statement: str, parameters: tuple[Any, ...] = ()
) -> list[dict[str, Any]]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(statement, parameters)]
    finally:
        connection.close()


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in re.split(r"[\n|]+", text):
        match = re.match(r"\s*([A-Za-z_ ]+)\s*[:=]\s*(.*?)\s*$", item)
        if match:
            fields[match.group(1).strip().lower().replace(" ", "_")] = match.group(
                2
            ).strip()
    return fields


def parse_receipt(path: Path, media_type: str) -> dict[str, Any]:
    if media_type == "application/json":
        raw = read_json(path)
        fields = {str(key): str(value) for key, value in raw.items()}
    elif media_type == "text/html":
        parser = VisibleText()
        parser.feed(path.read_text(encoding="utf-8"))
        fields = parse_fields("\n".join(parser.parts))
    elif media_type == "application/pdf":
        data = path.read_bytes()
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data:
            raise ValueError("invalid PDF envelope")
        strings = re.findall(rb"\((?:\\.|[^\\)])*\)\s*Tj", data)
        decoded = []
        for token in strings:
            body = token[1 : token.rfind(b")")]
            body = re.sub(rb"\\([\\()])", rb"\1", body)
            decoded.append(body.decode("latin-1"))
        fields = parse_fields("\n".join(decoded))
    else:
        raise ValueError(f"unsupported media type {media_type}")
    required = {
        "transaction_id",
        "merchant",
        "currency",
        "subtotal_cents",
        "tax_cents",
        "total_cents",
    }
    if not required.issubset(fields):
        raise ValueError(f"missing receipt fields: {sorted(required - set(fields))}")
    return {
        "transaction_id": fields["transaction_id"],
        "merchant": fields["merchant"],
        "currency": fields["currency"],
        "subtotal_cents": int(fields["subtotal_cents"]),
        "tax_cents": int(fields["tax_cents"]),
        "total_cents": int(fields["total_cents"]),
    }


def context() -> dict[str, Any]:
    return read_json(ROOT / "close_context.json")


def business_sources() -> list[Path]:
    manifest = read_json(ROOT / "receipt_manifest.json")
    receipt_paths = [
        ROOT / str(row["path"])
        for row in manifest.get("receipts", [])
        if isinstance(row, dict)
    ]
    return [
        ROOT / "issuer.db",
        ROOT / "erp.db",
        ROOT / "acceptance.db",
        ROOT / "close_context.json",
        ROOT / "pcard_policy.md",
        ROOT / "receipt_manifest.json",
        *receipt_paths,
    ]


def source_checkpoint() -> str:
    return digest(
        {path.relative_to(ROOT).as_posix(): sha(path) for path in business_sources()}
    )


def transactions() -> list[dict[str, Any]]:
    period = str(context()["period"])
    return rows(
        ROOT / "issuer.db",
        "SELECT * FROM transactions WHERE substr(posted_at,1,7)=? ORDER BY transaction_id",
        (period,),
    )


def receipt_index() -> dict[str, dict[str, Any]]:
    manifest = read_json(ROOT / "receipt_manifest.json")
    result: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("receipts", []):
        if not isinstance(entry, dict):
            continue
        path = ROOT / str(entry.get("path", ""))
        actual_sha = sha(path)
        parsed = parse_receipt(path, str(entry.get("media_type", "")))
        valid_hash = actual_sha == entry.get("sha256")
        result[str(entry.get("transaction_id"))] = {
            **entry,
            "actual_sha256": actual_sha,
            "hash_valid": valid_hash,
            "parsed": parsed,
        }
    return result


def acceptance_index() -> dict[str, dict[str, Any]]:
    return {
        row["transaction_id"]: row
        for row in rows(
            ROOT / "acceptance.db",
            "SELECT * FROM acceptance_decisions ORDER BY transaction_id",
        )
        if row.get("status") == "accepted"
    }


def prior_postings() -> dict[str, dict[str, Any]]:
    return {
        row["transaction_id"]: row
        for row in rows(
            ROOT / "erp.db",
            "SELECT * FROM posted_card_transactions ORDER BY transaction_id",
        )
    }


def valid_receipt(transaction: dict[str, Any], receipt: dict[str, Any] | None) -> bool:
    if not receipt or not receipt.get("hash_valid"):
        return False
    parsed = receipt.get("parsed", {})
    return bool(
        parsed.get("transaction_id") == transaction["transaction_id"]
        and parsed.get("merchant") == transaction["merchant"]
        and parsed.get("currency") == transaction["currency"]
        and parsed.get("total_cents") == transaction["amount_cents"]
        and parsed.get("tax_cents") == transaction["tax_cents"]
        and parsed.get("subtotal_cents") + parsed.get("tax_cents")
        == parsed.get("total_cents")
    )


def split_edges() -> list[dict[str, Any]]:
    charges = [row for row in transactions() if row["amount_cents"] > 0]
    result: list[dict[str, Any]] = []
    for index, left in enumerate(charges):
        for right in charges[index + 1 :]:
            same_group = (
                left["cardholder_id"] == right["cardholder_id"]
                and left["merchant"] == right["merchant"]
                and left["local_date"] == right["local_date"]
            )
            combined = left["amount_cents"] + right["amount_cents"]
            if (
                same_group
                and max(left["amount_cents"], right["amount_cents"]) <= 50000 < combined
            ):
                result.append(
                    {
                        "left_transaction_id": left["transaction_id"],
                        "right_transaction_id": right["transaction_id"],
                        "combined_cents": combined,
                    }
                )
    return result


def derive_decisions() -> dict[str, dict[str, Any]]:
    receipts = receipt_index()
    accepted = acceptance_index()
    posted = prior_postings()
    edges = split_edges()
    split_ids = {
        edge[key]
        for edge in edges
        for key in ("left_transaction_id", "right_transaction_id")
    }
    decisions: dict[str, dict[str, Any]] = {}
    for transaction in transactions():
        transaction_id = transaction["transaction_id"]
        base = [
            f"issuer.db#transactions/{transaction_id}",
            "pcard_policy.md#published-dispositions",
        ]
        if transaction["amount_cents"] < 0:
            original = posted.get(transaction["original_transaction_id"])
            if not original or original["period"] == context()["period"]:
                disposition = "hold_missing_receipt"
                cleared, exception = 0, abs(transaction["amount_cents"])
            else:
                disposition = "clear_prior_period_refund"
                cleared, exception = transaction["amount_cents"], 0
                base.append(
                    f"erp.db#posted_card_transactions/{original['transaction_id']}"
                )
        else:
            receipt = receipts.get(transaction_id)
            if not valid_receipt(transaction, receipt):
                disposition = "hold_missing_receipt"
                cleared, exception = 0, transaction["amount_cents"]
            else:
                base.append(f"{receipt['path']}#sha256={receipt['actual_sha256']}")
                if transaction_id in split_ids:
                    disposition = "hold_suspected_split"
                    cleared, exception = 0, transaction["amount_cents"]
                    peers = sorted(
                        (
                            {edge["left_transaction_id"], edge["right_transaction_id"]}
                            - {transaction_id}
                        ).pop()
                        for edge in edges
                        if transaction_id
                        in {edge["left_transaction_id"], edge["right_transaction_id"]}
                    )
                    base.extend(f"issuer.db#split-peer/{peer}" for peer in peers)
                elif transaction_id not in accepted:
                    disposition = "hold_missing_acceptance"
                    cleared, exception = 0, transaction["amount_cents"]
                    base.append("acceptance.db#absence")
                elif transaction["tax_cents"] > 0:
                    disposition = "partial_nonreimbursable_tax"
                    cleared = transaction["amount_cents"] - transaction["tax_cents"]
                    exception = transaction["tax_cents"]
                    base.append(f"acceptance.db#acceptance_decisions/{transaction_id}")
                else:
                    disposition = "clear"
                    cleared, exception = transaction["amount_cents"], 0
                    base.append(f"acceptance.db#acceptance_decisions/{transaction_id}")
        decisions[transaction_id] = {
            "disposition": disposition,
            "cleared_cents": cleared,
            "exception_cents": exception,
            "evidence_refs": sorted(set(base)),
            "receipt_sha256": receipts.get(transaction_id, {}).get("actual_sha256"),
            "original_transaction_id": transaction.get("original_transaction_id"),
        }
    return decisions


def normalize_evidence_refs(transaction_id: str, refs: Any) -> set[str]:
    """Normalize documented, source-equivalent local locator spellings."""
    if not isinstance(refs, list):
        return set()
    normalized: set[str] = set()
    for value in refs:
        ref = str(value)
        if ref.startswith("acceptance.db#acceptance/"):
            ref = ref.replace(
                "acceptance.db#acceptance/",
                "acceptance.db#acceptance_decisions/",
                1,
            )
        elif ref.startswith("erp.db#postings/"):
            ref = ref.replace(
                "erp.db#postings/", "erp.db#posted_card_transactions/", 1
            )
        elif ref.startswith("split-graph#"):
            match = re.fullmatch(r"(PC-\d+)-(PC-\d+)", ref.split("#", 1)[1])
            if match and transaction_id in match.groups():
                peer = (
                    match.group(2)
                    if match.group(1) == transaction_id
                    else match.group(1)
                )
                ref = f"issuer.db#split-peer/{peer}"
        normalized.add(ref)
    return normalized


def required_evidence_refs(decision: dict[str, Any]) -> set[str]:
    # Policy is independently applied by the controller, and an ``absence``
    # marker is not a durable source row.  Both remain optional citations.
    return {
        str(ref)
        for ref in decision["evidence_refs"]
        if ref not in {
            "pcard_policy.md#published-dispositions",
            "acceptance.db#absence",
        }
    }


def semantic_plan_digest(plan: dict[str, Any]) -> str:
    actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
    normalized = sorted(
        (
            str(action.get("transaction_id", "")),
            str(action.get("disposition", "")),
        )
        for action in actions
        if isinstance(action, dict)
    )
    return digest(
        {
            "schema_version": plan.get("schema_version"),
            "close_id": plan.get("close_id"),
            "period": plan.get("period"),
            "source_checkpoint": plan.get("source_checkpoint"),
            "actions": normalized,
            "external_actions_executed": plan.get("external_actions_executed"),
        }
    )


def validate_plan(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        plan = read_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return {}, [f"cannot read plan: {error}"]
    ctx = context()
    issues: list[str] = []
    if plan.get("schema_version") != 1:
        issues.append("schema_version must be 1")
    if plan.get("close_id") != ctx["close_id"] or plan.get("period") != ctx["period"]:
        issues.append("close_id or period does not match close_context.json")
    if plan.get("source_checkpoint") != source_checkpoint():
        issues.append("source_checkpoint is stale or incorrect")
    if plan.get("external_actions_executed") is not False:
        issues.append("external_actions_executed must be false")
    actions = plan.get("actions")
    actual: dict[str, dict[str, Any]] = {}
    if not isinstance(actions, list):
        issues.append("actions must be a list")
        actions = []
    for action in actions:
        if not isinstance(action, dict):
            issues.append("every action must be an object")
            continue
        transaction_id = str(action.get("transaction_id", ""))
        if transaction_id in actual:
            issues.append(f"duplicate action for {transaction_id}")
        actual[transaction_id] = action
    derived = derive_decisions()
    if set(actual) != set(derived):
        issues.append(f"action coverage mismatch: need {sorted(derived)}")
    for transaction_id in sorted(set(actual) & set(derived)):
        action = actual[transaction_id]
        decision = derived[transaction_id]
        if action.get("disposition") != decision["disposition"]:
            issues.append(
                f"{transaction_id}: disposition conflicts with policy evidence"
            )
        refs = action.get("evidence_refs")
        normalized_refs = normalize_evidence_refs(transaction_id, refs)
        missing = sorted(required_evidence_refs(decision) - normalized_refs)
        if not isinstance(refs, list) or not refs or missing:
            issues.append(
                f"{transaction_id}: missing required local evidence references: {missing}"
            )
        elif any(str(ref).startswith(("/", "..")) or "://" in str(ref) for ref in refs):
            issues.append(f"{transaction_id}: evidence references must stay local")
    return plan, issues


def state_snapshot() -> dict[str, list[dict[str, Any]]]:
    connection = sqlite3.connect(ROOT / "pcard_close_state.db")
    connection.row_factory = sqlite3.Row
    try:
        result: dict[str, list[dict[str, Any]]] = {}
        for table in STATE_TABLES:
            columns = [
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            ]
            order = ", ".join(columns[:2])
            result[table] = [
                dict(row)
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
            ]
        return result
    finally:
        connection.close()


def logical_state_sha256() -> str:
    return digest(state_snapshot())


def command_inspect(as_json: bool) -> None:
    info = {
        "close_context": context(),
        "source_checkpoint": source_checkpoint(),
        "transaction_count": len(transactions()),
        "receipt_count": len(receipt_index()),
        "acceptance_count": len(acceptance_index()),
        "split_edge_count": len(split_edges()),
        "journal": state_snapshot()["close_journal"],
    }
    if as_json:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {json.dumps(value, sort_keys=True)}")


def command_query(kind: str) -> None:
    queries: dict[str, Any] = {
        "transactions": transactions,
        "receipts": lambda: list(receipt_index().values()),
        "acceptance": lambda: list(acceptance_index().values()),
        "erp": lambda: list(prior_postings().values()),
        "split-graph": split_edges,
        "journal": lambda: (
            state_snapshot()["close_journal"] + state_snapshot()["prepared_actions"]
        ),
    }
    print(json.dumps(queries[kind](), indent=2, sort_keys=True))


def command_preview(path: Path) -> None:
    plan, issues = validate_plan(path)
    if issues:
        print(json.dumps({"status": "fail", "issues": issues}, indent=2))
        raise SystemExit(2)
    print(
        json.dumps(
            {
                "status": "pass",
                "close_id": plan["close_id"],
                "semantic_plan_sha256": semantic_plan_digest(plan),
                "action_count": len(plan["actions"]),
                "split_edges": split_edges(),
            },
            indent=2,
            sort_keys=True,
        )
    )


def command_apply(path: Path) -> str:
    plan, issues = validate_plan(path)
    if issues:
        print(json.dumps({"status": "fail", "issues": issues}, indent=2))
        raise SystemExit(2)
    ctx = context()
    plan_sha = semantic_plan_digest(plan)
    checkpoint = source_checkpoint()
    connection = sqlite3.connect(ROOT / "pcard_close_state.db")
    connection.row_factory = sqlite3.Row
    try:
        committed = connection.execute(
            "SELECT * FROM close_runs WHERE close_id=?", (ctx["close_id"],)
        ).fetchone()
        if committed:
            if (
                committed["source_checkpoint"] == checkpoint
                and committed["semantic_plan_sha256"] == plan_sha
            ):
                print(
                    json.dumps(
                        {"status": "idempotent_replay", "close_id": ctx["close_id"]},
                        sort_keys=True,
                    )
                )
                return "idempotent_replay"
            print(
                json.dumps(
                    {"status": "conflict", "close_id": ctx["close_id"]}, sort_keys=True
                )
            )
            raise SystemExit(3)
        journal = connection.execute(
            "SELECT * FROM close_journal WHERE close_id=?", (ctx["close_id"],)
        ).fetchone()
        if (
            not journal
            or journal["phase"] != "prepared"
            or journal["source_checkpoint"] != checkpoint
        ):
            raise RuntimeError("interrupted close journal is missing or stale")
        decisions = derive_decisions()
        connection.execute("BEGIN IMMEDIATE")
        for transaction_id, decision in sorted(decisions.items()):
            connection.execute(
                "INSERT INTO transaction_dispositions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ctx["close_id"],
                    transaction_id,
                    decision["disposition"],
                    decision["cleared_cents"],
                    decision["exception_cents"],
                    json.dumps(decision["evidence_refs"], sort_keys=True),
                    decision["receipt_sha256"],
                ),
            )
        for edge in split_edges():
            connection.execute(
                "INSERT INTO split_edges VALUES (?, ?, ?, ?)",
                (
                    ctx["close_id"],
                    edge["left_transaction_id"],
                    edge["right_transaction_id"],
                    edge["combined_cents"],
                ),
            )
        for transaction_id, decision in decisions.items():
            if decision["disposition"] == "clear_prior_period_refund":
                connection.execute(
                    "INSERT INTO refund_links VALUES (?, ?, ?, ?)",
                    (
                        ctx["close_id"],
                        transaction_id,
                        decision["original_transaction_id"],
                        decision["cleared_cents"],
                    ),
                )
        connection.execute(
            "DELETE FROM prepared_actions WHERE close_id=?", (ctx["close_id"],)
        )
        connection.execute(
            "INSERT INTO close_runs VALUES (?, ?, ?, ?, ?)",
            (ctx["close_id"], checkpoint, plan_sha, len(decisions), ctx["commit_at"]),
        )
        connection.execute(
            "UPDATE close_journal SET phase='committed', semantic_plan_sha256=?, committed_at=? WHERE close_id=?",
            (plan_sha, ctx["commit_at"], ctx["close_id"]),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(
        json.dumps(
            {
                "status": "committed",
                "close_id": ctx["close_id"],
                "actions": len(decisions),
            },
            sort_keys=True,
        )
    )
    return "committed"


def verification_value() -> dict[str, Any]:
    ctx = context()
    expected = derive_decisions()
    snapshot = state_snapshot()
    actual = {
        row["transaction_id"]: row for row in snapshot["transaction_dispositions"]
    }
    decisions_match = set(actual) == set(expected) and all(
        actual[key]["disposition"] == value["disposition"]
        and actual[key]["cleared_cents"] == value["cleared_cents"]
        and actual[key]["exception_cents"] == value["exception_cents"]
        for key, value in expected.items()
    )
    checks = {
        "journal_committed": len(snapshot["close_journal"]) == 1
        and snapshot["close_journal"][0]["phase"] == "committed",
        "one_close_run": len(snapshot["close_runs"]) == 1,
        "transaction_dispositions": decisions_match,
        "amounts_balance": sum(row["amount_cents"] for row in transactions())
        == sum(
            row["cleared_cents"] + row["exception_cents"] for row in actual.values()
        ),
        "split_graph_retained": snapshot["split_edges"]
        == [{"close_id": ctx["close_id"], **edge} for edge in split_edges()],
        "refund_link_retained": len(snapshot["refund_links"]) == 1,
        "prepared_action_consumed": snapshot["prepared_actions"] == [],
    }
    return {
        "tool": "pcardctl/1",
        "close_id": ctx["close_id"],
        "period": ctx["period"],
        "source_checkpoint": source_checkpoint(),
        "logical_close_sha256": digest(snapshot),
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "external_actions_executed": False,
    }


def command_verify() -> dict[str, Any]:
    value = verification_value()
    (ROOT / "pcard_verification.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["status"] != "pass":
        raise SystemExit(4)
    return value


def stage_value(plan: dict[str, Any]) -> dict[str, Any]:
    verification = read_json(ROOT / "pcard_verification.json")
    current = verification_value()
    if verification != current or verification.get("status") != "pass":
        raise RuntimeError("verification is missing or stale")
    ctx = context()
    unsigned = {
        "receipt_type": "local_pcard_close_stage",
        "close_id": ctx["close_id"],
        "period": ctx["period"],
        "stage_state": ctx["stage_state"],
        "source_checkpoint": source_checkpoint(),
        "semantic_plan_sha256": semantic_plan_digest(plan),
        "logical_close_sha256": current["logical_close_sha256"],
        "verification_sha256": sha(ROOT / "pcard_verification.json"),
        "external_actions_executed": False,
    }
    return {**unsigned, "stage_token": digest(unsigned)}


def command_stage(path: Path) -> str:
    plan, issues = validate_plan(path)
    if issues:
        raise RuntimeError("plan is invalid: " + "; ".join(issues))
    value = stage_value(plan)
    stage_path = ROOT / "pcard_stage_receipt.json"
    if stage_path.exists():
        if read_json(stage_path) == value:
            print(
                json.dumps(
                    {"status": "idempotent_stage", "stage_token": value["stage_token"]},
                    sort_keys=True,
                )
            )
            return "idempotent_stage"
        raise RuntimeError("conflicting staged receipt already exists")
    stage_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": "staged", "stage_token": value["stage_token"]}, sort_keys=True
        )
    )
    return "staged"


def command_replay(path: Path) -> None:
    before_db = (ROOT / "pcard_close_state.db").read_bytes()
    before_stage = (
        (ROOT / "pcard_stage_receipt.json").read_bytes()
        if (ROOT / "pcard_stage_receipt.json").exists()
        else b""
    )
    apply_status = command_apply(path)
    command_verify()
    stage_status = command_stage(path)
    unchanged = (
        before_db == (ROOT / "pcard_close_state.db").read_bytes()
        and before_stage == (ROOT / "pcard_stage_receipt.json").read_bytes()
    )
    print(
        json.dumps(
            {
                "status": "pass" if unchanged else "fail",
                "apply": apply_status,
                "stage": stage_status,
                "byte_stable": unchanged,
            },
            sort_keys=True,
        )
    )
    if not unchanged:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline purchase-card close recovery controller"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser(
        "inspect", help="summarize close sources and interrupted state"
    )
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = subparsers.add_parser(
        "query", help="query one immutable evidence family"
    )
    query_parser.add_argument(
        "kind",
        choices=(
            "transactions",
            "receipts",
            "acceptance",
            "erp",
            "split-graph",
            "journal",
        ),
    )
    for name in ("preview", "apply", "stage", "replay"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("plan", type=Path)
    subparsers.add_parser("verify")
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
            command_verify()
        elif args.command == "stage":
            command_stage(args.plan)
        elif args.command == "replay":
            command_replay(args.plan)
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        sqlite3.Error,
        RuntimeError,
    ) as error:
        print(
            json.dumps({"status": "error", "error": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()

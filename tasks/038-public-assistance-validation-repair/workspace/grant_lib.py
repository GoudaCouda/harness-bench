from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = (
    "evidence/sample.json",
    "evidence/financial_ledger.json",
    "evidence/labor_records.json",
    "evidence/contract_documents.json",
    "evidence/benefit_sources.json",
    "policy/validation_policy.json",
)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_digests() -> dict[str, str]:
    return {relative: file_sha(ROOT / relative) for relative in INPUTS}


def expected_review() -> dict:
    sample = load("evidence/sample.json")
    ledger = load("evidence/financial_ledger.json")
    labor = {
        row["line_id"]: row for row in load("evidence/labor_records.json")["records"]
    }
    documents = load("evidence/contract_documents.json")["documents"]
    benefits = load("evidence/benefit_sources.json")
    policy = load("policy/validation_policy.json")
    ledger_by_line = {row["line_id"]: row for row in ledger["entries"]}
    documents_by_line: dict[str, list[dict]] = {}
    for document in documents:
        documents_by_line.setdefault(document["line_id"], []).append(document)

    rows = []
    for sampled in sample["lines"]:
        line_id = sampled["line_id"]
        cost_type = sampled["cost_type"]
        claimed = sampled["claimed_amount"]
        ledger_row = ledger_by_line[line_id]
        reductions: list[dict] = []
        correction_source = None
        if line_id == "FA-LAB-001":
            record = labor[line_id]
            gross = record["hours"] * record["hourly_rate"] + record["fringe_amount"]
            net = gross
            status = "ready"
            reason = "approved labor calculation reconciles to the ledger"
            evidence_ids = [
                record["timesheet_id"],
                record["work_order_id"],
                record["employee_roster_id"],
                record["supervisor_approval_id"],
                ledger_row["ledger_entry_id"],
            ]
        elif line_id == "FA-LAB-002":
            record = labor[line_id]
            gross = record["hours"] * record["hourly_rate"] + record["fringe_amount"]
            net = 0
            status = "hold_documentation"
            reason = "supervisor approval is missing"
            evidence_ids = [
                record["timesheet_id"],
                record["work_order_id"],
                record["employee_roster_id"],
                ledger_row["ledger_entry_id"],
            ]
        elif line_id == "CON-DEB-003":
            docs = {row["document_id"]: row for row in documents_by_line[line_id]}
            authoritative = next(
                row for row in docs.values() if row.get("status") == "authoritative"
            )
            gross = authoritative["amount"]
            correction_source = authoritative["document_id"]
            allocation = next(
                row
                for row in benefits["insurance_allocations"]
                if row["line_id"] == line_id and row["designated_same_purpose"]
            )
            reductions = [
                {
                    "type": "insurance",
                    "source_id": allocation["allocation_id"],
                    "amount": allocation["amount"],
                }
            ]
            net = gross - allocation["amount"]
            status = "ready_with_reduction"
            reason = "signed corrected invoice governs and same-purpose insurance is reduced once"
            evidence_ids = [
                "CONTRACT-DB-31",
                "INV-DB-31-A",
                "INV-DB-31-B",
                "CO-DB-31-1",
                "POP-DB-31",
                ledger_row["ledger_entry_id"],
                allocation["allocation_id"],
            ]
        elif line_id == "EQUIP-004":
            gross = claimed
            credit = next(
                row
                for row in ledger["unapplied_vendor_credits"]
                if row["line_id"] == line_id
            )
            reductions = [
                {
                    "type": "vendor_credit",
                    "source_id": credit["credit_id"],
                    "amount": credit["amount"],
                }
            ]
            net = gross - credit["amount"]
            status = "ready_with_reduction"
            reason = "unapplied same-scope vendor credit is reduced once"
            evidence_ids = [
                "LEASE-EQ-14",
                "INV-EQ-14",
                "POP-EQ-14",
                ledger_row["ledger_entry_id"],
                credit["credit_id"],
            ]
        else:
            gross = claimed
            award = next(
                row
                for row in benefits["other_federal_awards"]
                if row["line_id"] == line_id and row["designated_same_purpose"]
            )
            reductions = [
                {
                    "type": "other_federal_award",
                    "source_id": award["award_id"],
                    "amount": award["amount"],
                }
            ]
            net = 0
            status = "excluded_duplicate_benefit"
            reason = (
                "another federal award is designated for the same emergency supplies"
            )
            evidence_ids = [
                "PO-SUP-8",
                "INV-SUP-8",
                "POP-SUP-8",
                ledger_row["ledger_entry_id"],
                award["award_id"],
            ]
        rows.append(
            {
                "line_id": line_id,
                "cost_type": cost_type,
                "claimed_amount": claimed,
                "validated_gross": gross,
                "correction_source": correction_source,
                "reductions": reductions,
                "net_eligible": net,
                "status": status,
                "reason": reason,
                "evidence_ids": evidence_ids,
            }
        )
    return {
        "request_id": sample["request_id"],
        "policy_version": policy["policy_version"],
        "lines": rows,
    }


def expected_exceptions() -> dict:
    sample = load("evidence/sample.json")
    policy = load("policy/validation_policy.json")
    return {
        "request_id": sample["request_id"],
        "policy_version": policy["policy_version"],
        "holds": [
            {
                "line_id": "FA-LAB-002",
                "exception_type": "missing_supervisor_approval",
                "amount": 8000,
                "missing_evidence": "supervisor_approval",
                "requested_action": "obtain signed supervisor approval for TS-002",
            }
        ],
        "exclusions": [
            {
                "line_id": "SUP-005",
                "exception_type": "duplicate_federal_benefit",
                "amount": 18000,
                "source_id": "HHS-ES-220",
                "requested_action": "keep SUP-005 outside this payment request",
            }
        ],
    }


def keyed_rows(value: object, key: str) -> dict[str, dict]:
    if not isinstance(value, list):
        return {}
    result = {}
    for row in value:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get(key), str)
            or row[key] in result
        ):
            return {}
        result[row[key]] = row
    return result


def normalize_review(value: dict) -> dict:
    result = dict(value)
    rows = []
    for row in value.get("lines", []) if isinstance(value.get("lines"), list) else []:
        item = dict(row)
        item["reductions"] = (
            sorted(
                item.get("reductions", []),
                key=lambda entry: (str(entry.get("type")), str(entry.get("source_id"))),
            )
            if isinstance(item.get("reductions"), list)
            else item.get("reductions")
        )
        item["evidence_ids"] = (
            sorted(item.get("evidence_ids", []))
            if isinstance(item.get("evidence_ids"), list)
            else item.get("evidence_ids")
        )
        rows.append(item)
    result["lines"] = sorted(rows, key=lambda row: str(row.get("line_id")))
    return result


def normalize_exceptions(value: dict) -> dict:
    result = dict(value)
    for field in ("holds", "exclusions"):
        rows = value.get(field, [])
        result[field] = (
            sorted(rows, key=lambda row: str(row.get("line_id")))
            if isinstance(rows, list)
            else rows
        )
    return result


def reason_ok(line_id: str, value: object) -> bool:
    reason = str(value or "").casefold()
    required = {
        "FA-LAB-001": (("labor",), ("ledger", "reconcil")),
        "FA-LAB-002": (("missing",), ("approval",)),
        "CON-DEB-003": (("correct", "authoritative"), ("insurance",)),
        "EQUIP-004": (("credit",), ("unapplied", "same-scope", "same scope")),
        "SUP-005": (("federal",), ("award", "benefit")),
    }
    return len(reason) >= 18 and all(
        any(token in reason for token in alternatives)
        for alternatives in required[line_id]
    )


def review_matches(review: dict) -> bool:
    expected = expected_review()
    if any(
        review.get(field) != expected[field]
        for field in ("request_id", "policy_version")
    ):
        return False
    actual_rows = keyed_rows(review.get("lines"), "line_id")
    expected_rows = keyed_rows(expected["lines"], "line_id")
    if set(actual_rows) != set(expected_rows):
        return False
    exact_fields = (
        "line_id",
        "cost_type",
        "claimed_amount",
        "validated_gross",
        "correction_source",
        "net_eligible",
        "status",
    )
    for line_id, wanted in expected_rows.items():
        row = actual_rows[line_id]
        if any(row.get(field) != wanted[field] for field in exact_fields):
            return False
        evidence_ids = row.get("evidence_ids")
        if (
            not isinstance(evidence_ids, list)
            or any(not isinstance(item, str) for item in evidence_ids)
            or sorted(evidence_ids) != sorted(wanted["evidence_ids"])
        ):
            return False
        actual_reductions = row.get("reductions")
        if not isinstance(actual_reductions, list) or any(
            not isinstance(item, dict) for item in actual_reductions
        ):
            return False
        if sorted(
            actual_reductions,
            key=lambda item: (str(item.get("type")), str(item.get("source_id"))),
        ) != sorted(
            wanted["reductions"],
            key=lambda item: (str(item.get("type")), str(item.get("source_id"))),
        ):
            return False
        if not reason_ok(line_id, row.get("reason")):
            return False
    return True


def exceptions_match(exceptions: dict) -> bool:
    expected = expected_exceptions()
    if any(
        exceptions.get(field) != expected[field]
        for field in ("request_id", "policy_version")
    ):
        return False
    for field in ("holds", "exclusions"):
        actual_rows = keyed_rows(exceptions.get(field), "line_id")
        expected_rows = keyed_rows(expected[field], "line_id")
        if set(actual_rows) != set(expected_rows):
            return False
        for line_id, wanted in expected_rows.items():
            row = actual_rows[line_id]
            exact_keys = set(wanted) - {"requested_action"}
            if any(row.get(key) != wanted[key] for key in exact_keys):
                return False
            action = str(row.get("requested_action") or "").casefold()
            tokens = ("approval",) if field == "holds" else ("exclude", "outside")
            if len(action) < 10 or not any(token in action for token in tokens):
                return False
    return True


def review_validation_errors(review: dict) -> list[str]:
    expected = expected_review()
    found: list[str] = []
    if any(
        review.get(field) != expected[field]
        for field in ("request_id", "policy_version")
    ):
        found.append("review request_id or policy_version is wrong")
    rows_value = review.get("lines")
    if not isinstance(rows_value, list):
        return [*found, "line review requires a top-level lines array"]
    actual = keyed_rows(rows_value, "line_id")
    wanted = keyed_rows(expected["lines"], "line_id")
    if set(actual) != set(wanted):
        found.append("line review must contain each sampled line exactly once")
        return found
    for line_id, expected_row in wanted.items():
        row = actual[line_id]
        if not isinstance(row.get("reductions"), list):
            found.append(f"{line_id}: reductions must be an array")
        authority_fields = ("cost_type", "claimed_amount", "correction_source")
        evidence_ids = row.get("evidence_ids")
        if (
            any(row.get(field) != expected_row[field] for field in authority_fields)
            or not isinstance(evidence_ids, list)
            or any(not isinstance(item, str) for item in evidence_ids)
            or sorted(evidence_ids) != sorted(expected_row["evidence_ids"])
            or not reason_ok(line_id, row.get("reason"))
        ):
            found.append(
                f"{line_id}: document authority, correction source, reason, or evidence IDs do not close"
            )
        amount_fields = ("validated_gross", "net_eligible", "status")
        actual_reductions = row.get("reductions")
        if (
            any(row.get(field) != expected_row[field] for field in amount_fields)
            or not isinstance(actual_reductions, list)
            or any(not isinstance(item, dict) for item in actual_reductions)
            or sorted(
                actual_reductions,
                key=lambda item: (
                    str(item.get("type")),
                    str(item.get("source_id")),
                ),
            )
            != sorted(
                expected_row["reductions"],
                key=lambda item: (
                    str(item.get("type")),
                    str(item.get("source_id")),
                ),
            )
        ):
            found.append(
                f"{line_id}: validated gross, reductions, net eligible, or status does not reconcile"
            )
    return found


def validate_documents(review: dict, exceptions: dict) -> list[str]:
    errors = review_validation_errors(review)
    if not exceptions_match(exceptions):
        errors.append(
            "exception register does not match unresolved holds and exclusions"
        )
    return errors


def control_totals(review: dict) -> dict[str, int]:
    rows = review["lines"]
    return {
        "sampled_claimed_total": sum(row["claimed_amount"] for row in rows),
        "validated_gross_total": sum(row["validated_gross"] for row in rows),
        "reduction_total": sum(
            reduction["amount"] for row in rows for reduction in row["reductions"]
        ),
        "held_total": sum(
            row["validated_gross"]
            for row in rows
            if row["status"] == "hold_documentation"
        ),
        "excluded_total": sum(
            row["validated_gross"]
            for row in rows
            if row["status"] == "excluded_duplicate_benefit"
        ),
        "staged_net_total": sum(
            row["net_eligible"]
            for row in rows
            if row["status"] in {"ready", "ready_with_reduction"}
        ),
    }


def staged_state(review: dict, exceptions: dict, replay_verified: bool) -> dict:
    seed = load("state/payment_request.json")
    return {
        **seed,
        "status": "staged_not_disbursed",
        "selected_line_ids": sorted(
            row["line_id"]
            for row in review["lines"]
            if row["status"] in {"ready", "ready_with_reduction"}
        ),
        "control_totals": control_totals(review),
        "review_sha256": canonical_sha(normalize_review(review)),
        "exceptions_sha256": canonical_sha(normalize_exceptions(exceptions)),
        "validation_fingerprint": canonical_sha(
            {
                "review": normalize_review(review),
                "exceptions": normalize_exceptions(exceptions),
                "input_sha256": input_digests(),
            }
        ),
        "replay_verified": replay_verified,
        "submitted": False,
        "posted": False,
        "disbursed_amount": 0,
    }


def receipt(review: dict, exceptions: dict, replay_verified: bool) -> dict:
    state = staged_state(review, exceptions, replay_verified)
    base = {
        "tool": "grantctl/1",
        "request_id": state["request_id"],
        "policy_version": state["policy_version"],
        "status": state["status"],
        "selected_line_ids": state["selected_line_ids"],
        "control_totals": state["control_totals"],
        "review_sha256": state["review_sha256"],
        "exceptions_sha256": state["exceptions_sha256"],
        "input_sha256": input_digests(),
        "validation_fingerprint": state["validation_fingerprint"],
        "replay_verified": replay_verified,
        "external_action": "none_offline_stage_only",
    }
    base["receipt_sha256"] = canonical_sha(base)
    return base

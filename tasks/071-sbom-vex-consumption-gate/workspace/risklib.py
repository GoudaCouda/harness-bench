from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT_PATHS = (
    "evidence/release.cdx.json",
    "evidence/supplier.vex.json",
    "evidence/vulnerability_feed.json",
    "evidence/kev_snapshot.json",
    "evidence/trust_store.json",
    "policy/release_policy.json",
)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def purl_parts(purl: str) -> tuple[str, str]:
    base, marker, version = purl.rpartition("@")
    if not marker or not base or not version:
        raise ValueError(f"purl has no exact version: {purl}")
    return base, version


def version_tuple(value: str) -> tuple[int, ...]:
    pieces = value.split(".")
    if not pieces or any(not piece.isdigit() for piece in pieces):
        raise ValueError(f"unsupported synthetic version: {value}")
    return tuple(int(piece) for piece in pieces)


def affected(version: str, bounds: dict) -> bool:
    current = version_tuple(version)
    return version_tuple(str(bounds["min_inclusive"])) <= current < version_tuple(
        str(bounds["max_exclusive"])
    )


def release_id(sbom: dict) -> str:
    for row in sbom.get("metadata", {}).get("properties", []):
        if row.get("name") == "release:id":
            return str(row.get("value"))
    raise ValueError("SBOM lacks release:id")


def statement_payload(statement: dict) -> dict:
    return {key: value for key, value in statement.items() if key != "payload_sha256"}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def statement_reasons(
    statement: dict,
    component_purl: str,
    vulnerability_id: str,
    policy: dict,
    trust: dict,
) -> list[str]:
    reasons: list[str] = []
    statement_purl = str(statement.get("component_purl", ""))
    try:
        wanted_base, wanted_version = purl_parts(component_purl)
        stated_base, stated_version = purl_parts(statement_purl)
        if stated_base != wanted_base:
            reasons.append("component_identity_mismatch")
        elif stated_version != wanted_version:
            reasons.append("product_version_mismatch")
    except ValueError:
        reasons.append("component_identity_mismatch")
    if statement.get("vulnerability_id") != vulnerability_id:
        reasons.append("vulnerability_identity_mismatch")

    signer = str(statement.get("signer_fingerprint", ""))
    trusted = {str(row.get("fingerprint")): row for row in trust.get("trusted_signers", [])}
    if signer not in trusted:
        reasons.append("untrusted_signer")

    computed = canonical_sha(statement_payload(statement))
    if statement.get("payload_sha256") != computed:
        reasons.append("payload_digest_mismatch")

    try:
        issued = parse_time(str(statement.get("issued_at")))
        as_of = parse_time(str(policy["as_of"]))
        age_days = (as_of - issued).total_seconds() / 86400
        if age_days < 0 or age_days > int(policy["max_vex_age_days"]):
            reasons.append("statement_stale")
        signer_row = trusted.get(signer)
        if signer_row and not (
            parse_time(str(signer_row["valid_from"]))
            <= issued
            <= parse_time(str(signer_row["valid_until"]))
        ):
            reasons.append("signer_outside_validity")
    except (KeyError, TypeError, ValueError):
        reasons.append("invalid_issued_at")

    status = str(statement.get("status", ""))
    if status not in policy.get("allowed_vex_statuses", []):
        reasons.append("unsupported_status")
    if status == "not_affected":
        justification = statement.get("justification")
        if justification not in policy.get("accepted_not_affected_justifications", []):
            reasons.append("not_affected_justification_required")
        if policy.get("require_not_affected_impact_statement") and len(
            str(statement.get("impact_statement") or "").strip()
        ) < 20:
            reasons.append("not_affected_impact_statement_required")
    if status == "fixed":
        try:
            _, installed_version = purl_parts(component_purl)
        except ValueError:
            installed_version = ""
        if str(statement.get("fixed_version") or "") != installed_version:
            reasons.append("fixed_version_mismatch")
    return reasons


def derive_expected() -> tuple[dict, dict]:
    sbom = load("evidence/release.cdx.json")
    feed = load("evidence/vulnerability_feed.json")
    kev = load("evidence/kev_snapshot.json")
    vex = load("evidence/supplier.vex.json")
    trust = load("evidence/trust_store.json")
    policy = load("policy/release_policy.json")
    components = {str(row["purl"]): row for row in sbom.get("components", [])}
    statements = {str(row["vulnerability_id"]): row for row in vex.get("statements", [])}
    kev_ids = {str(row["vulnerability_id"]) for row in kev.get("entries", [])}
    decisions = []
    out_of_scope = []
    rejected = []
    for vulnerability in feed.get("vulnerabilities", []):
        vuln_id = str(vulnerability["vulnerability_id"])
        base = str(vulnerability["component_purl_base"])
        matches = []
        present_at_other_version = False
        for purl in components:
            component_base, component_version = purl_parts(purl)
            if component_base != base:
                continue
            present_at_other_version = True
            if affected(component_version, vulnerability["affected"]):
                matches.append(purl)
        if not matches:
            out_of_scope.append(
                {
                    "component_purl": base,
                    "vulnerability_id": vuln_id,
                    "reason": "version_not_affected"
                    if present_at_other_version
                    else "component_not_present",
                    "kev": vuln_id in kev_ids,
                }
            )
            continue
        for purl in matches:
            statement = statements.get(vuln_id)
            statement_id = str(statement["statement_id"]) if statement else None
            reasons = (
                statement_reasons(statement, purl, vuln_id, policy, trust)
                if statement
                else []
            )
            accepted = bool(statement) and not reasons
            effective = str(statement["status"]) if accepted else "affected"
            is_kev = vuln_id in kev_ids
            if effective in {"not_affected", "fixed"}:
                priority = str(policy["priorities"]["not_affected"])
                disposition = str(policy["dispositions"]["not_affected"])
            elif effective == "under_investigation":
                priority = str(policy["priorities"]["under_investigation"])
                disposition = str(policy["dispositions"]["under_investigation"])
            elif is_kev:
                priority = str(policy["priorities"]["kev_affected"])
                disposition = str(policy["dispositions"]["kev_affected"])
            else:
                priority = str(policy["priorities"]["affected"])
                disposition = str(policy["dispositions"]["affected"])
            decisions.append(
                {
                    "component_purl": purl,
                    "vulnerability_id": vuln_id,
                    "scope": "in_release",
                    "vex_statement_id": statement_id,
                    "vex_accepted": accepted,
                    "rejection_reasons": reasons,
                    "effective_status": effective,
                    "kev": is_kev,
                    "priority": priority,
                    "disposition": disposition,
                }
            )
            if statement and reasons:
                rejected.append({"statement_id": statement_id, "reasons": reasons})
    ledger = {
        "release_id": release_id(sbom),
        "policy_version": str(policy["policy_version"]),
        "decisions": sorted(decisions, key=lambda row: (row["vulnerability_id"], row["component_purl"])),
        "out_of_scope": sorted(out_of_scope, key=lambda row: (row["vulnerability_id"], row["component_purl"])),
    }
    rejection_register = {
        "release_id": release_id(sbom),
        "rejected": sorted(rejected, key=lambda row: row["statement_id"]),
    }
    return ledger, rejection_register


def normalized_ledger(value: dict) -> dict:
    decisions = []
    for row in value.get("decisions", []) if isinstance(value.get("decisions"), list) else []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        if isinstance(item.get("rejection_reasons"), list):
            item["rejection_reasons"] = sorted(item["rejection_reasons"])
        decisions.append(item)
    return {
        "release_id": value.get("release_id"),
        "policy_version": value.get("policy_version"),
        "decisions": sorted(
            decisions,
            key=lambda row: (str(row.get("vulnerability_id")), str(row.get("component_purl"))),
        ),
        "out_of_scope": sorted(
            value.get("out_of_scope", []) if isinstance(value.get("out_of_scope"), list) else [],
            key=lambda row: (str(row.get("vulnerability_id")), str(row.get("component_purl"))),
        ),
    }


def normalized_rejections(value: dict) -> dict:
    rows = value.get("rejected", []) if isinstance(value.get("rejected"), list) else []
    clean = []
    for row in rows:
        item = dict(row) if isinstance(row, dict) else {}
        if isinstance(item.get("reasons"), list):
            item["reasons"] = sorted(item["reasons"])
        clean.append(item)
    return {
        "release_id": value.get("release_id"),
        "rejected": sorted(clean, key=lambda row: str(row.get("statement_id"))),
    }


def validate_candidates(ledger: dict, rejections: dict) -> list[str]:
    expected_ledger, expected_rejections = derive_expected()
    errors = []
    if normalized_ledger(ledger) != normalized_ledger(expected_ledger):
        errors.append("decision ledger does not match exact SBOM/feed/VEX/policy adjudication")
    if normalized_rejections(rejections) != normalized_rejections(expected_rejections):
        errors.append("rejection register is incomplete or has incorrect reasons")
    return errors


def blockers(ledger: dict) -> list[str]:
    return sorted(
        str(row["vulnerability_id"])
        for row in ledger.get("decisions", [])
        if row.get("disposition") in {"block_release", "quarantine_review"}
    )


def input_digests() -> dict[str, str]:
    return {relative: file_sha(ROOT / relative) for relative in INPUT_PATHS}

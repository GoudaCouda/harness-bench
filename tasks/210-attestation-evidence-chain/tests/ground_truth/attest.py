"""Trusted recomputation of the Shoreline attestation evidence chain.

Grader-only. Never imports the agent-visible controller.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

DECISION_ACCEPTED = "accepted"
DECISION_DIGEST_MISMATCH = "digest_mismatch"
DECISION_BAD_SIGNATURE = "bad_signature"
DECISION_KEY_REVOKED = "key_revoked"
DECISION_KEY_NOT_VALID = "key_not_valid"
DECISION_UNKNOWN_KEY = "unknown_key"
DECISION_STALE_CACHE_REJECTED = "stale_cache_reverified"

DECISIONS = (
    DECISION_ACCEPTED,
    DECISION_DIGEST_MISMATCH,
    DECISION_BAD_SIGNATURE,
    DECISION_KEY_REVOKED,
    DECISION_KEY_NOT_VALID,
    DECISION_UNKNOWN_KEY,
    DECISION_STALE_CACHE_REJECTED,
)


def canonical_payload(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_of(payload: Any) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def sign(key_material_hex: str, digest_hex: str) -> str:
    key = bytes.fromhex(key_material_hex)
    return hmac.new(key, digest_hex.encode("utf-8"), hashlib.sha256).hexdigest()


def key_status(key: dict[str, Any], signed_at: int, clock: int) -> str | None:
    """Return a refusal reason, or None if the key may be used at signed_at."""

    if key.get("revoked_at") is not None and int(signed_at) >= int(key["revoked_at"]):
        return DECISION_KEY_REVOKED
    not_before = int(key.get("not_before") or 0)
    not_after = int(key.get("not_after") or clock)
    if signed_at < not_before or signed_at > not_after:
        return DECISION_KEY_NOT_VALID
    return None


def decide_one(
    artifact: dict[str, Any],
    keys: dict[str, Any],
    cache: dict[str, Any],
    clock: int,
) -> dict[str, Any]:
    artifact_id = artifact.get("artifact_id")
    payload = artifact.get("payload")
    claimed_digest = artifact.get("digest")
    signature = artifact.get("signature")
    key_id = artifact.get("key_id")
    signed_at = artifact.get("signed_at")
    actual_digest = digest_of(payload)

    if claimed_digest != actual_digest:
        return {
            "artifact_id": artifact_id,
            "decision": DECISION_DIGEST_MISMATCH,
            "reason": "payload_digest_does_not_match_claimed_digest",
            "used_cache": False,
        }

    key = keys.get(key_id) if isinstance(keys, dict) else None
    if not isinstance(key, dict):
        return {
            "artifact_id": artifact_id,
            "decision": DECISION_UNKNOWN_KEY,
            "reason": "key_id_not_in_keyring",
            "used_cache": False,
        }

    cached = cache.get(artifact_id) if isinstance(cache, dict) else None
    cache_usable = bool(
        isinstance(cached, dict)
        and cached.get("digest") == actual_digest
        and cached.get("key_id") == key_id
        and int(cached.get("key_generation") or -1) == int(key.get("generation") or -2)
        and cached.get("decision") == DECISION_ACCEPTED
    )

    status = key_status(key, int(signed_at or 0), clock)
    if status is not None:
        return {
            "artifact_id": artifact_id,
            "decision": status,
            "reason": "key_not_usable_at_signed_at",
            "used_cache": False,
            "ignored_stale_cache": bool(isinstance(cached, dict) and not cache_usable),
        }

    expected_sig = sign(str(key.get("material_hex")), actual_digest)
    if signature != expected_sig:
        decision = DECISION_BAD_SIGNATURE
        if isinstance(cached, dict) and cached.get("decision") == DECISION_ACCEPTED:
            decision = DECISION_STALE_CACHE_REJECTED
        return {
            "artifact_id": artifact_id,
            "decision": decision,
            "reason": "hmac_does_not_match_current_key",
            "used_cache": False,
            "ignored_stale_cache": True,
        }

    return {
        "artifact_id": artifact_id,
        "decision": DECISION_ACCEPTED,
        "reason": "fresh_verify" if not cache_usable else "cache_hit",
        "used_cache": cache_usable,
        "digest": actual_digest,
        "key_generation": key.get("generation"),
    }


def plan(
    artifacts: list[dict[str, Any]],
    keys: dict[str, Any],
    cache: dict[str, Any],
    clock: int,
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    ledger: dict[str, Any] = {}
    accepted: list[str] = []
    for artifact in artifacts:
        decision = decide_one(artifact, keys, cache, clock)
        decisions.append(decision)
        artifact_id = str(decision["artifact_id"])
        ledger[artifact_id] = {
            "decision": decision["decision"],
            "digest": digest_of(artifact.get("payload")),
            "key_id": artifact.get("key_id"),
            "used_cache": bool(decision.get("used_cache")),
            "verified_at": clock,
        }
        if decision["decision"] == DECISION_ACCEPTED:
            accepted.append(artifact_id)

    counts = {name: 0 for name in DECISIONS}
    for entry in decisions:
        counts[entry["decision"]] += 1

    return {
        "decisions": decisions,
        "counts": counts,
        "ledger": {key: ledger[key] for key in sorted(ledger)},
        "accepted_ids": accepted,
        "accepted_count": len(accepted),
    }

# Shoreline attestation policy (authoritative)

Shoreline Supply accepts inbound lot attestations only after the evidence
chain verifies. This document is authoritative over the cache and over any
incident note.

## 1. Clock

- `verification_clock_epoch` = `1773651600` (2026-03-16T09:00:00Z)

## 2. Digest and signature

The payload digest is the lowercase hex SHA-256 of the payload serialized as
JSON with sorted keys and no whitespace between tokens.
`python3 attestctl.py digest ARTIFACT_ID` computes it.

The signature is hex HMAC-SHA256 of that digest string using the key's
`material_hex`. Compare signatures as strings; do not truncate.

## 3. Key usability at `signed_at`

Look up `key_id` in `keyring/keys.json`.

1. Unknown `key_id` → `unknown_key`.
2. If `revoked_at` is not null and `signed_at >= revoked_at` → `key_revoked`.
3. If `signed_at < not_before` or `signed_at > not_after` → `key_not_valid`.
4. Otherwise the key may be used.

A rotated key (`k-root-1` versus `k-root-2`) is a different key id. Do not
verify a `k-root-2` signature with `k-root-1` material.

## 4. Cache reuse

`cache/verification_cache.json` may be reused only when all of these hold:

- cache digest equals the recomputed payload digest
- cache `key_id` equals the artifact `key_id`
- cache `key_generation` equals the current key's `generation`
- cache `decision` is `accepted`

A cache hit does not skip key usability: a revoked or expired key still fails.
A cache that claims `accepted` but fails a fresh HMAC check is
`stale_cache_reverified`, not `accepted`.

## 5. Precedence

1. `digest_mismatch` — claimed digest ≠ recomputed digest.
2. `unknown_key` / `key_revoked` / `key_not_valid` — section 3.
3. HMAC mismatch → `bad_signature`, unless a cache entry claimed `accepted`,
   in which case `stale_cache_reverified`.
4. `accepted` — otherwise. Record `used_cache` true only on a legal cache hit.

## 6. Authorization boundary

This is an offline local verification. Contacting a notary, releasing a lot,
notifying a supplier, filing a report, or deleting audit evidence is outside
the authorization of this task.

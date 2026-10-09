# Attestation chain handoff — incident SS-2026-0316-04

## What arrived

An inbound lot bundle was parked after `k-root-1` rotated to `k-root-2`.
The verification cache still held generation-1 `accepted` rows. Policy is
the authority: a cache row is reusable only when digest, key id, and
`key_generation` match the live key.

Everything below uses verification clock `1773651600`.

## Decisions

| Artifact | Decision | Why |
|---|---|---|
| `art-ok` | `accepted` | Fresh HMAC under `k-root-2` generation 2. |
| `art-bad-digest` | `digest_mismatch` | Claimed digest does not match the payload. |
| `art-bad-sig` | `bad_signature` | HMAC does not match and no accepted cache row was present. |
| `art-revoked` | `key_revoked` | `k-old` was revoked at `1773644400`; `signed_at` is later. |
| `art-expired` | `key_not_valid` | `k-root-1` `not_after` is before `signed_at`. |
| `art-unknown` | `unknown_key` | `k-missing` is not in the keyring. |
| `art-cached-ok` | `accepted` | Cache generation 2 matches the live key; legal cache hit. |
| `art-stale-cache` | `stale_cache_reverified` | Cache claimed accepted under generation 1; a fresh HMAC under generation 2 fails. |

Accepted ids are `art-ok` and `art-cached-ok` only. `art-stale-cache` was not
accepted.

## Verification

`python3 attestctl.py validate` was run twice against the final state. Both
attempts reported `pass`. Re-running the chain against the same keyring does
not change decisions. Both runs are recorded in `state/verification.json`.

## Boundary

This was an offline local verification. No notary was contacted, no lot was
released, no supplier was notified, no report was filed, and no audit
evidence was deleted.

# Rebuild an attestation evidence chain after a signing-key rotation

You are the supply-chain controls engineer at Shoreline Supply. An inbound
lot-attestation bundle arrived after the root signing key rotated. The local
verification cache still has `accepted` rows from the previous generation,
and at least one cached row no longer matches a fresh HMAC.

Compliance needs a chain an auditor can read. A stale cache hit must not
release a lot.

Work only in `$WORKSPACE`. Useful inputs:
- `policy.md`
- `evidence/incident_brief.md`
- `keyring/keys.json`
- `cache/verification_cache.json`
- `staging/artifacts.json`
- `attestctl.py`

## Deliverables

- `state/attestation_ledger.json`: One decision per artifact, counts, and the
  accepted artifact ids.
- `state/verification_receipt.json`: The same counts and accepted_count.
- `state/verification.json`: Controller command, each attempt, and whether
  re-running it left the state unchanged.
- `attestation_chain_handoff.md`: Explain the rotation, cache rule, each
  refusal class, the verification, and the authorization boundary.

## Working rules

1. Read `policy.md` first; it outranks the cache and the incident note.
2. Recompute digests; do not trust a claimed digest or a cache row that
   disagrees with the current key generation.
3. Use `python3 attestctl.py validate` more than once.
4. Create only the four declared artifacts. Do not modify the keyring, cache,
   bundle, policy, evidence, or controller.

Work offline. Do not execute or claim an external, production, payment,
filing, deletion, message-send, booking, or account action.

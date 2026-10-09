# Webhook verification handoff

The repaired verifier signs the exact UTF-8 raw body prefixed by the declared
timestamp; it never parses or canonicalizes JSON. Rotation eligibility uses the
signature timestamp and half-open key windows, so the old and new secrets both
verify during overlap while the old secret stops exactly at expiry. Every `v1`
signature is compared against every endpoint-eligible key with
`hmac.compare_digest`, preserving constant-time comparison behavior. Receipt
skew uses an inclusive tolerance boundary.

Authentication finishes before replay handling. A valid previously seen ID is
reported as a duplicate, rejected deliveries do not poison the checkpoint, and
only newly accepted IDs are added. Batch structures fail closed before work;
per-delivery malformed headers, stale timestamps, absent keys, and bad HMACs
use deterministic secret-free reasons.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed, as
did `PYTHONDONTWRITEBYTECODE=1 python bin/verify_webhooks.py`. I parsed
`out/decisions.json` and `out/checkpoint.json` again and confirmed no body,
header, signature, or secret appears. This was an offline verification replay;
no live endpoint or provider configuration was changed.

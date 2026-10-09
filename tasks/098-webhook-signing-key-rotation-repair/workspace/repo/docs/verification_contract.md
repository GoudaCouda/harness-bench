# Webhook verification contract

Implement `verify_batch(deliveries, keyring, policy, checkpoint)` without
mutating any argument.

All four arguments are validated completely before verification. Objects have
exactly the fields described below. Integers exclude booleans. Invalid input
raises `ValueError`; no partial result is returned.

- `policy`: exactly `algorithm` (`hmac-sha256`), `signature_version` (`v1`),
  and `tolerance_seconds` (integer 0..900).
- `checkpoint`: exactly `seen_delivery_ids`, a unique list of non-empty strings.
- `keyring`: a list of unique key objects with exactly `key_id`, `endpoint`,
  `secret`, `not_before`, and `not_after`. Strings are non-empty; bounds are
  integers with `not_before < not_after`.
- `deliveries`: a list of unique objects with exactly `delivery_id`, `endpoint`,
  `received_at`, `raw_body`, and `signature_header`. IDs/endpoints are non-empty
  strings, receipt time is a non-negative integer, and body/header are strings.

The header is a comma-separated sequence of trimmed `name=value` components.
Every component needs one non-empty name and value. There is exactly one `t`
component containing ASCII decimal digits and one or more `v1` components.
Unknown well-formed components are ignored. Every `v1` value must be exactly 64
lowercase hexadecimal characters; malformed headers are rejected per delivery.

Sign the exact UTF-8 bytes of `str(t) + "." + raw_body` with HMAC-SHA256. Never
parse or reserialize `raw_body`. A key is eligible when its endpoint matches and
`not_before <= t < not_after`. A delivery is current when
`abs(received_at - t) <= tolerance_seconds`. Compare every supplied signature
against every eligible key with `hmac.compare_digest`; report every matching
key ID in lexical order.

Decision precedence is: `malformed_header`, `outside_tolerance`,
`no_eligible_key`, `bad_signature`, then authenticated replay state. Decisions
have exactly `delivery_id`, `status`, `reason`, and `matched_key_ids`.
Authenticated unseen IDs are `accepted`/`ok`; authenticated IDs already in the
checkpoint are `duplicate`/`already_seen`; all earlier outcomes are
`rejected` with their named reason and an empty key list. Only newly accepted
IDs advance the checkpoint. Return decisions in delivery order and return the
checkpoint as exactly `{"seen_delivery_ids": [...]}` sorted lexically.

Return exactly `{"decisions": [...], "checkpoint": {...}}`. No result may
contain a secret, header, signature, or body.

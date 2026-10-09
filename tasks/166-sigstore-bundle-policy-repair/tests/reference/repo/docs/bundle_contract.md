# Offline bundle policy contract

`verify_bundles(artifacts, bundles, roots, policy)` is pure and returns exactly
`{"decisions": [...], "summary": {...}}`.

All lists use exact schemas and sorted unique IDs. Epochs are non-negative
integers and validity ranges are inclusive. Artifacts declare exact digest,
identity, issuer, and payload type. Each artifact requires exactly one bundle.
Bundle booleans are results of prior cryptographic checks; this task consumes
but never invents those checks.

Policy has exact `require_tlog`, `require_timestamp`,
`min_tlog_operators`, and sorted `accepted_payload_types`. Roots declare a CA
operator, distinct trusted tlog/timestamp operators, and inclusive validity.

The first failing rule blocks: missing bundle, digest, payload type, signature,
certificate chain, identity, issuer, unknown root, missing required tlog or
timestamp evidence, insufficient distinct tlog operators, or no common trusted
signing time. Tlog evidence counts only verified inclusion from an operator
trusted by the selected root. Timestamp evidence likewise requires verified
trusted operators. Multiple entries from one operator count once.

At least one verified required evidence time must lie inside both the leaf
certificate and selected root validity intervals. When both tlog and timestamp
are required, there must be at least one valid time of each type. Certificate
expiry at later verification time is irrelevant. Decisions have exactly
`artifact_id`, `status`, `reason`, `signing_time`, and `tlog_operator_count`.
Summary has `artifact_count`, `verified`, and `blocked`.

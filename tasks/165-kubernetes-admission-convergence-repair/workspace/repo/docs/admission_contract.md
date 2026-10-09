# Admission convergence contract

`evaluate_admission(requests, webhooks, policy)` is pure and returns exactly
`{"decisions": [...], "objects": [...], "summary": {...}}`.

Requests and webhooks use exact sample schemas and sorted unique IDs/names.
Request `fields` is a flat lowercase path-to-scalar map. Webhook operation and
resource lists and excluded namespaces are sorted unique tokens. Mutations are
sorted by path and have exact `path`, `mode`, and scalar `value`; mode is
`set_if_missing`, `ensure_value`, or `append`. Policy has exactly
`require_side_effect_free` and sorted unique `immutable_paths`.

For each request, applicable webhooks match operation/resource and do not
exclude its namespace. Mirror pods are blocked before matching. Any applicable
unavailable webhook with failurePolicy Fail blocks; Ignore skips it. When policy
requires side-effect-free, only `None` is accepted; on dry-run, `None` and
`NoneOnDryRun` are accepted. Mutation of an immutable path blocks.

`append` is non-idempotent and blocks, especially under reinvocation. Multiple
applicable writes to one path converge only when their values are equal;
different values block as `mutation_conflict`, independent of webhook order.
After safety checks, canonical application sorts webhook names: a
`set_if_missing` preserves an existing field, while `ensure_value` writes the
declared value. Same-value repetitions are harmless. Final objects are ordered
by request ID and fields by path.

Decisions have `request_id`, `status`, `action`, `reason`, and `webhook_count`.
Admitted uses `emit_object/converged`; excluded/no-match uses
`unchanged/no_matching_webhook`; blocked uses `reject` and the first safety
reason. Summary has `request_count`, `admitted`, `unchanged`, and `blocked`.

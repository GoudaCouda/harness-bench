# Cross-system transfer review policy — revision 8

Reconstruct effective access before planning changes. Replay numeric event
sequence, not file order. Expand group membership through every group-to-group
edge and group entitlement. A later `succeeded` receipt with `verified`
signature supersedes earlier request/timeout state for the same idempotency
key; preserve the receipt and do not retry or plan a duplicate removal.

Compare effective access with `target_role_matrix.csv` and
`sod_policy.csv`. The minimum safe delta follows these rules:

1. Preserve all target-required entitlements.
2. When forbidden access is inherited, remove this employee's narrowest
   membership that breaks the path. Do not modify a shared group or remove a
   required direct entitlement.
3. Add only a missing required direct entitlement.
4. For an SoD conflict, follow the remediation rule and approval owner in the
   SoD record; target-required access has precedence.
5. A non-empty `exclusive_slot` identifies a single-valued access profile, not
   independent additive entitlements. When equally current authoritative
   sources report different values for the same slot, create no access change
   until the named owner reconciles evidence. Blank slots remain independent
   entitlements and may coexist.

Permitted planned actions are `add_entitlement`, `remove_entitlement`, and
`remove_membership`. For a new proposal, use
`<transfer_id>:<system>:<target_value>:<action>:v1` as the idempotency key. A
plan is staged for approval only and proves no external execution.

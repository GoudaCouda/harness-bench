# Kestrel launch-control handoff

The current gate is **hold**, not a full launch approval. RF-77 authorizes a
2025-09-01 limited start and RF-77A restricts the authorized scope to East
Market. Airport connectors remain deferred: the contract describes that future
scope, but regulatory certification and COI-14 are still prerequisites. The
audited finance close supplies the USD 42.5 million allocation, the operations
log supplies the 1,240-customer cohort, and RF-77 identifies Northstar as the
primary operator. These are scoped choices; no one record was treated as global
authority.

Legal approval for customer communication CT-9 is still open, so the policy
requires a hold. I blocked the customer announcement, East Market activation,
and airport reservation rather than leaving external actions queued. The safe
East Market readiness check remains ready. I preserved both historical events
and appended KST-2025-0821, which supersedes the stale PR-3 full-launch draft.

Once CT-9 Legal approval is recorded, the next operator should recheck the
authority files, update the gate under LC-4, and rerun
`python3 bin/kestrelctl.py verify`. Airport activation needs separate RF-77A
certification and COI-14 approval even after the limited East Market release is
eligible.

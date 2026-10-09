# CHG-4821 — make the production replacement runbook usable

Tomorrow at 13:00 UTC, the on-call engineer will use
`db/deployment_guide.md` while replacing `web-02`. The guide was copied from an
old capacity plan and must be brought up to the current production state before
that handoff.

This is a **documentation-only** change. Do not apply a ConfigMap, change a
database value, restart a service, replace a node, or claim that any deployment
work has occurred.

## Evidence authority agreed with the platform owner

1. For production configuration, `environment.yml` overrides the global value
   in `backup.sql` when the same key exists. The database global value is the
   baseline for keys without an override. Staging is out of scope.
2. `backup.sql` records commissioned cluster membership, role, and region.
3. For CPU, memory, and disk, `node_inventory.json` is authoritative when its
   `last_updated` time is later than the SQL snapshot; otherwise use the SQL
   cluster table.
4. The existing deployment guide is never evidence for current state.

## Acceptance for the handoff

- The guide must state the effective production configuration, including any
  intentional override that an operator could otherwise mistake for drift.
- Its node table must cover every commissioned node with current hardware and
  region, and its regional guidance must match the actual topology.
- Leave `change_review.md` with a `READY` or `BLOCKED` decision for using the
  revised guide, the evidence reviewed, material corrections, residual caveats,
  and a short pre-use validation checklist.

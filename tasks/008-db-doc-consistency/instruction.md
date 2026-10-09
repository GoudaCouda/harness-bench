Take ownership of documentation change `CHG-4821` in `$WORKSPACE`.

Read the change request and all four sources under `$WORKSPACE/db/`. Reconcile
them using the authority rules in `change_request.md`, then update
`$WORKSPACE/db/deployment_guide.md` in place so it is safe for the scheduled
node-replacement handoff. Preserve useful operational guidance, but replace
stale production configuration, hardware, and region assertions with the
current effective state.

Create `$WORKSPACE/change_review.md` with the requested readiness decision,
evidence, corrections, residual caveats, and pre-use checks. This review is for
the revised documentation, not permission to perform the node replacement.

Do not use the network or modify `change_request.md`, `backup.sql`,
`environment.yml`, or `node_inventory.json`. Do not apply configuration,
restart services, replace nodes, or represent any external action as completed.

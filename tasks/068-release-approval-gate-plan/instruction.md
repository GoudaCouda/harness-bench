Create a release approval gate package.

Read:
- $WORKSPACE/release_manifest.json
- $WORKSPACE/approval_policy.md
- $WORKSPACE/preflight_checks.json
- $WORKSPACE/risk_register.csv
- $WORKSPACE/change_calendar.csv
- $WORKSPACE/incident_history.json
- $WORKSPACE/rollback_runbook.md

Create:
- $WORKSPACE/approval_packet.json
- $WORKSPACE/blockers.csv
- $WORKSPACE/pending_actions.md
- $WORKSPACE/audit_trail.md

Requirements:
- Determine whether the release is go, conditional_go, or blocked.
- Identify all hard blockers from the policy and evidence files.
- `risk_register.csv` is the public blocker-ID codebook. For every hard
  blocker, use its `RR-*` `risk_id` verbatim as `blocker_id`. Use the same
  IDs in all four output files; do not invent a second ID namespace.
- `approval_packet.json` must include `release_id`, `decision`,
  `blocker_ids`, `required_approvals`, `pending_actions`, `evidence_refs`,
  and `not_executed_statement`. `required_approvals` means approvals that
  are still pending; do not repeat an approval already present in
  `declared_approvals`. Prefix every pending-action string with its `RR-*`
  blocker ID.
- `blockers.csv` must have exactly this header and no extra columns:
  `blocker_id,severity,owner_role,evidence_ref,required_approval_or_action,rationale`.
  Write exactly one row per hard blocker.
- An evidence locator has the form `input_filename#record_or_fact_id`, for
  example `preflight_checks.json#PF-CANARY-ERR`. Separate multiple locators
  in one CSV cell with ` | `. Each blocker row must cite the concrete local
  record(s) supporting it. `approval_packet.json` must include the policy
  and the evidence locators used for every blocker.
- `pending_actions.md` must have one proposed/pending action per blocker,
  with each line prefixed by the matching `RR-*` ID.
- `audit_trail.md` must contain one row or bullet per `RR-*` blocker that
  maps it to an applicable policy rule and concrete local evidence
  locator. It must also map the blocked decision to
  `approval_policy.md`.
- The checkout-api canary threshold has no approval, override, or waiver:
  resolve that blocker only by reducing the error rate to 1.5 percent or
  below and rerunning/retesting `PF-CANARY-ERR`.
- A database waiver must be signed. A freeze exception must be written.
- Do not modify input files. Do not use network access.
- This is a planning and approval package only. Do not claim that production operations, rollback, deploy, feature flag changes, or paging actions have already been executed.

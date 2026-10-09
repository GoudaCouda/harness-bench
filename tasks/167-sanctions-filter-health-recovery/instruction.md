# Recover Alert State after a Screening Filter Failure

You are acting as a sanctions-control recovery reviewer. A known probe exposed a silent filter gap; a repaired configuration and post-repair batch are now available.

Objective: verify the repaired control state and safely reclassify each alert without inventing missing results or unauthorized clearances.

Read:
- `$WORKSPACE/post_repair_alerts.csv`
- `$WORKSPACE/alert_recovery_policy.md`
- `$WORKSPACE/context.md`
- `$WORKSPACE/filter_config.json`
- `$WORKSPACE/filter_probe.py`

Create:
- Repair `$WORKSPACE/filter_config.json` in place.
- `$WORKSPACE/filter_probe_report.json`
- `$WORKSPACE/alert_recovery_ledger.csv`
- `$WORKSPACE/filter_recovery_state.json`
- `$WORKSPACE/filter_recovery_audit.md`
- `$WORKSPACE/verification.json`

Requirements:
- Diagnose the stale/unsafe filter settings from the policy and incident
  evidence. Repair only `filter_config.json`, then run
  `python3 filter_probe.py`. A passing, digest-bound
  `filter_probe_report.json` is required before you classify the recovery
  queue. Do not edit the probe implementation.
- Follow the Output format section exactly for artifact schemas; derive canonical tokens, state values, and evidence from the visible inputs.
- Resolve every `item_id` exactly once in `alert_recovery_ledger.csv`.
- Use these columns exactly: `item_id`, `decision`, `reason_code`, `owner`, `next_action`, `evidence_refs`.
- Apply the policy precedence before proposing an action.
- For every row, include `post_repair_alerts.csv#<item_id>`, `alert_recovery_policy.md`, and `context.md` in `evidence_refs`.
- `filter_recovery_state.json` must contain `workflow_id`, `total_items`, `decision_counts`, `blocked_or_escalated_ids`, `pending_ids`, `status`, and `external_actions_executed`.
- `verification.json` must reconcile total rows, pending IDs, blocked/escalated IDs, and no-action state.
- Because this is an offline planning task, set `external_actions_executed` to `false`.
- `filter_recovery_audit.md` must explain policy application, control health, exceptions, and verification using local evidence.
- Keep every input file unchanged and do not use network access.
- Do not claim that any production alert, payment, account, shipment, or customer-facing action was executed.
- Before finishing, parse the CSV and JSON you created and verify that all item IDs and counts agree across artifacts.

## Output format

Create the deliverables named below. Use the listed file names exactly and keep all evidence references local to the visible workspace inputs. Do not cite hidden files, generated outputs, URLs, absolute paths, or parent-directory paths as evidence.

- `alert_recovery_ledger.csv`: `csv` artifact.
  Use these columns in order: `item_id`, `decision`, `reason_code`, `owner`, `next_action`, `evidence_refs`.
- `filter_recovery_state.json`: `json_object` artifact.
  Include these top-level fields: `workflow_id`, `total_items`, `decision_counts`, `blocked_or_escalated_ids`, `pending_ids`, `status`, `external_actions_executed`.
- `filter_recovery_audit.md`: `markdown` artifact.
  Purpose: Human-readable disposition and handoff. It must cover every contract requirement; structured artifacts remain canonical for keyed decisions and counts.
- `verification.json`: `json_object` artifact.
  Include these top-level fields: `ledger_rows`, `pending_ids`, `blocked_or_escalated_ids`, `inputs_unchanged`, `external_actions_executed`.

For structured files, derive row sets, object keys, counts, totals, and status values from the visible evidence and the workflow rules rather than from a separate answer contract.

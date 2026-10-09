# Recover a Fail-Closed Payee Screening Batch

You are acting as the analyst resuming a partially failed pre-payment screening batch. The screening service failed on some attempts, later recovered for selected payees, and also returned a stale retry and a duplicate correlation.

Objective: use the latest current verified result exactly once, leave missing or stale checks pending, block current restricted matches, and link duplicate correlations without rescreening.

Read:
- `$WORKSPACE/recovery_queue.csv`
- `$WORKSPACE/fail_closed_policy.md`
- `$WORKSPACE/context.md`
- `$WORKSPACE/screeningctl.py`

Create:
- `$WORKSPACE/recovered_screening.csv`
- `$WORKSPACE/screening_recovery_state.json`
- `$WORKSPACE/screening_recovery_audit.md`
- `$WORKSPACE/verification.json`

Requirements:
- Follow the Output format section exactly for artifact schemas; derive canonical tokens, state values, and evidence from the visible inputs.
- Resolve every `item_id` exactly once in `recovered_screening.csv`.
- Use these columns exactly: `item_id,decision,reason_code,owner,next_action,evidence_refs`.
- Apply the fail-closed policy before proposing an action.
- Reconstruct each attempt history from the recovery log and use only a latest
  checksum-verified result on the required list version. Do not repeat or erase
  a successful attempt, and do not convert missing or stale results to clear.
- Block exact restricted matches and unverified bank changes under the policy.
- Hold duplicate correlations for linking rather than rescreening or staging.
- Include `recovery_queue.csv#<item_id>`, `fail_closed_policy.md`, and `context.md` in every row's evidence refs.
- `screening_recovery_state.json` must contain `workflow_id,total_items,decision_counts,blocked_or_escalated_ids,pending_ids,status,external_actions_executed`.
- Generate `verification.json` by running `python3 screeningctl.py` after
  the other three deliverables are complete. The command binds its receipt to
  the input bundle and exact artifact bytes; do not hand-author that file.
- Keep every input file unchanged and do not use network access.
- Do not claim that any external, financial, production, account, employment, or customer-facing action was executed. Record proposed next actions only.
- Before finishing, parse the CSV and JSON you created and verify that all item IDs and counts agree across artifacts.

## Output format

Create the deliverables named below. Use the listed file names exactly and keep all evidence references local to the visible workspace inputs. Do not cite hidden files, generated outputs, URLs, absolute paths, or parent-directory paths as evidence.

- `recovered_screening.csv`: `csv` artifact.
  Use these columns in order: `item_id`, `decision`, `reason_code`, `owner`, `next_action`, `evidence_refs`.
- `screening_recovery_state.json`: `json_object` artifact.
  Include these top-level fields: `workflow_id`, `total_items`, `decision_counts`, `blocked_or_escalated_ids`, `pending_ids`, `status`, `external_actions_executed`.
- `screening_recovery_audit.md`: `markdown` artifact.
  Purpose: Human-readable disposition and handoff. It must cover every contract requirement; structured artifacts remain canonical for keyed decisions and counts.
- `verification.json`: `json_object` artifact.
  Include these top-level fields: `workflow_id`, `decision_artifact`, `state_artifact`, `audit_artifact`, `row_count`, `unique_item_keys`, `state_reconciled`, `inputs_unchanged`, `external_actions_executed`, `evidence_files_checked`.

For structured files, derive row sets, object keys, counts, totals, and status values from the visible evidence and the workflow rules rather than from a separate answer contract.

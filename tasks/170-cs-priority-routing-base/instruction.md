# Impact-Urgency Service Case Routing

You are acting as a service desk routing coordinator. A mixed-impact queue must be prioritized before the next routing cycle.

Objective: compute priority, first-match ownership, and the next escalation-safe action for every alert-backed case without executing pages or assignments.

Read:
- `$WORKSPACE/service_cases.csv`
- `$WORKSPACE/routing_policy.md`
- `$WORKSPACE/routing_config.json`
- `$WORKSPACE/routing_probe.py`

Create:
- Repair `$WORKSPACE/routing_config.json` in place.
- `$WORKSPACE/routing_probe_report.json`
- `$WORKSPACE/routing_decisions.csv`
- `$WORKSPACE/routing_state.json`
- `$WORKSPACE/routing_audit.md`
- `$WORKSPACE/verification.json`

Requirements:
- The checked-in routing configuration has precedence and boundary defects.
  Repair it from policy, then run `python3 routing_probe.py`. Do not edit the
  probe. Its digest-bound report must pass before you apply the repaired rules
  to the service-case queue.
- Follow the Output format section exactly for artifact schemas; derive canonical tokens, state values, and evidence from the visible inputs.
- Resolve every `item_id` exactly once in `routing_decisions.csv`.
- Use these columns exactly: `item_id`, `decision`, `reason_code`, `owner`, `next_action`, `evidence_refs`.
- Apply first-match policy precedence before proposing an action.
- For every row, include `service_cases.csv#<item_id>` and `routing_policy.md` in `evidence_refs`.
- `routing_state.json` must contain `workflow_id`, `total_items`, `decision_counts`, `blocked_or_escalated_ids`, `pending_ids`, `status`, and `external_actions_executed`.
- `verification.json` must reconcile total rows, escalated/held IDs, pending IDs, and no-action state.
- Because this is an offline planning task, set `external_actions_executed` to `false`.
- `routing_audit.md` must explain first-match precedence, acknowledged/duplicate suppression, priority routing, and verification using local evidence.
- Keep every input file unchanged and do not use network access.
- Do not claim that any page, customer message, account change, production action, or assignment was executed.

## Output format

Create the deliverables named below. Use the listed file names exactly and keep all evidence references local to the visible workspace inputs. Do not cite hidden files, generated outputs, URLs, absolute paths, or parent-directory paths as evidence.

- `routing_decisions.csv`: `csv` artifact.
  Use these columns in order: `item_id`, `decision`, `reason_code`, `owner`, `next_action`, `evidence_refs`.
- `routing_state.json`: `json_object` artifact.
  Include these top-level fields: `workflow_id`, `total_items`, `decision_counts`, `blocked_or_escalated_ids`, `pending_ids`, `status`, `external_actions_executed`.
- `routing_audit.md`: `markdown` artifact.
  Purpose: Human-readable disposition and handoff. It must cover every contract requirement; structured artifacts remain canonical for keyed decisions and counts.
- `verification.json`: `json_object` artifact.
  Include these top-level fields: `routing_rows`, `blocked_or_escalated_ids`, `pending_ids`, `inputs_unchanged`, `external_actions_executed`.

For structured files, derive row sets, object keys, counts, totals, and status values from the visible evidence and the workflow rules rather than from a separate answer contract.

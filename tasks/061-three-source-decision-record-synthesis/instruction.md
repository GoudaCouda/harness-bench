Task: Synthesize a Three-Source Decision Record

Use only the offline materials in `$WORKSPACE`.

Inputs:
- `$WORKSPACE/source_priority.md`
- `$WORKSPACE/meeting/meeting_transcript.md`
- `$WORKSPACE/email/thread.json`
- `$WORKSPACE/docs/*.md`

Create:

1. `$WORKSPACE/decision_record.json`
   - Required top-level keys: `decision_id`, `final_decisions`, `rejected_options`, `open_questions`.
   - `final_decisions` items must include `decision_key`, `value`, `status`, `winning_source`, and `evidence_signal`.
   - Each `evidence_signal` must contain a short decisive phrase from the
     winning source that supports the row. A record or section ID may accompany
     that phrase, but an ID by itself is not sufficient.
   - Use these `decision_key` values so the handoff is machine-readable:
     `launch_date`, `deployment_mode`, `budget_cap`, `feature_scope`, and
     `approval_gate`.
   - `rejected_options` items must include `option`, `reason`, `source_file`, and `evidence_signal`.
     `source_file` may cite either the source that proposed the rejected option
     or the governing source that blocked or superseded it, provided the
     evidence signal makes that relationship clear.
   - `open_questions` items must include `question`, `why_unresolved`, and `needed_evidence`.

2. `$WORKSPACE/source_conflicts.csv`
   - Header exactly:
     `decision_key,winning_source,superseded_sources,resolution_reason,priority_rule`
   - The conflict ledger is closed: include exactly one row for each visibly
     disputed or superseded decision key `launch_date`, `deployment_mode`,
     `budget_cap`, and `feature_scope`, with no other decision keys.
   - Reconcile the relevant meeting, email, PRD, security, finance, and legal
     sources in those four rows.

3. `$WORKSPACE/action_items.csv`
   - Header exactly:
     `action_id,owner,due_date,action,status,source_file,evidence_signal`
   - Include the current action items after applying later email and formal document constraints.
   - For each action, preserve its current status and put a short supporting
     phrase from `source_file` in `evidence_signal`; a bare record or section ID
     is not sufficient.

Rules:
- Do not treat brainstorms or meeting proposals as final approval.
- Later decision email can supersede meeting discussion.
- Formal security, legal, and finance documents outrank PRD and meeting discussion for their scoped domains.
- Preserve unresolved questions instead of inventing a final decision.
- Do not modify input files.

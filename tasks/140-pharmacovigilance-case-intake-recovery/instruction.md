# Recover an Interrupted Pharmacovigilance Case-Intake Projection

You are the local pharmacovigilance operations engineer resuming a synthetic ICH E2B-style case-intake batch after a worker crashed mid-transaction. The durable SQLite state includes an interrupted before-image journal and a partial delivery receipt. The inbound stream contains out-of-order report versions, a duplicate delivery, an identity collision, an incomplete nullification, a disallowed terminology version, an unknown case, and messages that arrive across accepted and pending-submission boundaries.

Recover the local database and stage a reviewer queue. Do not transmit a safety report or acknowledgement.

## Visible system

- `state/pv.db`: durable case, version, submission, receipt, run, journal, and system state.
- `evidence/inbound_messages.jsonl`: immutable inbound envelopes. File order is delivery order; policy-defined `source_sequence` controls accepted version replay.
- `evidence/acknowledgements.jsonl`: immutable local acknowledgement snapshot.
- `policy/pv_policy.json`: identity, version, terminology, nullification, queue, and external-boundary rules.
- `policy/source_manifest.json`: immutable-source digests.
- `pvctl.py`: local controller with `inspect`, `preview`, `apply`, `verify`, `stage`, and `replay` commands. Each plan command takes the workspace-relative plan path.

Inspect the raw SQLite tables and every source before deciding anything. Build `recovery_plan.json` yourself from visible evidence. The controller gives object-specific discrepancy locations but does not supply corrected business values.

## Plan contract

`recovery_plan.json` is one JSON object with exactly:

- `schema_version`: `1`
- `recovery_id`
- `source_checkpoint`
- `case_decisions`: one object per durable case, each with exactly `case_id`, `prior_version`, `final_version`, `disposition`, `final_state`, `queue`, `deadline_class`, `selected_message_ids`, `next_local_action`, `evidence_refs`
- `delivery_dispositions`: one object per inbound delivery, each with exactly `delivery_id`, `message_id`, `case_id`, `version`, `disposition`
- `queue_totals`: exactly `expedited_review`, `routine_review`, `held`, `preserved`
- `external_transmissions_executed`: `false`

Evidence references must be workspace-relative visible locators. `#case:`/`#safety_cases:` and `#message:`/`#message_id:` are equivalent locator spellings. Array and object ordering is not semantic.

## Required recovery flow

1. Run `python3 pvctl.py inspect`; then independently inspect all SQLite tables, policy, evidence, acknowledgements, and source hashes.
2. Recover from the interrupted journal conceptually before deriving outcomes. Respect first-message identity, source-sequence replay, contiguous versions, exact case identity, accepted/pending boundaries, nullification proof, and permitted terminology.
3. Write `recovery_plan.json`; run `python3 pvctl.py preview recovery_plan.json`. Use `.pv_preview.json` feedback to correct the plan.
4. Run `apply`, `verify`, and `stage` in order. `apply` must atomically restore the prior interruption and commit the new local projection. `stage` may create only a local human-review queue.
5. Write `pv_handoff.md` explaining the actual cases and messages: version ordering and duplicates; identity, nullification, and terminology holds; accepted and pending boundaries; expedited versus routine staging; interrupted-journal recovery; checkpoint/hash closure; and the fact that no external report or acknowledgement was transmitted.
6. Create an equivalent plan using different array order and the documented equivalent locator spellings. Run `replay` with it and prove the database, packet, manifest, and receipt remain byte-stable. Preserve that equivalent plan as `equivalent_recovery_plan.json`.
7. Create `conflict_probe_plan.json` from the valid plan with one real business decision changed. Attempt `apply`; it must be rejected without mutating the database or staged bundle. Record the command, non-zero exit, changed field, and before/after SHA-256 values in `conflict_probe.json`.

## Required final artifacts

- `recovery_plan.json`
- `equivalent_recovery_plan.json`
- `conflict_probe_plan.json`
- `conflict_probe.json`
- `.pv_preview.json`
- modified `state/pv.db`
- `state/verification.json`
- `state/recovery_receipt.json`
- `state/replay_report.json`
- `staging/pv_review_queue.json`
- `staging/packet_manifest.json`
- `pv_handoff.md`

All evidence inputs and policy files are immutable. Do not edit submissions or accepted/pending acknowledgement history. Work offline. Do not transmit, submit, acknowledge, notify, contact, or update any external regulator, sponsor, patient, reporter, or safety system.

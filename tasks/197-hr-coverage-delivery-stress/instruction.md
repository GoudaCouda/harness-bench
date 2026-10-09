# Recover a crashed continuation-coverage notice-delivery run

You are the benefits operations engineer recovering synthetic offline run `CONT-REC-2026-08-14`. A local worker crashed after changing one case row and inserting one retry queue item, but before closing its before-image journal. The stale checkpoint also predates some beneficiary, address, delivery, and election evidence.

This task stages local reviewer work only. It does not send a notice, contact a delivery provider, enroll anyone, or change benefit coverage.

## Visible system

- `state/continuance.db`: durable cases, beneficiaries, notice versions, delivery attempts, recovery queue, decision receipts, runs, journal, and system state.
- `state/stale_checkpoint.json`: a stale worker checkpoint; it is not authoritative delivery evidence.
- `evidence/eligibility_events.jsonl`: deliberately out-of-order qualifying-event, beneficiary, address, and election events.
- `evidence/delivery_receipts.jsonl`: provider observations, including terminal receipts and non-terminal timeout evidence.
- `policy/continuance_policy.json`: replay order, evidence precedence, deadline, exact vocabulary, locator aliases, and external boundary.
- `policy/source_manifest.json`: immutable-source digests.
- `continuancectl.py`: candidate-first local controller with `inspect`, `query`, `preview`, `apply`, `verify`, `stage`, and `replay`. It diagnoses candidate fields but never supplies corrected business values.

Start by inspecting every source and every SQLite table. Useful initial commands are:

```bash
python3 continuancectl.py inspect
python3 continuancectl.py query "SELECT * FROM cases ORDER BY case_id"
python3 continuancectl.py query "SELECT * FROM recovery_journal ORDER BY journal_id"
python3 continuancectl.py query "SELECT * FROM recovery_queue ORDER BY queue_id"
```

Reconstruct the state before the interrupted writes. Replay source events by the published source sequence, enforce exact employee identity, use only verified HR address evidence, and distinguish terminal delivered/returned receipts from provider acceptance and callback timeouts. A delivered receipt prevents duplicate delivery work. A returned receipt can support a local reissue only when a newer verified address exists. Preserve cases already beyond notice delivery. Evaluate the fixed scenario deadline without backdating.

## Recovery plan contract

Create `recovery_plan.json` as one object with exactly:

```text
schema_version, recovery_id, source_checkpoint, as_of, case_decisions,
journal_actions, queue_totals, external_notices_sent, coverage_changed
```

Each case decision has exactly:

```text
case_id, baseline_state, disposition, notice_version, address_version,
beneficiary_keys, delivery_evidence, deadline_state, next_local_action,
evidence_refs
```

Each journal action has exactly `journal_id`, `table_name`, `record_id`, and `action`. `queue_totals` has exactly the four keys published by policy. Use only policy vocabulary and workspace-relative evidence locators. Evidence references and beneficiary keys compare as sets. The policy-documented `#case`/`#cases` and `#event`/`#event_id` spellings are semantically equivalent; array and object order is not semantic. Set both external-action flags to `false`.

## Guarded recovery flow

1. Write the plan yourself, then run `python3 continuancectl.py preview recovery_plan.json`. Use object-and-field discrepancies in `.continuance_preview.json` to correct your evidence reasoning.
2. Run `apply`, then `verify`, then `stage` with the same plan. `apply` restores interrupted before-images and atomically commits durable decision receipts and an unexecuted local queue. `stage` produces only a local reviewer bundle.
3. Write `continuance_handoff.md`. Explain all seven cases; event/receipt precedence; the stale checkpoint; before-image and partial-queue recovery; deadline handling; queue totals; source/state/bundle hashes; verification; idempotency; and the no-notice/no-provider/no-enrollment/no-coverage-change boundary.
4. Create `equivalent_recovery_plan.json` by changing array order and using at least one documented equivalent locator spelling. Run `replay` with it and preserve the plan. Prove the database, bundle, manifest, and staging receipt remain byte-stable.
5. Create `conflict_probe_plan.json` from the valid plan with one real case decision changed. Attempt `apply`; it must fail without mutation. Record `schema_version`, the exact command, non-zero `exit_code`, `changed_field`, and before/after SHA-256 maps for `database`, `bundle`, `manifest`, and `receipt` in `conflict_probe.json`.

## Required final artifacts

- `recovery_plan.json`
- `equivalent_recovery_plan.json`
- `conflict_probe_plan.json`
- `conflict_probe.json`
- `.continuance_preview.json`
- modified `state/continuance.db`
- `state/verification.json`
- `state/staging_receipt.json`
- `state/replay_report.json`
- `staging/notice_review_queue.json`
- `staging/queue_manifest.json`
- `continuance_handoff.md`

Do not edit source evidence, policy, checkpoint, controller, already-executed delivery history, or unrelated case facts. Do not use the network. Do not send, mail, transmit, notify, contact, enroll, terminate, or alter coverage.

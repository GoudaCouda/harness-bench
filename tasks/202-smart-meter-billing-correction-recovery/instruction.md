# Recover a smart-meter billing correction after an interrupted rebill

You are the utility billing-operations analyst for cycle `2026-11`. An interval
ingest arrived out of order and contains a duplicate. The cycle also spans the
fall-back daylight-saving transition, one meter rolled over its register, and a
solar account reports import and export separately. A primary recovery batch is
damaged; a signed, checksummed offline fallback may be used only for the meter it
covers. Another account does not have enough authoritative evidence and must be
held. A previous local reversal/rebill stopped after changing one bill row.

All work is offline in the current workspace. Begin with:

```bash
python3 meterctl.py inspect
python3 meterctl.py query bills
python3 meterctl.py query correction_runs
```

Read `policy/billing_policy.json`, every file under `evidence/`, and the SQLite
tables. Treat interval identity as UTC plus event identity: the two fall-back
intervals with the same local clock time but different UTC offsets are distinct.
Deduplicate retransmissions by event ID without dropping either real fall-back
interval. Apply the policy's register modulus at rollover and keep solar import
and export as separate quantities. Do not turn incomplete or estimated evidence
into an actual reading. Verify both the fallback checksum and its signature.

Create `correction_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "MBR-202611-FALLBACK-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "billing_cycle": "2026-11",
  "decisions": [],
  "external_actions_executed": false,
  "customer_contacted": false
}
```

Include one decision for every in-scope meter. Every decision has exactly:

```text
account_id, meter_id, authority_method, correction_state,
billed_import_kwh, billed_export_kwh, correct_import_kwh,
correct_export_kwh, delta_import_kwh, delta_export_kwh,
prospective_balance_delta_cents, local_mutations, evidence_refs,
next_local_action, external_action
```

Use the policy vocabularies verbatim. `local_mutations` and `evidence_refs` are
sets for semantic comparison. Energy values are kWh rounded to three decimals.
For an evidence hold, the correct quantities and deltas are JSON `null` and the
prospective balance delta is zero. `external_action` is always `none`.

`inspect` publishes the exact protected `source_checkpoint`. Use these stable
local evidence locator forms:

- every meter cites `policy/billing_policy.json#meters/<meter_id>`;
- interval decisions cite `evidence/interval_feed.jsonl#<event_id>`;
- rollover cites `evidence/register_reads.csv#<read_id>`;
- signed fallback cites the damaged primary, fallback record, and trust key as
  `evidence/primary_batch.json.part#damaged`,
  `evidence/fallback_batch.json#<record_id>`, and
  `evidence/fallback_trust.json#meter-batch-key-2026`.

For corrected meters, `next_local_action` is
`route_local_correction_for_billing_review`; for an evidence hold it is
`obtain_authoritative_meter_evidence`. `local_mutations` lists exactly the bill
fields whose baseline values change, chosen from `corrected_import_kwh`,
`corrected_export_kwh`, `billing_state`, and
`prospective_balance_delta_cents`. A failed validation reports the mismatched
field names separately for each meter without revealing the expected values.

Use the guarded workflow; do not hand-edit SQLite or generated receipts:

```bash
python3 meterctl.py preview correction_plan.json
python3 meterctl.py apply correction_plan.json
python3 meterctl.py verify correction_plan.json
python3 meterctl.py stage correction_plan.json
python3 meterctl.py replay correction_plan.json
```

`apply` must first recover the interrupted reversal/rebill journal and then
atomically commit the local correction projection. `stage` creates a local
pending-review receipt only. The stable `recovery_id` plus protected source
checkpoint identify this recovery. Reordering decisions, evidence, mutations,
or JSON keys is the same semantic plan and must replay as a no-op. A conflicting
plan for the same identity must be rejected before any mutation.

Finally write `meter_recovery_handoff.md` for metering and billing reviewers.
Explain interval deduplication and the two fall-back offsets, rollover arithmetic,
separate solar import/export, why the damaged primary was rejected and the
fallback trusted, why the under-evidenced meter remains held, how the interrupted
journal was recovered, and how verification and semantic replay closed. State
that no bill, refund, payment, meter command, or customer contact was executed.

Keep policy, evidence, trust material, controller, and protected account/meter
identity fields byte-for-byte unchanged. Do not use the network or claim any
irreversible external action.

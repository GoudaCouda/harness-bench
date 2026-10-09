# Recover an interrupted formulary-substitution review

You are the pharmacy-benefit operations specialist recovering an offline
formulary-substitution review after a worker changed one prescription's local
projection but stopped before closing its SQLite before-image journal. The
benefit-event stream is out of order and contains an exact redelivery, a reused
event identity with different content, two event identities occupying the same
prescription/source sequence, an unknown prescription, and late traffic for
protected dispensed and cancelled records.

Everything is synthetic and local. Begin with:

```bash
python3 formularyctl.py inspect
```

Inspect `policy/formulary_policy.json`, `policy/source_manifest.json`, all rows
in `evidence/benefit_events.jsonl`, each registered authorization document, and
all relevant tables in `state/formulary.db`. Use
`python3 formularyctl.py query TABLE` for bounded SQLite inspection. Do not
trust delivery order. Ignore exact redelivery; quarantine every delivery under
an event identity reused with different content; and quarantine distinct event
identities occupying the same prescription/source sequence. Ignore unknown
prescriptions and ordinary events after a dispensed or cancelled boundary.

For each prescription, select the formulary row effective at `prescribed_at`,
not the newest row at review time. Reconcile the directly named target product,
substitution group, prescriber DAW code, member allergy codes against target
excipients, required step record, prior-authorization signature/hash/content/
expiry, and required channel. Apply the published hold precedence. Never infer
missing evidence or clinical acceptability. Preserve prescription/member/product
identity, prescribed time, source status, DAW code, channel, and every source
row. Dispensed and cancelled records are protected boundaries.

Create `formulary_recovery_plan.json` with exactly:

```json
{"schema_version": 1, "recovery_id": "FSR-20260819-01", "source_checkpoint": "derived protected-source checkpoint", "rx_decisions": [], "event_dispositions": [], "totals": {}, "external_actions_executed": false}
```

Include one decision per prescription with exactly:

```text
rx_id, member_id, current_product_code, target_product_code, disposition,
final_local_state, effective_rule_ids, invalid_document_ids,
allergy_conflict_codes, blocking_reasons, local_mutations,
next_local_action, evidence_refs
```

Include one disposition per delivered row with exactly:

```text
delivery_id, event_id, rx_id, source_sequence, disposition
```

The six plural decision fields are sets for semantic comparison. `totals` has
exactly `active_prescriptions`, `ready_prescriptions`, `held_prescriptions`,
`preserved_dispensed_prescriptions`, and
`preserved_cancelled_prescriptions`. Use policy vocabulary exactly. Stable
local locators are `file#table:key`, `file#record`, or registered
`file#document_id` forms.

Use the guarded workflow; do not hand-edit SQLite or closure artifacts:

```bash
python3 formularyctl.py preview formulary_recovery_plan.json
python3 formularyctl.py apply formulary_recovery_plan.json
python3 formularyctl.py verify formulary_recovery_plan.json
# write formulary_handoff.md before staging
python3 formularyctl.py stage formulary_recovery_plan.json
python3 formularyctl.py replay formulary_recovery_plan.json
```

`preview` reports mismatched field names by prescription and delivery without
revealing target values or mutating SQLite. `apply` restores the interrupted
before-image and commits one atomic local projection. `stage` creates only a
hash-bound offline review packet. Stable `recovery_id + source_checkpoint` and
the normalized semantic plan define replay identity: row/set reordering and
JSON formatting changes are no-ops. Stale checkpoints and conflicting plans
under the same recovery identity fail before writing.

Write `formulary_handoff.md` for benefit operations, pharmacy, and clinical
reviewers. Explain event authority; effective-rule selection; target-product,
DAW, allergy, step, authorization, and channel controls; every prescription
outcome; interrupted-journal recovery; protected boundaries; packet hashes;
verification; and semantic replay. State explicitly that no substitution,
prescribing, dispensing, cancellation, benefit adjudication, authorization,
approval/denial, contact, notification, transmission, or submission occurred.

Preserve all supplied policy, evidence, controller, and protected database
facts byte-for-byte. Do not use the network or claim any external, pharmacy,
benefit, prescriber, member, or clinical-system action.

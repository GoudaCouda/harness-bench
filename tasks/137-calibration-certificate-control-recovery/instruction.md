# Recover calibration-certificate control after a reference-standard recall

You are the quality systems specialist for an accredited calibration laboratory.
A signed reference-standard recall arrived out of order, a corrected measurement
result was delivered twice, and an earlier certificate-control transaction
stopped after changing only part of the SQLite register. Reconstruct the
authoritative state, recover the interrupted transaction, and stage an offline
review packet.

Everything is local. Begin with:

```bash
python3 metrologyctl.py inspect
```

Read the policy, source manifest, signed event stream, result attachments,
reference-standard records, and relevant SQLite tables. Verify signed records
with the supplied local trust material. Deduplicate identical deliveries by
event identity, order authoritative events by sequence, and treat a conflicting
duplicate sequence or a bad attachment checksum as unavailable evidence.

Reference validity is evaluated at the calibration timestamp, except that a
signed recall's `affected_from_utc` overrides the recorded validity interval.
Every standard in a job's traceability chain must be usable. Apply the published
inclusive guard-band rule using decimal arithmetic. A corrected measurement
supersedes the earlier result for the same job. Scope downstream recall review
only to recorded uses at or after the calibration timestamp; do not invent uses.

Create `certificate_control_plan.json` with exactly these top-level fields:

```text
schema_version, recovery_id, source_checkpoint, decisions,
external_actions_executed
```

Include exactly one decision per in-scope calibration job, with exactly:

```text
job_id, asset_id, certificate_id, authoritative_result_id,
reference_chain, traceability_status, error_abs, expanded_uncertainty,
guard_band_margin, measurement_decision, certificate_action, asset_action,
downstream_scope, local_mutations, evidence_refs
```

`reference_chain`, `downstream_scope`, `local_mutations`, and `evidence_refs`
are sets for comparison. Numeric fields are JSON numbers and use `null` when
authoritative measurement evidence is unavailable. Use policy vocabularies
verbatim. Evidence references are stable local `file#record` locators.

Use the guarded controller; never hand-edit the database or its receipts:

```bash
python3 metrologyctl.py preview certificate_control_plan.json
python3 metrologyctl.py apply certificate_control_plan.json
python3 metrologyctl.py verify certificate_control_plan.json
# write calibration_control_handoff.md before staging
python3 metrologyctl.py stage certificate_control_plan.json
python3 metrologyctl.py replay certificate_control_plan.json
```

`preview` must not mutate SQLite. `apply` first restores the interrupted
before-images, then commits the exact certificate, asset, assessment, and recall
projection atomically. Stable `recovery_id + source_checkpoint` identifies this
recovery. Reordering decisions or any set-valued field, or changing JSON
formatting, is the same semantic plan and must replay without mutation. A stale
checkpoint or conflicting plan for the same identity must fail before writing.

Write `calibration_control_handoff.md` for the laboratory manager and downstream
quality owners. Explain signature/deduplication authority, the recall's
effective scope, attachment integrity, each job's traceability and guard-band
decision, downstream scope, interrupted-state recovery, verification, staging,
and replay. State explicitly that no certificate was sent externally, no
customer or regulator was contacted, and no physical asset was released,
quarantined, recalled, or adjusted by this offline workflow.

Preserve policy, evidence, controller, and protected asset/job identity fields
byte-for-byte. Do not use the network or claim an external or physical action.

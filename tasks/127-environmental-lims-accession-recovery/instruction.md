# Recover an environmental-laboratory sample accession after a partial commit

You are the accession coordinator for a municipal environmental laboratory. A
local LIMS accession stopped after changing one sample row. The field-to-lab
label stream also contains out-of-order events, a byte-identical duplicate, and
a custody transfer whose signature arrived later. Reconstruct the protected
local state from signed evidence without starting analysis, notifying a client,
or releasing results.

All work is offline in the current workspace. Begin with:

```bash
python3 limsctl.py inspect
```

`inspect` publishes the exact stable `source_checkpoint`, its SHA-256 component
contract, the complete controlled decision vocabulary, and the evidence-locator
contract. Use that checkpoint directly; it binds the immutable manifest, source
bundle hash, source LIMS revision, and journal-restored baseline samples sorted
by `sample_id`.

Then inspect `policy/accession_policy.json`, the signed JSONL evidence and trust
material under `evidence/`, and the SQLite tables in `state/lims.db`. Event file
order is not authority: verify signatures, collapse only byte-equivalent event
IDs, resolve the highest authorized label-alias version, and use event timestamps
and signed late-signature checksums. An unsupported event type, conflicting
duplicate, broken alias chain, bad signature, stale source checkpoint, or wrong
sample identity must fail closed.

Apply the suite-specific receipt rules exactly. Receipt temperature,
preservation, container integrity, custody completeness, and holding time are
independent controls. A sample can therefore be accepted locally, quarantined,
or rejected. `accepted_pending_analysis` does not authorize testing; quarantine
and rejection do not authorize disposal or notification.

Create `accession_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "LIMS-ACC-20260819-07",
  "source_checkpoint": "derived protected-source checkpoint",
  "evidence_batch_id": "verified evidence batch ID",
  "decisions": [],
  "external_analysis_started": false,
  "notifications_sent": false
}
```

Include one decision for every registered sample. Each decision has exactly:

```text
sample_id, field_label, resolved_lab_label, alias_version, matrix,
analysis_suite, receipt_event_id, received_at, receipt_temperature_c,
temperature_status, preservation_status, container_status, custody_status,
holding_time_status, accession_state, local_mutations, evidence_refs,
next_local_action, external_action
```

`local_mutations` and `evidence_refs` are sets for comparison. Use policy
vocabularies and ordered disposition precedence verbatim. Evidence locators
must follow `policy/accession_policy.json#evidence_locator_contract`: cite the
registration, highest authorized alias, custody transfer, receipt observation,
and suite rule for every sample, plus the checksum-bound late signature when it
completes a pending transfer. `external_action` is always `none`.

Use the guarded workflow instead of hand-editing SQLite or generated receipts:

```bash
python3 limsctl.py preview accession_plan.json
python3 limsctl.py apply accession_plan.json
python3 limsctl.py verify accession_plan.json
python3 limsctl.py stage accession_plan.json
python3 limsctl.py replay accession_plan.json
```

`apply` first restores the interrupted journal and then commits the accession in
one SQLite transaction. `stage` records only a local pending-review receipt. The
stable `recovery_id` plus protected source checkpoint identify this recovery.
On both valid and invalid candidates, `preview` writes per-sample field and
evidence-category booleans without returning corrected values and never changes
SQLite state.
Reordering decisions, evidence, or mutation sets and changing JSON formatting is
the same semantic plan and must replay as a byte-stable no-op. A conflicting plan
for that identity must be rejected without changing the database.

Finally write `accession_handoff.md` for accession and QA reviewers. Explain the
event authority/deduplication, alias rekeys, late custody signature, each sample's
temperature/preservation/container/holding-time disposition, journal recovery,
verification, and replay. State clearly that no analysis, result release, sample
disposal, client notification, or other external action occurred.

Keep supplied policy, evidence, trust material, controller, and protected sample
identity/project fields byte-for-byte unchanged. Do not use the network or claim
any irreversible external action.

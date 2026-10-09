# Recover an interrupted DICOM de-identification export

You are the imaging-data engineer recovering a synthetic, offline DICOM research export after a worker stopped between writing a transformed instance and closing its SQLite journal. The inbound queue includes exact redelivery, a reused SOP Instance UID with different content, an unknown study, burned-in pixel-text risk, an unsupported encapsulated document, a protected study that was already exported, and a SEG object whose referenced CT UID must be remapped consistently.

The `.dcm` fixtures are compact Part-10-like test datasets: a 128-byte preamble, the `DICM` marker, then one UTF-8 JSON dataset. `dicomctl.py` is the supplied offline parser and guarded transformation tool; do not replace it or hand-edit the database or generated export files.

Start with `python3 dicomctl.py inspect`. Inspect every row in `evidence/deliveries.jsonl`, every referenced DICOM dataset, `policy/deid_policy.json`, `policy/source_manifest.json`, and all tables in `state/imaging.db`. You can use `python3 dicomctl.py query TABLE`. File order is delivery order; do not trust filenames or StudyDate as event authority.

Apply these rules:

- The first delivery of an SOP Instance UID is authoritative; an exact later redelivery is ignored and a later different dataset with the same SOP UID is quarantined as an identity collision.
- Unknown studies, unsupported SOP classes, and `BurnedInAnnotation` values other than `NO` are quarantined without generating output.
- An already-exported protected study is preserved byte-for-byte and late deliveries for it do not create or replace output.
- Eligible instances remove the listed direct identifiers and all private tags except the policy allowlist, replace PatientID with the study pseudonym, shift DA fields by the patient-specific number of days, and remap every Study, Series, SOP, and referenced SOP UID using the policy namespace.
- SEG references must resolve to an eligible instance in the same export and use that instance's remapped SOP UID. Never invent a missing reference.

Create `deid_plan.json` with exactly `schema_version`, `recovery_id`, `source_checkpoint`, `delivery_dispositions`, `instance_decisions`, `uid_map`, `totals`, and `external_exports_executed`. Use schema version `1`, recovery ID `DICOM-DEID-141-R1`, and `false` for external exports.

Each delivery disposition has exactly `delivery_id`, `sop_instance_uid`, `study_instance_uid`, `source_sequence`, and `disposition`. Each instance decision has exactly `delivery_id`, `sop_instance_uid`, `study_instance_uid`, `modality`, `disposition`, `reason`, `output_relpath`, `date_shift_days`, and `evidence_refs`. Each UID mapping has exactly `uid_type`, `original_uid`, and `deidentified_uid`. `totals` has exactly `deliveries`, `eligible_instances`, `quarantined_deliveries`, `ignored_deliveries`, `preserved_instances`, and `generated_instances`. Arrays and `evidence_refs` are sets/order-insensitive for semantic comparison. Evidence locators are visible workspace-relative `file#record` references.

Use the recovery flow:

```bash
python3 dicomctl.py preview deid_plan.json
python3 dicomctl.py apply deid_plan.json
python3 dicomctl.py verify deid_plan.json
# write deid_handoff.md before staging
python3 dicomctl.py stage deid_plan.json
python3 dicomctl.py replay deid_plan.json
```

`preview` writes `.deid_preview.json` with object-specific mismatch fields and does not mutate state. `apply` restores the interrupted before-image, replaces its PHI-bearing orphan output with a non-PHI rollback tombstone at the same path, and commits the new local export projection. `verify` parses the emitted DICOM datasets independently and checks removed identifiers, private-tag policy, date shifting, UID/reference consistency, hashes, and protected boundaries. `stage` creates only a hash-bound local review packet.

Stable `recovery_id + source_checkpoint` and the normalized semantic plan are the replay identity. Create `equivalent_deid_plan.json` by reordering arrays and evidence references; replay it and prove the database and output tree remain byte-stable. Create `conflict_deid_plan.json` with one real business decision changed; its `apply` must fail without mutation. Record the command, non-zero exit, changed field, and before/after database and export-tree SHA-256 values in `conflict_probe.json`.

Write `deid_handoff.md` for privacy, imaging, and research reviewers. Explain every delivery disposition, the collision and duplicate, quarantine reasons, UID and reference mapping, date shift, tag/private-tag handling, interrupted journal restoration, protected boundary, verification and packet hashes, equivalent replay, and conflict rejection. State that nothing was uploaded, transmitted, published, or sent to a PACS/research repository.

Preserve all supplied policy, evidence, controller, source DICOM files, and protected export rows/files byte-for-byte. Work offline and do not claim an external transfer, patient contact, clinical-system update, or deletion of a source study.

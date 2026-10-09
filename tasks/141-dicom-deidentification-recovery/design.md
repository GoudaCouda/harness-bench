# Task Design: `141-dicom-deidentification-recovery`

## 1. Workflow identity

- **Primary domain:** Compliance / medical-imaging privacy
- **Role:** imaging-data engineer recovering an offline de-identification export
- **Trigger:** a worker stopped after an output write but before journal closure
- **Objective:** restore the before-image, adjudicate dirty DICOM deliveries, transform eligible instances consistently, and stage a verified local review packet
- **Real-world consequence:** wrong UID/reference mapping can make image objects unusable, while missed tags or burned-in text can disclose patient information
- **Task family:** `dicom-deidentification-recovery`
- **Variant:** interrupted multi-study UID/reference and pixel-risk recovery

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| DICOM-PS3-15 | DICOM PS3.15 Security and System Management Profiles | https://dicom.nema.org/medical/dicom/current/output/html/part15.html | De-identification, confidentiality, and UID consistency workflow |
| DICOM-PS3-10 | DICOM PS3.10 Media Storage and File Format | https://dicom.nema.org/medical/dicom/current/output/html/part10.html | Part-10 marker and dataset-file framing |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic recovery projection and durable journal semantics |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** All patients, identifiers, studies, UIDs, images, deliveries, hashes, and events are synthetic.
- **Adaptation:** The public specifications supply privacy and file-format workflow constraints; all bounded parser behavior, local records, identities, faults, and recovery state were newly synthesized for this offline task.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The retired version was a document-selection spreadsheet task with no executable feedback or durable recovery state and was near-duplicative of earlier personal packet workflows. This rebuild models a recognizable imaging research-export operation: correlate deliveries, protect already-exported records, identify metadata and pixel disclosure risks, preserve referential UID graphs, recover a partial transaction, validate transformed binary artifacts, and stage a local privacy review. The task-only judgement is `priority`: transfer, terminal agency, recovery, complexity, verifiability, feasibility, and novelty are strong. The compact fixtures intentionally bound the Part-10 parser instead of pretending to cover every DICOM transfer syntax.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `evidence/deliveries.jsonl` | Immutable delivery order, file paths, source sequence, hashes, and output names. |
| `evidence/incoming/` | Compact binary Part-10-like DICOM datasets containing tags and reference edges. |
| `policy/deid_policy.json` | SOP, identifier, date, UID, private-tag, pixel-risk, and protected-boundary rules. |
| `policy/source_manifest.json` | Immutable-source SHA-256 registry. |
| `state/imaging.db` | Study pseudonyms/shifts, protected exports, interrupted run, before-image journal, and projection state. |
| `dicomctl.py` | Offline parser and guarded inspect/preview/apply/verify/stage/replay controller. |

## 5. Hidden ground truth

The hidden oracle stores the source-derived normalized `deid_plan.json`, independently parsed transformed datasets, exact final `state/imaging.db` rows, and protected-export hash. The evaluator does not call `dicomctl.py`: it reparses the binary wrapper, queries SQLite read-only, recomputes artifact and tree hashes, validates removed tags and the SEG-to-CT UID graph, and checks journal/run/protected state. Reference outputs and acceptance code remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `policy/deid_policy.json`, `evidence/deliveries.jsonl`, every DICOM dataset, and all `state/imaging.db` tables; derive the protected source checkpoint.
2. Resolve each delivery state in `deid_plan.json`: first-SOP authority, exact redelivery, identity collision, unknown/protected studies, SOP support, burned-in annotation, and SEG reference eligibility.
3. Build the deterministic UID map and patient-specific date shifts in `deid_plan.json`; use `.deid_preview.json` object feedback to correct mismatched fields.
4. Apply once to restore the journal and replace the partial orphan with a non-PHI tombstone while committing three files under `exports/deidentified/`, then use `state/verification.json` to close tags, graph, hashes, and the protected boundary.
5. Write `deid_handoff.md`, stage `exports/packet_manifest.json`, replay `equivalent_deid_plan.json`, and reject `conflict_deid_plan.json` without database or export-tree mutation.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Delivery, database, tag, reference, and policy evidence jointly control each decision. |
| `tool_selection` | The agent must combine shell inspection, SQLite queries, JSON parsing, hashing, and the guarded controller. |
| `multi_step_execution` | Preview, recovery, verification, staging, equivalent replay, and conflict probing depend on prior state. |
| `state_management` | An interrupted before-image and protected export boundary must survive one atomic local projection. |
| `error_recovery` | Field-level preview discrepancies and rejected conflicts create executable correction feedback. |
| `verification_behavior` | Output tags, UID graph, dates, hashes, packet, and byte-stable replay require independent closure. |
| `safety_boundary` | Source studies and protected outputs are immutable and no external export is performed. |

## 8. Stressors and difficulty

**Difficulty rationale:** Difficulty comes from coupled state, not bulk: the SEG arrives before its CT, a later file reuses a SOP UID with different content, exact redelivery must not become collision, a metadata-clean object can still have burned-in pixel risk, one study is already protected, and per-patient shifts must agree across dates and graph-linked objects. The interrupted record/orphan must be rolled back before new state, and semantic plan identity must tolerate ordering while rejecting a real decision conflict.

**Plausible failure mode:** The agent trusts file order as semantic authority, strips all private tags, leaves clinical UIDs in references, generates an unknown/protected output, or reports replay without proving byte stability.

## 9. Oracle design

| Case | Weight | Tier |
|---|---:|---|
| `delivery_authority_and_deidentification_decisions` | 0.27 | core |
| `emitted_datasets_and_uid_reference_graph` | 0.27 | core |
| `journal_recovery_and_protected_boundary` | 0.26 | core |
| `verification_packet_replay_and_conflict` | 0.12 | closure |
| `deid_handoff` | 0.08 | semantic fallback |
| `source_privacy_and_external_action_gate` | 0.00 | redline gate |

Core deterministic weight is 0.80. The handoff is the only LLM-eligible case and is capped at 0.08. The oracle explicitly covers `deid_plan.json`, `equivalent_deid_plan.json`, `conflict_deid_plan.json`, `conflict_probe.json`, `.deid_preview.json`, `state/imaging.db`, `state/verification.json`, `state/recovery_receipt.json`, `state/replay_report.json`, `exports/research_review_packet.json`, `exports/packet_manifest.json`, and `deid_handoff.md`. The reference must score 1.0; empty, pristine, and malformed workspaces score 0; source mutation or an unsafe external-action claim fails the gate. Reordered plans and evidence sets must replay without database/output mutation, while a changed business decision must fail before any write.

## 10. Leakage, isolation, and safety review

The agent sees rules and raw records but no final plan, corrected values, ground-truth UID map, reference packet, or evaluator. The public controller has no callable constructor for a complete plan or decision/final-state container; it validates a submitted candidate incrementally. Preview reports mismatched object fields without supplying target values. The network and external PACS are unnecessary. Candidate code is never executed by the grader. Mutation is limited to the declared SQLite projection, generated local outputs, closure records, and sanitization of one declared orphan into a non-PHI tombstone; immutable evidence, policy, controller, study rows, and protected file/record are compared independently. Bounded regular `.py`/`.sql` analysis helpers, ordinary Python caches, and unknown regular extras are diagnostic rather than safety failures; links, source/controller tampering, proven PHI leakage, and explicit external-action claims still fail the gate.

## 11. Pilot plan

Run the focused contracts, reference/empty/pristine/malformed discrimination, deterministic read-only oracle checks, Ruff, design-outline, leakage, and full task-suite validation before any model pilot. A fresh Gemma/OpenClaw run is required after static admission. **Expected Gemma/OpenClaw failure modes:** it may skip a SQLite or DICOM source, confuse duplicate with collision, miss pixel risk, break the SEG UID edge, trust apply without independent verification, or omit the equivalent/conflict probes. Review whether the trajectory actually inspects the databases and datasets, uses preview feedback, closes apply/verify/stage, and exercises both equivalent replay and negative conflict. Model success or failure is diagnostic evidence only and does not replace this task-only selection judgement.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

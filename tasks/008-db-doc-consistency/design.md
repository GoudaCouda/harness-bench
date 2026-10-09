# Task Design: `008-db-doc-consistency`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** production on-call engineer
- **Trigger:** A reviewed change request conflicts with a production runbook and the current cluster inventory.
- **Objective:** Repair a Production Runbook Before an On-Call Handoff
- **Real-world consequence:** A stale runbook can make the next responder apply unsafe production settings.
- **Task family:** `008-db-doc-consistency`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| POSTGRES-BACKUP-RESTORE | PostgreSQL backup and restore documentation | https://www.postgresql.org/docs/current/backup.html | 2026-08-26 | Grounds backup-method distinctions, restore assumptions, and the need for precise operational documentation. |
| GOOGLE-SRE-INCIDENT | Google SRE Workbook incident response | https://sre.google/workbook/incident-response/ | 2026-08-26 | Grounds on-call handoff, working records, explicit roles, and methodical recovery actions. |

- **Origin class:** public_workflow_adaptation
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** The public sources shape the database-runbook and handoff workflow; the cluster, change request, backup, conflicts, and correct repaired state are synthetic.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The task requires source-precedence reconciliation, an in-place operational document repair, and a reviewable verification handoff.

The downstream consequence is concrete: A stale runbook can make the next responder apply unsafe production settings. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `change_request.md` | Current synthetic evidence used by the production on-call engineer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `db/backup.sql` | Current synthetic evidence used by the production on-call engineer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `db/deployment_guide.md` | Current synthetic evidence used by the production on-call engineer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `db/environment.yml` | Current synthetic evidence used by the production on-call engineer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `db/node_inventory.json` | Current synthetic evidence used by the production on-call engineer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 6 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `change_request.md`, `db/backup.sql`, `db/deployment_guide.md`, `db/environment.yml`, `db/node_inventory.json`.

- `effective_production_configuration`: Runbook contains the effective production configuration. Every operator-facing production setting is reconciled to the governing baseline and overrides, with stale guide values removed from current instructions.
- `current_cluster_topology`: Runbook represents the commissioned multi-region cluster. The complete node table uses the authoritative membership, role, region, and latest hardware state and no longer gives false single-region guidance.
- `source_precedence_explained`: Material source precedence is operationally explicit. The guide explains the production override and newer-inventory cases that would otherwise appear to be unresolved drift.
- `safe_handoff_decision`: Documentation readiness is decided without claiming execution. The review gives a grounded READY or BLOCKED decision for guide use, remains scoped to documentation, and includes meaningful pre-use checks.
- `correction_trace`: Material corrections and evidence are traceable. The review identifies the key corrected configuration, hardware, and regional assumptions and ties them to the actual local evidence.
- `maintainable_runbook_handoff`: Revised artifacts are maintainable by the next operator. The guide and review identify the change, revision state, intended use, and residual caveat without requiring a separate answer-shape artifact.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `db/deployment_guide.md`, `change_review.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `change_request.md`, `db/backup.sql`, `db/deployment_guide.md`, `db/environment.yml`, `db/node_inventory.json` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Runbook contains the effective production configuration, Runbook represents the commissioned multi-region cluster, Material source precedence is operationally explicit; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `db/deployment_guide.md`, `change_review.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `state_management` | The agent must preserve, update, or derive a coherent business state across artifacts. |
| `verification_behavior` | Completion requires re-reading, executing, rendering, or otherwise checking the resulting state. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence.
- **Plausible failure mode:** A stale runbook can make the next responder apply unsafe production settings.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** The candidate must reconcile 5 visible source files into 6 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The task requires source-precedence reconciliation, an in-place operational document repair, and a reviewable verification handoff.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `effective_production_configuration` — Runbook contains the effective production configuration | 0.30 | Every operator-facing production setting is reconciled to the governing baseline and overrides, with stale guide values removed from current instructions. |
| `current_cluster_topology` — Runbook represents the commissioned multi-region cluster | 0.25 | The complete node table uses the authoritative membership, role, region, and latest hardware state and no longer gives false single-region guidance. |
| `source_precedence_explained` — Material source precedence is operationally explicit | 0.15 | The guide explains the production override and newer-inventory cases that would otherwise appear to be unresolved drift. |
| `safe_handoff_decision` — Documentation readiness is decided without claiming execution | 0.10 | The review gives a grounded READY or BLOCKED decision for guide use, remains scoped to documentation, and includes meaningful pre-use checks. |
| `correction_trace` — Material corrections and evidence are traceable | 0.10 | The review identifies the key corrected configuration, hardware, and regional assumptions and ties them to the actual local evidence. |
| `maintainable_runbook_handoff` — Revised artifacts are maintainable by the next operator | 0.10 | The guide and review identify the change, revision state, intended use, and residual caveat without requiring a separate answer-shape artifact. |
| `source_and_execution_boundary` — Evidence and output integrity are preserved | gate | Governed sources are unchanged and deliverables are regular files rather than links. Unsupported execution claims lose `safe_handoff_decision` credit. |

- **Critical gates:** `source_and_execution_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `db/deployment_guide.md`, `change_review.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['change_review.md'], modified=['db/deployment_guide.md'], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** A stale runbook can make the next responder apply unsafe production settings. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `effective_production_configuration`; inconsistent `current_cluster_topology`; a polished handoff without the required state change; or an unsupported execution/approval claim.
- **Expected strong-harness success band:** To be calibrated from fresh, hash-bound multi-harness pilots; no target score is used to tune this task.
- **Signals that indicate task ambiguity:** multiple competent agents make the same unsupported interpretation despite locating all visible evidence.
- **Signals that indicate environment/oracle failure:** reference failure, nondeterminism, unreadable source files, or an alternative-valid answer rejected only for wording or layout.
- **Revision rule after pilot:** repair task or verifier defects for every model/harness configuration; do not relax a correct business requirement to raise one candidate model score.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `effective_production_configuration`.
- `validation_and_replay`: `current_cluster_topology`, `source_precedence_explained`, `safe_handoff_decision`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

# Task Design: `048-research-repro-package`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** research reproducibility reviewer
- **Trigger:** A deposited analysis package contains paper claims, shipped results, executable code, a small current snapshot, and stale provenance records.
- **Objective:** Research reproducibility package completeness check
- **Real-world consequence:** Declaring reproduction from a mismatched snapshot or omitting a failed claim misrepresents scientific evidence.
- **Task family:** `048-research-repro-package`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-048 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `048-research-repro-package` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent must run the code, recompute the deposited data, compare three evidence layers, and separate executable findings from provenance gaps.

The downstream consequence is concrete: Declaring reproduction from a mismatched snapshot or omitting a failed claim misrepresents scientific evidence. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `README.md` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `data/raw_trials.csv` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `deposit_manifest.json` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `environment.lock` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `execution_log.txt` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `paper_claims.md` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `results.csv` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `scripts/analyze_main.py` | Current synthetic evidence used by the research reproducibility reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `README.md`, `data/raw_trials.csv`, `deposit_manifest.json`, `environment.lock`, `execution_log.txt`, `paper_claims.md`, `results.csv`, `scripts/analyze_main.py`.

- `claim_assessment`: Every manuscript claim is adjudicated against observed and shipped evidence. All four claim sections bind the claimed number, relevant artifact, actual observation, disagreement, and honest status.
- `execution_and_provenance`: The audit distinguishes command execution from snapshot-level reproduction. The observed main metrics, row count, freeze mismatch, and old execution record are reconciled rather than conflated.
- `repair_plan`: The closed blocker ledger gives one actionable repair per independent defect. Snapshot mismatch, retention disagreement, unsupported subgroup interface, and missing subgroup output are each covered without duplicate symptoms.
- `package_conclusion`: The release conclusion is honest and decision-ready. The conclusion states what ran, what failed to reproduce, and what a coherent release needs without fabricating success.
- `audit_integrity`: The blocker ledger is parseable, closed, and usable. The published columns, unique items, non-empty impacts, and recommended fixes form a valid handoff.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `missing_steps.csv`, `reproducibility_report.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `README.md`, `data/raw_trials.csv`, `deposit_manifest.json`, `environment.lock`, `execution_log.txt`, `paper_claims.md`, `results.csv`, `scripts/analyze_main.py` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Every manuscript claim is adjudicated against observed and shipped evidence, The audit distinguishes command execution from snapshot-level reproduction, The closed blocker ledger gives one actionable repair per independent defect; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `missing_steps.csv`, `reproducibility_report.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |
| `state_management` | The agent must preserve, update, or derive a coherent business state across artifacts. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input.
- **Plausible failure mode:** Declaring reproduction from a mismatched snapshot or omitting a failed claim misrepresents scientific evidence.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The candidate must reconcile 8 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent must run the code, recompute the deposited data, compare three evidence layers, and separate executable findings from provenance gaps.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `claim_1_assessment` — The conversion-lift claim is adjudicated against the rerun and shipped result | 0.10 | CLAIM-1 binds the claimed value, shipped table, actual rerun observation, disagreement, and honest status. |
| `claim_2_assessment` — The retention claim reconciles all three conflicting values | 0.10 | CLAIM-2 distinguishes the manuscript, shipped table, and rerun value and reaches an honest status. |
| `claim_3_assessment` — End-to-end reproducibility is distinguished from command execution | 0.10 | CLAIM-3 binds the runnable command to the mismatched snapshot size and provenance evidence. |
| `claim_4_assessment` — The subgroup claim is adjudicated against the absent interface and artifact | 0.10 | CLAIM-4 binds the claimed value, unsupported flag, missing output, and honest status. |
| `execution_and_provenance` — The audit distinguishes command execution from snapshot-level reproduction | 0.30 | The observed main metrics, row count, freeze mismatch, and old execution record are reconciled rather than conflated. |
| `repair_plan` — The closed blocker ledger gives one actionable repair per independent defect | 0.10 | Snapshot mismatch, retention disagreement, unsupported subgroup interface, and missing subgroup output are each covered without duplicate symptoms. |
| `handoff_quality` — The conclusion and blocker ledger form an honest decision-ready handoff | 0.20 | The conclusion distinguishes execution from reproduction, while the parseable ledger uses the published columns and actionable fixes. |
| `safety_and_input_integrity` — Deposit evidence and execution boundaries are preserved | gate | Source artifacts remain unchanged and no successful external publication or run is fabricated. |

- **Critical gates:** `safety_and_input_integrity`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `missing_steps.csv`, `reproducibility_report.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['missing_steps.csv', 'reproducibility_report.md'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Declaring reproduction from a mismatched snapshot or omitting a failed claim misrepresents scientific evidence. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `claim_assessment`; inconsistent `execution_and_provenance`; a polished handoff without the required state change; or an unsupported execution/approval claim.
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

- `decision_and_state`: `claim_1_assessment`, `claim_2_assessment`, `claim_3_assessment`, `claim_4_assessment`.
- `validation_and_replay`: `execution_and_provenance`, `repair_plan`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

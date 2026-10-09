# Task Design: `060-research-claims-batch-evidence-audit`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** a research analyst
- **Trigger:** Task: Batch Research Claims Evidence Audit
- **Objective:** Batch Research Claims Evidence Audit
- **Real-world consequence:** An incorrect `claim_audit.csv` would make the synthetic `Batch Research Claims Evidence Audit` handoff incomplete or operationally misleading.
- **Task family:** `060-research-claims-batch-evidence-audit`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-060 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `060-research-claims-batch-evidence-audit` reconstruction: the checked-in package transforms `claims/claims.csv`, `sources`, `sources/errata.md`, `sources/methods_appendix.md`, `sources/peer_review_notes.md`, `sources/repro_readme.md`, and 2 other entries listed in Section 4 into `claim_audit.csv`, `evidence_matrix.json`, preserving the visible action `Audit every claim and create:` and `claims/claims.csv` as the first concrete state anchor; `format` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Batch Research Claims Evidence Audit` models a Research handoff in which the agent must reconcile `claims/claims.csv`, `sources`, `sources/errata.md`, `sources/methods_appendix.md`, `sources/peer_review_notes.md`, `sources/repro_readme.md`, and 2 other entries listed in Section 4, apply the visible rule/state clauses `'status' must be exactly one of:`; `Each item must include 'claim_id', 'status', 'evidence', and 'reproducibility_note'.`; `Use only the offline materials in '$WORKSPACE'.`, and leave `claim_audit.csv`, `evidence_matrix.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `claims/claims.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources` | Agent-visible factual working material; explicitly named in the prompt | Prompt clause: 'claim_id,claim_text,status,primary_source,evidence_location,evidence_signal,secondary_sources,rationale' |
| `sources/errata.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources/methods_appendix.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources/peer_review_notes.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources/repro_readme.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources/results_table.csv` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `sources/study_summary.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `060-research-claims-batch-evidence-audit` truth reconciliation binds concrete source state `claims/claims.csv`, `sources`, `sources/errata.md`, `sources/methods_appendix.md`, `sources/peer_review_notes.md`, `sources/repro_readme.md`, and 2 other entries listed in Section 4 to required final state `claim_audit.csv`, `evidence_matrix.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `'status' must be exactly one of:`; `Each item must include 'claim_id', 'status', 'evidence', and 'reproducibility_note'.`; `Use only the offline materials in '$WORKSPACE'.`.
- `ground_truth.json` exposes maintainer keys `claims`, `repro_gap_tokens`, `overstatement_tokens`, `scoring`; salient state/key anchors `claims.CL-01.status='contradicted'`, `claims.CL-02.status='contradicted'`, `claims.CL-03.status='contradicted'`, `claims.CL-04.status='supported'`, `claims.CL-05.status='not_reproducible'`, plus 1 more; exact values remain isolated from the agent workspace.
- Reference `claim_audit.csv` has exact header `claim_id`, `claim_text`, `status`, `primary_source`, `evidence_location`, `evidence_signal`, `secondary_sources`, `rationale`, 14 data row(s); `claim_id` values begin `CL-01`, `CL-02`, `CL-03`, `CL-04`, `CL-05`, `CL-06`, plus 8 more.
- Reference `evidence_matrix.json` has top-level keys `claims`, `repro_gaps`; collection sizes `claims[14]`, `repro_gaps[4]`.
- The relocated legacy fact library retains its historical dimensions for diagnostics only. Formal score ownership belongs to the seven business-level cases in Section 13; ordinary output defects fail the cases that consume the affected record.

## 6. Expected workflow

1. Inventory the actual starting state in `claims/claims.csv`, `sources`, `sources/errata.md`, `sources/methods_appendix.md`, `sources/peer_review_notes.md`, `sources/repro_readme.md`, and 2 other entries listed in Section 4; for `060-research-claims-batch-evidence-audit`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `claims/claims.csv`: Audit every claim and create:.
3. Execute visible workflow clause 2 against `claims/claims.csv`: For numeric claims, identify the source row, metric, cohort, field, or section used..
4. Execute visible workflow clause 3 against `claims/claims.csv`: Do not run internet search..
5. Materialize the complete declared state `claim_audit.csv`, `evidence_matrix.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
6. Cross-reconcile `claim_audit.csv` with every other declared artifact and the source state `claims/claims.csv`; check shared identifiers, counts, decisions, and status transitions where present.
7. Run local parse/structure checks for `claim_audit.csv` and `evidence_matrix.json`; confirm that both records cover the same fourteen claims with valid, workspace-local evidence locators.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** none
- **Plausible failure mode:** For `Batch Research Claims Evidence Audit`, the agent may create `claim_audit.csv` but fail the declared `evidence_grounding` demand over `claims/claims.csv`, violate the rule/state clause `'status' must be exactly one of:`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** hard
- **Difficulty rationale:** Fourteen claims must be distinguished across five dispositions using document precedence, numeric cohort comparisons, multi-source corroboration, and explicit reproducibility gaps, then represented consistently in CSV and JSON. The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `format` | returned-check raw=`0.08`; 7.62% of returned positive check metadata (consult aggregation row) | claim_audit.csv header is exact; extracted from the reference oracle result |
| `coverage` | returned-check raw=`0.08`; 7.62% of returned positive check metadata (consult aggregation row) | all and only claims covered; extracted from the reference oracle result |
| `status` | returned-check raw=`0.24`; 22.86% of returned positive check metadata (consult aggregation row) | claim statuses match evidence; extracted from the reference oracle result |
| `sources` | returned-check raw=`0.14`; 13.33% of returned positive check metadata (consult aggregation row) | primary sources match decisive evidence; extracted from the reference oracle result |
| `locations` | returned-check raw=`0.12`; 11.43% of returned positive check metadata (consult aggregation row) | evidence locations cite sections rows or fields; extracted from the reference oracle result |
| `signals` | returned-check raw=`0.16`; 15.24% of returned positive check metadata (consult aggregation row) | evidence signals contain decisive tokens; extracted from the reference oracle result |
| `secondary` | returned-check raw=`0.08`; 7.62% of returned positive check metadata (consult aggregation row) | multi-source claims include required secondary sources; extracted from the reference oracle result |
| `repro_gaps` | returned-check raw=`0.05`; 4.76% of returned positive check metadata (consult aggregation row) | not_reproducible claims cite missing artifacts; extracted from the reference oracle result |
| `overstatement` | returned-check raw=`0.05`; 4.76% of returned positive check metadata (consult aggregation row) | overstated claim preserves scope limitation; extracted from the reference oracle result |
| `evidence_matrix_json` | returned-check raw=`0.05`; 4.76% of returned positive check metadata (consult aggregation row) | evidence_matrix.json mirrors claim statuses with evidence and repro gaps; extracted from the reference oracle result |
| `required_artifact_contract` | legacy diagnostic; no formal weight | Historical artifact-presence signal retained in the relocated fact library; formal cases own parseability, coverage, and claim correctness |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = 0.07 * format_score + 0.07 * coverage_score + 0.24 * status_score + 0.14 * source_score + 0.12 * location_score + 0.16 * evidence_score + 0.08 * secondary_score + 0.05 * repro_score + 0.04 * over_score + 0.03 * matrix_score` |

- **Critical gates:** Only the zero-weight safety gate may override weighted cases, for protected-source mutation or a task-specific redline. Missing or malformed ordinary deliverables fail the owning cases rather than erasing unrelated earned credit.
- **Partial-credit rationale:** Formal core cases total 0.80 across headline/methods, subgroup, operational/safety, reproducibility, and generalization outcomes; cross-source traceability and audit integrity contribute 0.10 each. Historical fractional dimensions and caps are diagnostic provenance only.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.


Artifact coverage: `claim_audit.csv` and `evidence_matrix.json` are both scored by the formal evidence-coverage and decision-consistency cases.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `060-research-claims-batch-evidence-audit`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `claim_audit.csv` while attempting `Batch Research Claims Evidence Audit`.; Agent misreads the `060-research-claims-batch-evidence-audit` rule/state anchor `'status' must be exactly one of:` while reconciling `claims/claims.csv`.; Agent violates the prompt-stated safety boundary while producing `claim_audit.csv`, `evidence_matrix.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `060-research-claims-batch-evidence-audit`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `headline_and_methods` (0.20, core): six claims about headline values,
  methods, sample, correction, exported fields, and exclusions.
- `subgroup_results` (0.15, core): partner, mobile, and regional claims.
- `operational_and_safety` (0.15, core): support-ticket and adverse-event claims.
- `reproducibility_gaps` (0.20, core): subgroup-output and end-to-end
  package reproducibility claims.
- `generalization_scope` (0.10, core): the all-customers causal overstatement.
- `cross_source_traceability` (0.10, optional): declared secondary evidence
  is retained for every multi-source adjudication.
- `audit_integrity` (0.10, optional): both schemas cover all 14 claims.

The core cases total 0.80 and optional handoff quality totals 0.20. Claim
errors are charged to their substantive cohort once; a single status mistake
cannot zero separate all-table status, evidence, reproducibility, and JSON
cases. A valid source locator may ground source content without duplicating the
same private token in every output field. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

Diagnostic review removed a hidden secondary-source requirement from CL-14.
That claim asks whether the methods appendix states that trial accounts were
excluded, so the cited M-2 passage is independently decisive; the study summary
is useful corroboration but not a necessary second source. Multi-source claims
such as CL-02 and CL-09 still require their actual secondary evidence trail.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `headline_and_methods`, `subgroup_results`.
- `validation_and_replay`: `operational_and_safety`, `reproducibility_gaps`, `generalization_scope`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

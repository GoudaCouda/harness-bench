# Task Design: `018-cross-doc-citation-check`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** research publication editor
- **Trigger:** A publication candidate cites versioned source notes and contains retired, mismatched, and missing references.
- **Objective:** Audit And Repair Cross-Document Citations
- **Real-world consequence:** A plausible but wrong source-to-claim link breaks the evidence chain and publication integrity.
- **Task family:** `018-cross-doc-citation-check`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-018 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `018-cross-doc-citation-check` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent audits claim-location-source relationships, repairs the reference set, and documents a closed citation issue ledger.

The downstream consequence is concrete: A plausible but wrong source-to-claim link breaks the evidence chain and publication integrity. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `appendix.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `report.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `review_context.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `sources/csat.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `sources/escalations.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `sources/help_center.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `sources/latency.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `sources/renewal_draft.md` | Current synthetic evidence used by the research publication editor. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 4 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `appendix.md`, `report.md`, `review_context.md`, `sources/csat.md`, `sources/escalations.md`, `sources/help_center.md`, `sources/latency.md`, `sources/renewal_draft.md`.

- `citation_issue_set`: The audit identifies the exact citation defects. The audit identifies the exact citation defects; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.
- `corrected_references`: The fixed reference list is complete and excludes retired sources. The fixed reference list is complete and excludes retired sources; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.
- `evidence_traceability`: Every citation defect is tied to the right location and repair. Each closed-set issue row must carry the correct citation, location, semantic issue, source, and affirmative repair rather than merely naming the right IDs.
- `audit_integrity`: The citation audit is parseable with the published columns. The citation audit is parseable with the published columns; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `citation_audit.csv`, `fixed_references.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `appendix.md`, `report.md`, `review_context.md`, `sources/csat.md`, `sources/escalations.md`, `sources/help_center.md`, `sources/latency.md`, `sources/renewal_draft.md` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for The audit identifies the exact citation defects, The fixed reference list is complete and excludes retired sources, Every citation defect is tied to the right location and repair; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `citation_audit.csv`, `fixed_references.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input.
- **Plausible failure mode:** A plausible but wrong source-to-claim link breaks the evidence chain and publication integrity.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The candidate must reconcile 8 visible source files into 4 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent audits claim-location-source relationships, repairs the reference set, and documents a closed citation issue ledger.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `citation_issue_set` — The audit identifies the exact citation defects | 0.34 | The audit identifies the exact citation defects; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `corrected_references` — The fixed reference list is complete and excludes retired sources | 0.25 | The fixed reference list is complete and excludes retired sources; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `evidence_traceability` — Every citation defect is tied to the right location and repair | 0.21 | Each closed-set issue row must carry the correct citation, location, semantic issue, source, and affirmative repair rather than merely naming the right IDs. |
| `audit_integrity` — The citation audit is parseable with the published columns | 0.20 | The citation audit is parseable with the published columns; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `safety_and_input_integrity` — Source evidence and execution boundaries are preserved | gate | Protected inputs and true redline boundaries remain intact; ordinary business mistakes lose their own cases instead of triggering this gate. |

- **Critical gates:** `safety_and_input_integrity`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `citation_audit.csv`, `fixed_references.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['citation_audit.csv', 'fixed_references.md'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** A plausible but wrong source-to-claim link breaks the evidence chain and publication integrity. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `citation_issue_set`; inconsistent `corrected_references`; a polished handoff without the required state change; or an unsupported execution/approval claim.
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

# Task Design: `014-contract-summary-risk`

## 1. Workflow identity

- **Primary domain:** Compliance
- **Role:** commercial contract reviewer
- **Trigger:** A master draft, signed security addendum, order form, policy, and scoped approvals must be reconciled before deal review.
- **Objective:** Summarize Contract Terms And Extract Policy Risks
- **Real-world consequence:** Treating superseded or approved terms as open risks can block a deal; omitting an effective conflict can create policy exposure.
- **Task family:** `014-contract-summary-risk`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| ICO-CONTROLLER-PROCESSOR | ICO controller-processor contracts guidance | https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/contracts-and-liabilities-between-controllers-and-processors-multi/ | 2026-08-26 | Grounds the existence and scope of data-processing contract clauses while leaving legal review facts and wording synthetic. |

- **Origin class:** public_workflow_adaptation
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** Public guidance supplies the recognizable controller-processor review context. The agreement, addendum, approvals, policy, conflicts, and dispositions are entirely synthetic and are not legal advice.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent must establish document precedence and scope, identify only current material conflicts, and hand off actionable owner-aware dispositions.

The downstream consequence is concrete: Treating superseded or approved terms as open risks can block a deal; omitting an effective conflict can create policy exposure. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `approval_register.csv` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `company_policy.md` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `contract.md` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `order_form.md` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `review_playbook.md` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `security_addendum.md` | Current synthetic evidence used by the commercial contract reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `approval_register.csv`, `company_policy.md`, `contract.md`, `order_form.md`, `review_playbook.md`, `security_addendum.md`.

- `effective_risk_register`: The register contains exactly the material effective conflicts. All five effective open conflicts are present and compliant, superseded, approved, or differently scoped terms are excluded.
- `effective_terms_summary`: The summary reconciles the effective agreement across document versions. The decision memo states the effective commercial, security, liability, and termination terms rather than treating the master draft in isolation.
- `review_boundary`: The handoff avoids unsupported legal conclusions. The package is substantive but does not claim legal approval, enforceability, or external action.
- `business_handoff`: Every open risk has an actionable owner-aware disposition. Recommendations and owners make the review usable by the deal team.
- `register_integrity`: The risk register is a valid closed business ledger. The CSV uses the published columns, valid severities, unique clause keys, and no extra rows.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `contract_summary.md`, `risk_clauses.csv`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `approval_register.csv`, `company_policy.md`, `contract.md`, `order_form.md`, `review_playbook.md`, `security_addendum.md` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for The register contains exactly the material effective conflicts, The summary reconciles the effective agreement across document versions, The handoff avoids unsupported legal conclusions; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `contract_summary.md`, `risk_clauses.csv` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules.
- **Plausible failure mode:** Treating superseded or approved terms as open risks can block a deal; omitting an effective conflict can create policy exposure.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The candidate must reconcile 6 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent must establish document precedence and scope, identify only current material conflicts, and hand off actionable owner-aware dispositions.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `effective_risk_register` — The register contains exactly the material effective conflicts | 0.40 | All five effective open conflicts are present and compliant, superseded, approved, or differently scoped terms are excluded. |
| `effective_terms_summary` — The summary reconciles the effective agreement across document versions | 0.30 | The decision memo states the effective commercial, security, liability, and termination terms rather than treating the master draft in isolation. |
| `review_boundary` — The handoff avoids unsupported legal conclusions | 0.10 | The package is substantive but does not claim legal approval, enforceability, or external action. |
| `business_handoff` — Every open risk has an actionable owner-aware disposition | 0.10 | Recommendations and owners make the review usable by the deal team. |
| `register_integrity` — The risk register is a valid closed business ledger | 0.10 | The CSV uses the published columns, valid severities, unique clause keys, and no extra rows. |
| `safety_and_input_integrity` — Source evidence and execution boundaries are preserved | gate | Protected inputs remain unchanged and the response makes no unauthorized external-action claim. |

- **Critical gates:** `safety_and_input_integrity`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `contract_summary.md`, `risk_clauses.csv`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['contract_summary.md', 'risk_clauses.csv'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Treating superseded or approved terms as open risks can block a deal; omitting an effective conflict can create policy exposure. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `effective_risk_register`; inconsistent `effective_terms_summary`; a polished handoff without the required state change; or an unsupported execution/approval claim.
- **Expected strong-harness success band:** To be calibrated from fresh, hash-bound multi-harness pilots; no target score is used to tune this task.
- **Signals that indicate task ambiguity:** multiple competent agents make the same unsupported interpretation despite locating all visible evidence.
- **Signals that indicate environment/oracle failure:** reference failure, nondeterminism, unreadable source files, or an alternative-valid answer rejected only for wording or layout.
- **Revision rule after pilot:** repair task or verifier defects for every model/harness configuration; do not relax a correct business requirement to raise one candidate model score.

The first current-package Gemma 4 31B + OpenClaw trajectory produced the exact
five-risk closed register, all effective terms, and concrete actions, but used
the task-visible owner `Deal Team` for each disposition. The hidden oracle had
required an unstated subject-department token and therefore scored every risk
row wrong. The owner equivalence was repaired while preserving concrete-action
requirements; the unchanged real model workspace then scores 1.0. Positive
and negative regressions confirm that `Deal Team` is accepted as an accountable
owner but does not rescue a vague or missing action.

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

- `decision_and_state`: `effective_risk_register`.
- `validation_and_replay`: `effective_terms_summary`, `review_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

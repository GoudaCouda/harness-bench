# Task Design: `022-policy-clause-retrieval`

## 1. Workflow identity

- **Primary domain:** Compliance
- **Role:** a compliance operations reviewer
- **Trigger:** Task: Policy Clause Retrieval and Case Rulings
- **Objective:** Policy Clause Retrieval and Case Rulings
- **Real-world consequence:** An incorrect `case_rulings.json` would make the synthetic `Policy Clause Retrieval and Case Rulings` handoff incomplete or operationally misleading.
- **Task family:** `022-policy-clause-retrieval`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-022 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `022-policy-clause-retrieval` reconstruction: the checked-in package transforms `cases.json`, `policy_amendment.md`, `policy_manual.md`, `reason_codes.json` into `case_rulings.json`, `ruling_summary.csv`, preserving the visible action `Use the policy manual, amendment, and canonical reason-code registry to rule on every case, and write '$WORKSPACE/case_rulings.json'.` and `cases.json` as the first concrete state anchor; `format` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Policy Clause Retrieval and Case Rulings` models a Compliance handoff in which the agent must reconcile `cases.json`, `policy_amendment.md`, `policy_manual.md`, `reason_codes.json`, apply the visible rule/state clauses `For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code.`; `Forbidden: do not use the internet; do not modify fixtures; do not ignore exception clauses.`; `Each element must contain: 'case_id', 'applicable_clause', 'decision', 'reason_code', 'quote_or_signal', 'secondary_clauses', 'blocking_condition', and 'missing_information'.`, and leave `case_rulings.json`, `ruling_summary.csv` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `cases.json` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `policy_amendment.md` | Normative local rule or procedure input; explicitly named in the prompt | Apply as later-state evidence only where the prompt authorizes it |
| `policy_manual.md` | Normative local rule or procedure input; explicitly named in the prompt | Use as the named rule source; do not infer an unstated override |
| `reason_codes.json` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `022-policy-clause-retrieval` truth reconciliation binds concrete source state `cases.json`, `policy_amendment.md`, `policy_manual.md`, `reason_codes.json` to required final state `case_rulings.json`, `ruling_summary.csv`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code.`; `Forbidden: do not use the internet; do not modify fixtures; do not ignore exception clauses.`; `Each element must contain: 'case_id', 'applicable_clause', 'decision', 'reason_code', 'quote_or_signal', 'secondary_clauses', 'blocking_condition', and 'missing_information'.`.
- `ground_truth.json` exposes maintainer keys `cases`, `line_items`, `summary_terms`, `scoring`; salient state/key anchors `cases.T100.decision='approve'`, `cases.T101.decision='needs_review'`, `cases.T102.decision='deny'`, `cases.T103.decision='approve'`, `cases.T104.decision='needs_review'`, plus 1 more; exact values remain isolated from the agent workspace.
- Reference `case_rulings.json` has top-level keys `rulings`; collection sizes `rulings[11]`.
- Reference `ruling_summary.csv` has exact header `case_id`, `case_decision`, `denied_lines`, `review_lines`, `approved_lines`, `controlling_clause`, `summary_reason`, 11 data row(s); `case_id` values begin `T100`, `T101`, `T102`, `T103`, `T104`, `T105`, plus 5 more.
- The reference-path scoring ledger contains positive dimensions `format`, `coverage`, `clauses`, `decisions`, `reason_codes`, `quotes`, `secondary_clauses`, `blocking_conditions`, `missing_information`, `line_item_rulings`, `ruling_summary`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `cases.json`, `policy_amendment.md`, `policy_manual.md`, `reason_codes.json`; for `022-policy-clause-retrieval`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `cases.json`: Use the policy manual, amendment, and canonical reason-code registry to rule on every case, and write '$WORKSPACE/case_rulings.json'..
3. Execute visible workflow clause 2 against `cases.json`: 'quote_or_signal' may quote the controlling policy language, identify the.
4. Execute visible workflow clause 3 against `cases.json`: For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code..
5. Execute visible workflow clause 4 against `cases.json`: Also write '$WORKSPACE/ruling_summary.csv' with header:.
6. Materialize the complete declared state `case_rulings.json`, `ruling_summary.csv`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
7. Cross-reconcile `case_rulings.json` with every other declared artifact and the source state `cases.json`; check shared identifiers, counts, decisions, and status transitions where present.
8. Run local parse/structure checks for `case_rulings.json`, `ruling_summary.csv` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input
- **Plausible failure mode:** For `Policy Clause Retrieval and Case Rulings`, the agent may create `case_rulings.json` but fail the declared `evidence_grounding` demand over `cases.json`, violate the rule/state clause `For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** hard
- **Difficulty rationale:** The legacy package provisionally labels `Policy Clause Retrieval and Case Rulings` as `hard`; completing `case_rulings.json` requires the declared `evidence_grounding` demand across 4 listed input(s), 2 required artifact(s), 11 positive reference-path oracle dimension(s), and 6 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `format` | returned-check raw=`0.06`; 5.08% of returned positive check metadata (consult aggregation row) | case_rulings.json has required schema; extracted from the reference oracle result |
| `coverage` | returned-check raw=`0.1`; 8.47% of returned positive check metadata (consult aggregation row) | all and only cases covered; extracted from the reference oracle result |
| `clauses` | returned-check raw=`0.14`; 11.86% of returned positive check metadata (consult aggregation row) | applicable clauses correct; extracted from the reference oracle result |
| `decisions` | returned-check raw=`0.24`; 20.34% of returned positive check metadata (consult aggregation row) | decisions correct; extracted from the reference oracle result |
| `reason_codes` | returned-check raw=`0.14`; 11.86% of returned positive check metadata (consult aggregation row) | reason codes correct; extracted from the reference oracle result |
| `quotes` | returned-check raw=`0.08`; 6.78% of returned positive check metadata (consult aggregation row) | quote_or_signal supports ruling; extracted from the reference oracle result |
| `secondary_clauses` | returned-check raw=`0.08`; 6.78% of returned positive check metadata (consult aggregation row) | secondary clauses capture exception rules; extracted from the reference oracle result |
| `blocking_conditions` | returned-check raw=`0.1`; 8.47% of returned positive check metadata (consult aggregation row) | blocking conditions explain deny/review decisions; extracted from the reference oracle result |
| `missing_information` | returned-check raw=`0.06`; 5.08% of returned positive check metadata (consult aggregation row) | missing_information captures absent evidence without inventing approvals; extracted from the reference oracle result |
| `line_item_rulings` | returned-check raw=`0.1`; 8.47% of returned positive check metadata (consult aggregation row) | mixed-packet line-item fields follow their controlling and secondary clauses; extracted from the reference oracle result |
| `ruling_summary` | returned-check raw=`0.08`; 6.78% of returned positive check metadata (consult aggregation row) | ruling_summary.csv enforces case coverage and explicit-line counts; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `case_rulings.json`, `ruling_summary.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = 0.05 * format_score + 0.08 * coverage_score + 0.12 * clause_score + 0.2 * decision_score + 0.12 * reason_score + 0.06 * quote_score + 0.07 * secondary_score + 0.08 * blocking_score + 0.04 * missing_score + 0.1 * line_item_score + 0.08 * summary_score` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `case_rulings.json`, `ruling_summary.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Legacy oracle cap: if `coverage_score < 1.0`, final score is capped at `0.72`.; Legacy oracle cap: if `decision_score < 0.9`, final score is capped at `0.78`.; Legacy oracle cap: if `reason_score < 0.8`, final score is capped at `0.74`.; Legacy oracle cap: if `blocking_score < 0.8`, final score is capped at `0.78`.; Legacy oracle cap: if `line_item_score < 0.8`, final score is capped at `0.74`.; Legacy oracle cap: if `summary_score < 0.85`, final score is capped at `0.78`.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 11 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (6) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `022-policy-clause-retrieval`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `case_rulings.json` while attempting `Policy Clause Retrieval and Case Rulings`.; Agent misreads the `022-policy-clause-retrieval` rule/state anchor `For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code.` while reconciling `cases.json`.; Agent violates the prompt-stated safety boundary while producing `case_rulings.json`, `ruling_summary.csv`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `022-policy-clause-retrieval`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

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

- `line_item_rulings` (core): Every request receives the correct policy ruling
- `cited_reasoning` (core): Rulings carry reason codes, quotes, and secondary clauses
- `blocking_and_gaps` (core): Blocking conditions and missing information remain explicit
- `ruling_package` (optional): The detailed rulings and summary are parseable

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

The high-concurrency Gemma/OpenClaw diagnostic completed all eight tool calls
and wrote both artifacts but reached the former 1,800-second provider boundary
during its final response after roughly 14k generated tokens. Because the
partial artifacts were still gradeable and showed genuine clause omissions,
this was not classified as a verifier or Docker failure. The task timeout is
3,600 seconds so a slow final response does not turn a substantive result into
an infrastructure timeout; content omissions remain scored normally.

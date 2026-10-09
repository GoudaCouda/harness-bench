# Task Design: `041-capacity-planning`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** an IT operations practitioner
- **Trigger:** You are planning launch-window capacity for multiple services using only offline data.
- **Objective:** Capacity planning from traffic history and instance catalog
- **Real-world consequence:** An incorrect `capacity_plan.json` would make the synthetic `Capacity planning from traffic history and instance catalog` handoff incomplete or operationally misleading.
- **Task family:** `041-capacity-planning`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-041 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `041-capacity-planning` reconstruction: the checked-in package transforms `instance_types.json`, `traffic_history.csv` into `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`, preserving the visible action `Create exactly these output files:` and `instance_types.json` as the first concrete state anchor; `capacity_plan` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Capacity planning from traffic history and instance catalog` models a IT Operations handoff in which the agent must reconcile `instance_types.json`, `traffic_history.csv`, apply the visible rule/state clauses `checkout-api must use on-demand only. pricing-worker may use a spot/on-demand mix, but spot cannot exceed spot_max_share.`; `Do not modify input files. Do not use current date, network APIs, or cloud pricing APIs.`; `The combined hourly cost must stay under total_hourly_budget_usd.`, and leave `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `instance_types.json` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `traffic_history.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `041-capacity-planning` truth reconciliation binds concrete source state `instance_types.json`, `traffic_history.csv` to required final state `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `checkout-api must use on-demand only. pricing-worker may use a spot/on-demand mix, but spot cannot exceed spot_max_share.`; `Do not modify input files. Do not use current date, network APIs, or cloud pricing APIs.`; `The combined hourly cost must stay under total_hourly_budget_usd.`.
- `ground_truth.json` exposes maintainer keys `expected`, `cost_keywords`, `risk_tradeoffs_path`, `risk_terms`, `scoring`; exact values remain isolated from the agent workspace.
- Reference `capacity_plan.json` has top-level keys `services`, `total_hourly_cost_usd`; collection sizes `services[2]`.
- Reference `cost_notes.md` has 2 non-empty line(s); its first state/content anchor is `# Cost notes`.
- Reference `risk_tradeoffs.csv` has exact header `risk`, `tradeoff`, `mitigation`, 4 data row(s); `risk` values begin `budget`, `spot`, `incompatible`, `headroom`.
- The reference-path scoring ledger contains positive dimensions `capacity_plan`, `cost_notes`, `risk_tradeoffs`, `source_unchanged`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `instance_types.json`, `traffic_history.csv`; for `041-capacity-planning`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `instance_types.json`: Create exactly these output files:.
3. Materialize the complete declared state `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
4. Cross-reconcile `capacity_plan.json` with every other declared artifact and the source state `instance_types.json`; check shared identifiers, counts, decisions, and status transitions where present.
5. Run local parse/structure checks for `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |
| `tool_selection` | The task exposes more than one possible operation and rewards the appropriate one. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules
- **Plausible failure mode:** For `Capacity planning from traffic history and instance catalog`, the agent may create `capacity_plan.json` but fail the declared `multi_step_execution` demand over `instance_types.json`, violate the rule/state clause `checkout-api must use on-demand only. pricing-worker may use a spot/on-demand mix, but spot cannot exceed spot_max_share.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** medium
- **Difficulty rationale:** The legacy package provisionally labels `Capacity planning from traffic history and instance catalog` as `medium`; completing `capacity_plan.json` requires the declared `multi_step_execution` demand across 2 listed input(s), 3 required artifact(s), 4 positive reference-path oracle dimension(s), and 0 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `capacity_plan` | returned-check raw=`0.68`; 68.00% of returned positive check metadata (consult aggregation row) | capacity_plan.json has forecast, headroom, count, and cost; extracted from the reference oracle result |
| `cost_notes` | returned-check raw=`0.14`; 14.00% of returned positive check metadata (consult aggregation row) | cost_notes.md explains calculation and alternatives; extracted from the reference oracle result |
| `risk_tradeoffs` | returned-check raw=`0.12`; 12.00% of returned positive check metadata (consult aggregation row) | risk_tradeoffs.csv covers budget, spot, compatibility, and SLO headroom; extracted from the reference oracle result |
| `source_unchanged` | returned-check raw=`0.06`; 6.00% of returned positive check metadata (consult aggregation row) | fixtures are not modified; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = plan_score * weights['capacity_plan'] + notes_score * weights['cost_notes'] + risk_score * weights['risk_tradeoffs'] + float(unchanged) * weights['source_unchanged']` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Oracle AST audit found no explicit conditional final-score cap; the hard required-artifact gate still applies.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 4 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (0) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `041-capacity-planning`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `capacity_plan.json` while attempting `Capacity planning from traffic history and instance catalog`.; Agent misreads the `041-capacity-planning` rule/state anchor `checkout-api must use on-demand only. pricing-worker may use a spot/on-demand mix, but spot cannot exceed spot_max_share.` while reconciling `instance_types.json`.; Agent violates the prompt-stated safety boundary while producing `capacity_plan.json`, `cost_notes.md`, `risk_tradeoffs.csv`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `041-capacity-planning`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Consistency-review notes

- Capacity arithmetic and constraint satisfaction are authoritative. Cost notes
  are graded by the required concepts and figures, not a hidden sentence template.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `capacity_forecast` (0.20, core): Forecast peaks, headroom targets, regions,
  and redundancy requirements are correct for both services.
- `capacity_selection` (0.30, core): The submitted instance types, purchase
  options, counts, zone allocations, delivered capacity, and SLO headroom form
  the lowest-cost feasible plans.
- `cost_accounting` (0.15, core): Service and combined costs, assumptions,
  calculation explanations, budget check, and a rejected alternative are all
  present.
- `risk_tradeoffs` (0.15, core): Budget, spot availability, incompatible
  instances, and SLO headroom are covered as usable risk/mitigation rows.
- `planning_handoff` (0.20, optional): Submitted service coverage and totals
  reconcile across the three artifacts without charging gold facts twice.

The former aggregate thresholds allowed an explicitly required assumption or
cost-note element to disappear while the corresponding core case still
passed. Forecast truth, optimal selection, cost communication, and risk
communication now have separate owners. A complete-looking package cannot
average away a missing required business block.

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

`planning_handoff` checks cross-artifact coherence rather than replaying the
three preceding cases: service coverage and total cost must reconcile between
the plan and notes, and the risk table must be usable for both services. A
missing risk category therefore loses `risk_tradeoffs` once, while a coherent
package can still earn the handoff outcome.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `capacity_forecast`, `capacity_selection`.
- `validation_and_replay`: `cost_accounting`, `risk_tradeoffs`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

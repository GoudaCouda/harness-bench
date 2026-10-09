# Task Design: `057-metric-definition-migration-diff`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** a data analyst
- **Trigger:** Compare old and new metric definitions and report migration differences using only local files.
- **Objective:** Metric definition migration before/after difference report
- **Real-world consequence:** An incorrect `caveats.md` would make the synthetic `Metric definition migration before/after difference report` handoff incomplete or operationally misleading.
- **Task family:** `057-metric-definition-migration-diff`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-057 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `057-metric-definition-migration-diff` reconstruction: the checked-in package transforms `dashboard_after.csv`, `dashboard_before.csv`, `migration_policy.md`, `new_metric_definitions.md`, `old_metric_definitions.md`, `query_exports/new_results.csv`, and 1 other entries listed in Section 4 into `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv`, preserving the visible action `Compare old and new metric definitions and report migration differences using only local files.` and `dashboard_after.csv` as the first concrete state anchor; `fixture_present_old_metric_definitions.md` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Metric definition migration before/after difference report` models a Data Analytics handoff in which the agent must reconcile `dashboard_after.csv`, `dashboard_before.csv`, `migration_policy.md`, `new_metric_definitions.md`, `old_metric_definitions.md`, `query_exports/new_results.csv`, and 1 other entries listed in Section 4, apply the visible rule/state clauses `metric_migration_diff.csv exact header:`; `classification must be one of: expected_definition_change, unexpected_regression, no_material_change, requires_review.`; `regression_ledger.csv exact header:`, and leave `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `dashboard_after.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `dashboard_before.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `migration_policy.md` | Normative local rule or procedure input; explicitly named in the prompt | Use as the named rule source; do not infer an unstated override |
| `new_metric_definitions.md` | Schema, inventory, or contract input; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `old_metric_definitions.md` | Schema, inventory, or contract input; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `query_exports/new_results.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `query_exports/old_results.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `057-metric-definition-migration-diff` truth reconciliation binds concrete source state `dashboard_after.csv`, `dashboard_before.csv`, `migration_policy.md`, `new_metric_definitions.md`, `old_metric_definitions.md`, `query_exports/new_results.csv`, and 1 other entries listed in Section 4 to required final state `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv`; hidden materials are oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `metric_migration_diff.csv exact header:`; `classification must be one of: expected_definition_change, unexpected_regression, no_material_change, requires_review.`; `regression_ledger.csv exact header:`.
- `057-metric-definition-migration-diff` has no separate `ground_truth.json`; expected state is encoded in `oracle_grade.py` and the checked-in `reference/`.
- Reference `caveats.md` has 2 non-empty line(s); its first state/content anchor is `# Caveats`.
- Reference `metric_migration_diff.csv` has exact header `metric_name`, `old_value`, `new_value`, `absolute_diff`, `relative_diff`, `expected_direction`, `classification`, 5 data row(s); `metric_name` values begin `activation_rate`, `arr`, `gross_margin`, `retention_rate`, `support_sla`.
- Reference `migration_summary.json` has top-level keys `total_metrics`, `expected_definition_change_count`, `unexpected_regression_count`, `no_material_change_count`, `requires_review_count`, `largest_relative_diff_metric`.
- Reference `regression_ledger.csv` has exact header `metric_name`, `bad_field`, `policy_clause`, `severity`, 1 data row(s); `metric_name` values begin `retention_rate`.
- The legacy fact library retains `required_artifact_contract` only as a non-rewarding diagnostic. Formal Standard207 scoring is owned by the business cases in `tests/cases.yaml`; a missing ordinary deliverable fails its dependent case rather than zeroing otherwise valid work.

## 6. Expected workflow

1. Inventory the actual starting state in `dashboard_after.csv`, `dashboard_before.csv`, `migration_policy.md`, `new_metric_definitions.md`, `old_metric_definitions.md`, `query_exports/new_results.csv`, and 1 other entries listed in Section 4; for `057-metric-definition-migration-diff`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `dashboard_after.csv`: Compare old and new metric definitions and report migration differences using only local files..
3. Execute visible workflow clause 2 against `dashboard_after.csv`: Create:.
4. Execute visible workflow clause 3 against `dashboard_after.csv`: Compare every metric in old_results.csv or new_results.csv..
5. Materialize the complete declared state `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
6. Cross-reconcile `caveats.md` with every other declared artifact and the source state `dashboard_after.csv`; check shared identifiers, counts, decisions, and status transitions where present.
7. Run local parse/structure checks for `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, high_stakes_rules
- **Plausible failure mode:** For `Metric definition migration before/after difference report`, the agent may create `caveats.md` but fail the declared `evidence_grounding` demand over `dashboard_after.csv`, violate the rule/state clause `metric_migration_diff.csv exact header:`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** medium
- **Difficulty rationale:** The legacy package provisionally labels `Metric definition migration before/after difference report` as `hard`; completing `caveats.md` requires the declared `evidence_grounding` demand across 7 listed input(s), 4 required artifact(s), 20 positive reference-path oracle dimension(s), and 3 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `fixture_present_old_metric_definitions.md` | returned-check raw=`0.01`; 0.87% of returned positive check metadata (consult aggregation row) | fixture_present_old_metric_definitions.md; extracted from the reference oracle result |
| `fixture_present_new_metric_definitions.md` | returned-check raw=`0.01`; 0.87% of returned positive check metadata (consult aggregation row) | fixture_present_new_metric_definitions.md; extracted from the reference oracle result |
| `fixture_present_dashboard_before.csv` | returned-check raw=`0.01`; 0.87% of returned positive check metadata (consult aggregation row) | fixture_present_dashboard_before.csv; extracted from the reference oracle result |
| `fixture_present_dashboard_after.csv` | returned-check raw=`0.01`; 0.87% of returned positive check metadata (consult aggregation row) | fixture_present_dashboard_after.csv; extracted from the reference oracle result |
| `fixture_present_migration_policy.md` | returned-check raw=`0.01`; 0.87% of returned positive check metadata (consult aggregation row) | fixture_present_migration_policy.md; extracted from the reference oracle result |
| `diff_exists` | returned-check raw=`0.06`; 5.22% of returned positive check metadata (consult aggregation row) | diff_exists; extracted from the reference oracle result |
| `diff_header` | returned-check raw=`0.06`; 5.22% of returned positive check metadata (consult aggregation row) | diff_header; extracted from the reference oracle result |
| `diff_coverage` | returned-check raw=`0.08`; 6.96% of returned positive check metadata (consult aggregation row) | diff_coverage; extracted from the reference oracle result |
| `diff_values` | returned-check raw=`0.16`; 13.91% of returned positive check metadata (consult aggregation row) | diff_values; extracted from the reference oracle result |
| `diff_classifications` | returned-check raw=`0.12`; 10.43% of returned positive check metadata (consult aggregation row) | diff_classifications; extracted from the reference oracle result |
| `diff_directions` | returned-check raw=`0.04`; 3.48% of returned positive check metadata (consult aggregation row) | diff_directions; extracted from the reference oracle result |
| `classification_distinguishes_expected_vs_regression` | returned-check raw=`0.08`; 6.96% of returned positive check metadata (consult aggregation row) | classification_distinguishes_expected_vs_regression; extracted from the reference oracle result |
| `regression_exists` | returned-check raw=`0.05`; 4.35% of returned positive check metadata (consult aggregation row) | regression_exists; extracted from the reference oracle result |
| `regression_header` | returned-check raw=`0.05`; 4.35% of returned positive check metadata (consult aggregation row) | regression_header; extracted from the reference oracle result |
| `regression_required` | returned-check raw=`0.1`; 8.70% of returned positive check metadata (consult aggregation row) | regression_required; extracted from the reference oracle result |
| `regression_no_extra` | returned-check raw=`0.04`; 3.48% of returned positive check metadata (consult aggregation row) | regression_no_extra; extracted from the reference oracle result |
| `summary_exists` | returned-check raw=`0.05`; 4.35% of returned positive check metadata (consult aggregation row) | summary_exists; extracted from the reference oracle result |
| `summary_*` | six returned field checks raw=`0.02` each; aggregate raw=`0.12` | Summary counts and largest-difference metric are graded independently |
| `summary_exact` | returned-check raw=`0` (diagnostic) | Reports whether the complete summary matches without duplicating field deductions |
| `caveats_exists` | returned-check raw=`0.03`; 2.61% of returned positive check metadata (consult aggregation row) | caveats_exists; extracted from the reference oracle result |
| `caveats_required` | returned-check raw=`0.06`; 5.22% of returned positive check metadata (consult aggregation row) | caveats_required; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = sum((c['weight'] for c in checks))` |
| `aggregation_formula_02` | authoritative executable formula; not an extra check | `score = round(sum((c['weight'] for c in checks if c['pass'])) / total, 4)` |

- **Critical gates:** only `safety_and_input_integrity` can force final score `0.0`, for protected-source mutation or a true workspace/action redline. Missing, empty, or malformed ordinary deliverables fail their owning business cases at natural weight.
- **Partial-credit rationale:** Each metric is graded independently for values, classification, and policy-supported direction. Each summary field is also independent, so one local error cannot erase unrelated correct comparisons.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `057-metric-definition-migration-diff`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `caveats.md` while attempting `Metric definition migration before/after difference report`.; Agent misreads the `057-metric-definition-migration-diff` rule/state anchor `metric_migration_diff.csv exact header:` while reconciling `dashboard_after.csv`.; Agent violates the prompt-stated safety boundary while producing `caveats.md`, `metric_migration_diff.csv`, `migration_summary.json`, `regression_ledger.csv`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `057-metric-definition-migration-diff`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

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

- `metric_diff` (core): Every metric has the correct old/new values, direction, and classification
- `regression_register` (core): Unexpected regressions are isolated without extras
- `migration_summary` (core): Aggregate counts and largest change reconcile to the diff
- `summary_reconciliation` (optional): The published diff schema is respected and summary counts plus the largest change recompute from the submitted rows. It does not compare those values to gold a second time.
- `decision_caveats` (optional): The handoff records the required interpretation caveats

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

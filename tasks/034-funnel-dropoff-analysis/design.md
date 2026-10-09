# Task Design: `034-funnel-dropoff-analysis`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** a data analyst
- **Trigger:** Analyze the product funnel from local event logs with cohort comparison and data-quality caveats.
- **Objective:** Product funnel dropoff analysis from JSONL events
- **Real-world consequence:** An incorrect `cohort_comparison.csv` would make the synthetic `Product funnel dropoff analysis from JSONL events` handoff incomplete or operationally misleading.
- **Task family:** `034-funnel-dropoff-analysis`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-034 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `034-funnel-dropoff-analysis` reconstruction: the checked-in package transforms `events.jsonl` into `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`, preserving the visible action `Create:` and `events.jsonl` as the first concrete state anchor; `fixture_present` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Product funnel dropoff analysis from JSONL events` models a Data Analytics handoff in which the agent must reconcile `events.jsonl`, apply the visible rule/state clauses `deduplicated_stage_user_ids must list users with at least one repeated valid stage event ignored after the first valid event for that user and stage.`; `Count unique users who reached each stage in the required order. Ignore stage events that occur before the user has reached the previous stage, but allow a later valid event for the same stage to count.`; `deduplicated_stage_events counts repeated valid stage event records ignored after the first valid event for that user and stage.`, and leave `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `events.jsonl` | Structured operational evidence; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `034-funnel-dropoff-analysis` truth reconciliation binds concrete source state `events.jsonl` to required final state `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `deduplicated_stage_user_ids must list users with at least one repeated valid stage event ignored after the first valid event for that user and stage.`; `Count unique users who reached each stage in the required order. Ignore stage events that occur before the user has reached the previous stage, but allow a later valid event for the same stage to count.`; `deduplicated_stage_events counts repeated valid stage event records ignored after the first valid event for that user and stage.`.
- `ground_truth.json` exposes maintainer keys `outputs`, `fixture_hashes`, `stages`, `largest_dropoff`, `excluded_bot_users`, `data_quality`, `cohort_header`, `cohort_rows`, `required_insight_terms`, `stage_user_sets`; exact values remain isolated from the agent workspace.
- Reference `cohort_comparison.csv` has exact header `cohort`, `visit_users`, `purchase_users`, `purchase_rate`, `largest_dropoff_transition`, 3 data row(s); `cohort` values begin `beta`, `control`, `variant`.
- Reference `dropoff_insights.md` has 2 non-empty line(s); its first state/content anchor is `# Funnel insights`.
- Reference `funnel_metrics.json` has top-level keys `stages`, `largest_dropoff`, `excluded_bot_users`, `data_quality`; collection sizes `stages[5]`, `largest_dropoff[4]`, `excluded_bot_users[2]`, `data_quality[2]`.
- Reference `stage_user_sets.json` has top-level keys `stage_users`, `largest_dropoff_lost_user_ids`, `ignored_order_user_ids`, `deduplicated_stage_user_ids`; collection sizes `stage_users[5]`, `largest_dropoff_lost_user_ids[3]`, `ignored_order_user_ids[3]`, `deduplicated_stage_user_ids[2]`.
- The reference-path scoring ledger contains positive dimensions `fixture_present`, `fixtures_unchanged`, `json_exists`, `insights_exists`, `cohort_exists`, `stage_user_sets_exists`, `stage_count`, `stage_order`, `stage_metrics_exact`, `largest_dropoff_exact`, `bot_exclusion_recorded`, `ignored_order_events_exact`, `deduplicated_stage_events_exact`, `largest_dropoff_lost_users`, `cohort_header`, `cohort_rows`, `third_cohort_present`, `stage_user_sets_exact`, `largest_dropoff_lost_user_ids_exact`, `ignored_order_user_ids_exact`, `deduplicated_stage_user_ids_exact`, `insights_mentions_transition`, `insights_has_followup`, `insights_cohort_caveat`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `events.jsonl`; for `034-funnel-dropoff-analysis`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `events.jsonl`: Create:.
3. Execute visible workflow clause 2 against `events.jsonl`: Sort each user's non-bot events by timestamp before evaluating the funnel. CSV/JSONL row order is not guaranteed..
4. Execute visible workflow clause 3 against `events.jsonl`: Deduplicate repeated valid stage events for the same user..
5. Execute visible workflow clause 4 against `events.jsonl`: Sort rows by cohort name ascending..
6. Materialize the complete declared state `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
7. Cross-reconcile `cohort_comparison.csv` with every other declared artifact and the source state `events.jsonl`; check shared identifiers, counts, decisions, and status transitions where present.
8. Run local parse/structure checks for `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules
- **Plausible failure mode:** For `Product funnel dropoff analysis from JSONL events`, the agent may create `cohort_comparison.csv` but fail the declared `multi_step_execution` demand over `events.jsonl`, violate the rule/state clause `deduplicated_stage_user_ids must list users with at least one repeated valid stage event ignored after the first valid event for that user and stage.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** medium
- **Difficulty rationale:** The legacy package provisionally labels `Product funnel dropoff analysis from JSONL events` as `medium`; completing `cohort_comparison.csv` requires the declared `multi_step_execution` demand across 1 listed input(s), 4 required artifact(s), 24 positive reference-path oracle dimension(s), and 0 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `fixture_present` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | fixture_present; extracted from the reference oracle result |
| `fixtures_unchanged` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | fixtures_unchanged; extracted from the reference oracle result |
| `json_exists` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | json_exists; extracted from the reference oracle result |
| `insights_exists` | returned-check raw=`0.04`; 2.19% of returned positive check metadata (consult aggregation row) | insights_exists; extracted from the reference oracle result |
| `cohort_exists` | returned-check raw=`0.06`; 3.28% of returned positive check metadata (consult aggregation row) | cohort_exists; extracted from the reference oracle result |
| `stage_user_sets_exists` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | stage_user_sets_exists; extracted from the reference oracle result |
| `stage_count` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | stage_count; extracted from the reference oracle result |
| `stage_order` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | stage_order; extracted from the reference oracle result |
| `stage_metrics_exact` | returned-check raw=`0.24`; 13.11% of returned positive check metadata (consult aggregation row) | stage_metrics_exact; extracted from the reference oracle result |
| `largest_dropoff_exact` | returned-check raw=`0.12`; 6.56% of returned positive check metadata (consult aggregation row) | largest_dropoff_exact; extracted from the reference oracle result |
| `bot_exclusion_recorded` | returned-check raw=`0.06`; 3.28% of returned positive check metadata (consult aggregation row) | bot_exclusion_recorded; extracted from the reference oracle result |
| `ignored_order_events_exact` | returned-check raw=`0.04`; 2.19% of returned positive check metadata (consult aggregation row) | ignored_order_events_exact; extracted from the reference oracle result |
| `deduplicated_stage_events_exact` | returned-check raw=`0.04`; 2.19% of returned positive check metadata (consult aggregation row) | deduplicated_stage_events_exact; extracted from the reference oracle result |
| `largest_dropoff_lost_users` | returned-check raw=`0.03`; 1.64% of returned positive check metadata (consult aggregation row) | largest_dropoff_lost_users; extracted from the reference oracle result |
| `cohort_header` | returned-check raw=`0.05`; 2.73% of returned positive check metadata (consult aggregation row) | cohort_header; extracted from the reference oracle result |
| `cohort_rows` | returned-check raw=`0.12`; 6.56% of returned positive check metadata (consult aggregation row) | cohort_rows; extracted from the reference oracle result |
| `third_cohort_present` | returned-check raw=`0.04`; 2.19% of returned positive check metadata (consult aggregation row) | third_cohort_present; extracted from the reference oracle result |
| `stage_user_sets_exact` | returned-check raw=`0.2`; 10.93% of returned positive check metadata (consult aggregation row) | stage_user_sets_exact; extracted from the reference oracle result |
| `largest_dropoff_lost_user_ids_exact` | returned-check raw=`0.08`; 4.37% of returned positive check metadata (consult aggregation row) | largest_dropoff_lost_user_ids_exact; extracted from the reference oracle result |
| `ignored_order_user_ids_exact` | returned-check raw=`0.06`; 3.28% of returned positive check metadata (consult aggregation row) | ignored_order_user_ids_exact; extracted from the reference oracle result |
| `deduplicated_stage_user_ids_exact` | returned-check raw=`0.06`; 3.28% of returned positive check metadata (consult aggregation row) | deduplicated_stage_user_ids_exact; extracted from the reference oracle result |
| `insights_mentions_transition` | returned-check raw=`0.03`; 1.64% of returned positive check metadata (consult aggregation row) | insights_mentions_transition; extracted from the reference oracle result |
| `insights_has_followup` | returned-check raw=`0.03`; 1.64% of returned positive check metadata (consult aggregation row) | insights_has_followup; extracted from the reference oracle result |
| `insights_cohort_caveat` | returned-check raw=`0.05`; 2.73% of returned positive check metadata (consult aggregation row) | insights_cohort_caveat; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `score = round(sum((c['weight'] for c in checks if c['pass'])) / total_w, 4) if total_w else 0.0` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Oracle AST audit found no explicit conditional final-score cap; the hard required-artifact gate still applies.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 24 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (0) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `034-funnel-dropoff-analysis`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `cohort_comparison.csv` while attempting `Product funnel dropoff analysis from JSONL events`.; Agent misreads the `034-funnel-dropoff-analysis` rule/state anchor `deduplicated_stage_user_ids must list users with at least one repeated valid stage event ignored after the first valid event for that user and stage.` while reconciling `events.jsonl`.; Agent violates the prompt-stated safety boundary while producing `cohort_comparison.csv`, `dropoff_insights.md`, `funnel_metrics.json`, `stage_user_sets.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `034-funnel-dropoff-analysis`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Consistency-review notes

- Transition labels are compared semantically across ordinary arrow-spacing
  variants. Product follow-up prose is not an unpublished scoring requirement.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `funnel_metrics` (core): Stage counts, conversion, and drop-off metrics are exact
- `user_reconciliation` (core): User sets reconcile ignored, duplicate, and lost events
- `cohort_analysis` (core): Cohort rows and the key caveat are correct
- `stakeholder_insight` (optional, 0.20): The narrative identifies the decisive transition and caveat. Structural existence checks are diagnostics only because the three core outcomes already require parseable structured artifacts; they are not scored a second time.

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

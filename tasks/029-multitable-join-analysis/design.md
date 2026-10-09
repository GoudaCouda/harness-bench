# Task Design: `029-multitable-join-analysis`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** a data analyst
- **Trigger:** Build customer-level revenue metrics and a reconciliation note from local tables.
- **Objective:** Customer metrics from joined order and refund tables
- **Real-world consequence:** An incorrect `customer_metrics.csv` would make the synthetic `Customer metrics from joined order and refund tables` handoff incomplete or operationally misleading.
- **Task family:** `029-multitable-join-analysis`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-029 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `029-multitable-join-analysis` reconstruction: the checked-in package transforms `chargebacks.csv`, `customers.csv`, `fx_rates.csv`, `orders.csv`, `payments.csv`, `refunds.csv` into `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`, preserving the visible action `Create:` and `chargebacks.csv` as the first concrete state anchor; `fixtures_unchanged` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Customer metrics from joined order and refund tables` models a Data Analytics handoff in which the agent must reconcile `chargebacks.csv`, `customers.csv`, `fx_rates.csv`, `orders.csv`, `payments.csv`, `refunds.csv`, apply the visible rule/state clauses `Gross revenue comes from captured payments, not from order_amount. Ignore duplicate payment rows only when '(order_id, amount, currency, status)' all match; captured payments for the same order with different amounts are additive.`; `Chargebacks count only when they reference an included paid/captured order and status is won_by_customer. won_by_merchant chargebacks are reconciliation notes but not revenue deductions.`; `customer_metrics.csv columns, in this exact order:`, and leave `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `chargebacks.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `customers.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `fx_rates.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `orders.csv` | Structured operational evidence; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `payments.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `refunds.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `029-multitable-join-analysis` truth reconciliation binds concrete source state `chargebacks.csv`, `customers.csv`, `fx_rates.csv`, `orders.csv`, `payments.csv`, `refunds.csv` to required final state `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `Gross revenue comes from captured payments, not from order_amount. Ignore duplicate payment rows only when '(order_id, amount, currency, status)' all match; captured payments for the same order with different amounts are additive.`; `Chargebacks count only when they reference an included paid/captured order and status is won_by_customer. won_by_merchant chargebacks are reconciliation notes but not revenue deductions.`; `customer_metrics.csv columns, in this exact order:`.
- `ground_truth.json` exposes maintainer keys `output`, `region_summary`, `audit`, `notes`, `header`, `rows`, `region_summary_expected`, `fixture_counts`, `fixture_hashes`, `required_notes_terms`, `audit_expected`; exact values remain isolated from the agent workspace.
- Reference `customer_metrics.csv` has exact header `canonical_customer_id`, `name`, `region`, `order_count`, `gross_revenue_usd`, `refund_amount_usd`, `chargeback_amount_usd`, `net_revenue_usd`, `segment`, 7 data row(s); `canonical_customer_id` values begin `C001`, `C002`, `C003`, `C004`, `C005`, `C008`, plus 1 more.
- Reference `reconciliation_audit.json` has top-level keys `duplicate_payment_ids`, `orphan_payment_ids`, `refund_anomaly_ids`, `included_chargeback_ids`, `excluded_chargeback_ids`, `alias_customer_ids`; collection sizes `duplicate_payment_ids[2]`, `orphan_payment_ids[2]`, `refund_anomaly_ids[3]`, `included_chargeback_ids[2]`, `excluded_chargeback_ids[2]`, `alias_customer_ids[3]`.
- Reference `reconciliation_notes.md` has 3 non-empty line(s); its first state/content anchor is `# Reconciliation notes`.
- Reference `region_summary.json` has top-level keys `Central`, `East`, `North`, `South`, `West`; collection sizes `Central[3]`, `East[3]`, `North[3]`, `South[3]`, `West[3]`.
- The reference-path scoring ledger contains positive dimensions `fixtures_unchanged`, `fixture_customers_unchanged`, `fixture_orders_unchanged`, `fixture_refunds_unchanged`, `fixture_payments_unchanged`, `fixture_fx_rates_unchanged`, `fixture_chargebacks_unchanged`, `output_exists`, `exact_header`, `all_canonical_customers_once`, `exact_metric_rows`, `multi_alias_merge`, `refund_and_chargeback_deducted`, `cancelled_order_excluded`, `same_order_different_amount_additive`, `platinum_boundary`, `money_format`, `region_summary_exists`, `region_summary_values`, `reconciliation_audit_exists`, `reconciliation_audit_keys`, `reconciliation_audit_exact`, `audit_chargeback_classification`, `audit_refund_anomaly_classification`, `notes_exists`, `notes_anomalies`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `chargebacks.csv`, `customers.csv`, `fx_rates.csv`, `orders.csv`, `payments.csv`, `refunds.csv`; for `029-multitable-join-analysis`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `chargebacks.csv`: Create:.
3. Execute visible workflow clause 2 against `chargebacks.csv`: Mention the canonical customer merge..
4. Materialize the complete declared state `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
5. Cross-reconcile `customer_metrics.csv` with every other declared artifact and the source state `chargebacks.csv`; check shared identifiers, counts, decisions, and status transitions where present.
6. Run local parse/structure checks for `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, high_stakes_rules
- **Plausible failure mode:** For `Customer metrics from joined order and refund tables`, the agent may create `customer_metrics.csv` but fail the declared `evidence_grounding` demand over `chargebacks.csv`, violate the rule/state clause `Gross revenue comes from captured payments, not from order_amount. Ignore duplicate payment rows only when '(order_id, amount, currency, status)' all match; captured payments for the same order with different amounts are additive.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** medium
- **Difficulty rationale:** The legacy package provisionally labels `Customer metrics from joined order and refund tables` as `medium`; completing `customer_metrics.csv` requires the declared `evidence_grounding` demand across 6 listed input(s), 4 required artifact(s), 26 positive reference-path oracle dimension(s), and 1 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `fixtures_unchanged` | returned-check raw=`0.06`; 3.21% of returned positive check metadata (consult aggregation row) | fixtures_unchanged; extracted from the reference oracle result |
| `fixture_customers_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_customers_unchanged; extracted from the reference oracle result |
| `fixture_orders_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_orders_unchanged; extracted from the reference oracle result |
| `fixture_refunds_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_refunds_unchanged; extracted from the reference oracle result |
| `fixture_payments_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_payments_unchanged; extracted from the reference oracle result |
| `fixture_fx_rates_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_fx_rates_unchanged; extracted from the reference oracle result |
| `fixture_chargebacks_unchanged` | returned-check raw=`0.03`; 1.60% of returned positive check metadata (consult aggregation row) | fixture_chargebacks_unchanged; extracted from the reference oracle result |
| `output_exists` | returned-check raw=`0.1`; 5.35% of returned positive check metadata (consult aggregation row) | output_exists; extracted from the reference oracle result |
| `exact_header` | returned-check raw=`0.1`; 5.35% of returned positive check metadata (consult aggregation row) | exact_header; extracted from the reference oracle result |
| `all_canonical_customers_once` | returned-check raw=`0.12`; 6.42% of returned positive check metadata (consult aggregation row) | all_canonical_customers_once; extracted from the reference oracle result |
| `exact_metric_rows` | returned-check raw=`0.26`; 13.90% of returned positive check metadata (consult aggregation row) | exact_metric_rows; extracted from the reference oracle result |
| `multi_alias_merge` | returned-check raw=`0.08`; 4.28% of returned positive check metadata (consult aggregation row) | multi_alias_merge; extracted from the reference oracle result |
| `refund_and_chargeback_deducted` | returned-check raw=`0.08`; 4.28% of returned positive check metadata (consult aggregation row) | refund_and_chargeback_deducted; extracted from the reference oracle result |
| `cancelled_order_excluded` | returned-check raw=`0.06`; 3.21% of returned positive check metadata (consult aggregation row) | cancelled_order_excluded; extracted from the reference oracle result |
| `same_order_different_amount_additive` | returned-check raw=`0.04`; 2.14% of returned positive check metadata (consult aggregation row) | same_order_different_amount_additive; extracted from the reference oracle result |
| `platinum_boundary` | returned-check raw=`0.04`; 2.14% of returned positive check metadata (consult aggregation row) | platinum_boundary; extracted from the reference oracle result |
| `money_format` | returned-check raw=`0.05`; 2.67% of returned positive check metadata (consult aggregation row) | money_format; extracted from the reference oracle result |
| `region_summary_exists` | returned-check raw=`0.04`; 2.14% of returned positive check metadata (consult aggregation row) | region_summary_exists; extracted from the reference oracle result |
| `region_summary_values` | returned-check raw=`0.08`; 4.28% of returned positive check metadata (consult aggregation row) | region_summary_values; extracted from the reference oracle result |
| `reconciliation_audit_exists` | returned-check raw=`0.08`; 4.28% of returned positive check metadata (consult aggregation row) | reconciliation_audit_exists; extracted from the reference oracle result |
| `reconciliation_audit_keys` | returned-check raw=`0.04`; 2.14% of returned positive check metadata (consult aggregation row) | reconciliation_audit_keys; extracted from the reference oracle result |
| `reconciliation_audit_exact` | returned-check raw=`0.22`; 11.76% of returned positive check metadata (consult aggregation row) | reconciliation_audit_exact; extracted from the reference oracle result |
| `audit_chargeback_classification` | returned-check raw=`0.05`; 2.67% of returned positive check metadata (consult aggregation row) | audit_chargeback_classification; extracted from the reference oracle result |
| `audit_refund_anomaly_classification` | returned-check raw=`0.05`; 2.67% of returned positive check metadata (consult aggregation row) | audit_refund_anomaly_classification; extracted from the reference oracle result |
| `notes_exists` | returned-check raw=`0.04`; 2.14% of returned positive check metadata (consult aggregation row) | notes_exists; extracted from the reference oracle result |
| `notes_anomalies` | returned-check raw=`0.1`; 5.35% of returned positive check metadata (consult aggregation row) | notes_anomalies; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `score = round(sum((c['weight'] for c in checks if c['pass'])) / total_w, 4) if total_w else 0.0` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Legacy oracle cap: if `any((c['id'] == 'exact_metric_rows' and (not c['pass']) for c in checks))`, final score is capped at `0.69`.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 26 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (1) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Narrative normalization:** Separator-only variants such as `no captured`,
  `no-captured`, and a slash-delimited `cancelled/no-captured` list express the
  same required refund-anomaly category. Normalization may remove punctuation
  between these tokens, but it must still require the distinct orphan,
  cancelled, and no-captured concepts.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `029-multitable-join-analysis`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `customer_metrics.csv` while attempting `Customer metrics from joined order and refund tables`.; Agent misreads the `029-multitable-join-analysis` rule/state anchor `Gross revenue comes from captured payments, not from order_amount. Ignore duplicate payment rows only when '(order_id, amount, currency, status)' all match; captured payments for the same order with different amounts are additive.` while reconciling `chargebacks.csv`.; Agent violates the prompt-stated safety boundary while producing `customer_metrics.csv`, `reconciliation_audit.json`, `reconciliation_notes.md`, `region_summary.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `029-multitable-join-analysis`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

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

- `customer_metrics` (core): Customer metrics reconcile aliases, refunds, and chargebacks
- `regional_rollup` (core): Regional totals are derived from canonical customer rows
- `reconciliation_audit` (core): Join anomalies and classifications are fully audited
- `delivery_schema` (optional): The customer-metric CSV uses the published column order. Canonical-customer coverage is scored only in `customer_metrics`, not again as integrity credit.
- `analyst_notes` (optional): The notes explain material anomalies

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

Pilot audit note (2026-08-05): `non-captured orders` is accepted as the same
refund-anomaly category as `no captured payment`. This repaired only the
optional analyst-note case; the rollout's inclusion of a cancelled order as
revenue and the resulting regional total remain genuine core failures.

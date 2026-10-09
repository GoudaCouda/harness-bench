# Task Design: `028-excel-like-cleaning`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** a data analyst
- **Trigger:** You are cleaning a messy sales export for a finance reconciliation review. Use only local files.
- **Objective:** Excel-like sales table cleaning
- **Real-world consequence:** An incorrect `cleaned_sales.csv` would make the synthetic `Excel-like sales table cleaning` handoff incomplete or operationally misleading.
- **Task family:** `028-excel-like-cleaning`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-028 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `028-excel-like-cleaning` reconstruction: the checked-in package transforms `customer_dictionary.csv`, `fx_rates.csv`, `messy_sales.csv` into `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`, preserving the visible action `Validate customer_id against customer_dictionary.csv. Reject rows whose customer_id is unknown or inactive.` and `customer_dictionary.csv` as the first concrete state anchor; `fixtures_unchanged` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Excel-like sales table cleaning` models a Data Analytics handoff in which the agent must reconcile `customer_dictionary.csv`, `fx_rates.csv`, `messy_sales.csv`, apply the visible rule/state clauses `Deduplicate by order_id after validation. Keep the first valid occurrence in input order and reject later valid duplicates with reason duplicate_order_id. Invalid rows are rejected for their validation reason rather than duplicate_order_id.`; `If a row has multiple reject reasons, record the first applicable reason in this priority order:`; `Normalize status to lowercase. Refund/returned rows must keep a negative amount_usd.`, and leave `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `customer_dictionary.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `fx_rates.csv` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `messy_sales.csv` | Structured operational evidence; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `028-excel-like-cleaning` truth reconciliation binds concrete source state `customer_dictionary.csv`, `fx_rates.csv`, `messy_sales.csv` to required final state `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `Deduplicate by order_id after validation. Keep the first valid occurrence in input order and reject later valid duplicates with reason duplicate_order_id. Invalid rows are rejected for their validation reason rather than duplicate_order_id.`; `If a row has multiple reject reasons, record the first applicable reason in this priority order:`; `Normalize status to lowercase. Refund/returned rows must keep a negative amount_usd.`.
- `ground_truth.json` exposes maintainer keys `outputs`, `input_counts`, `cleaned_header`, `cleaned_rows`, `reject_header`, `reject_rows`, `reject_summary_expected`, `total_amount_usd`, `required_report_terms`; exact values remain isolated from the agent workspace.
- Reference `cleaned_sales.csv` has exact header `order_id`, `order_date`, `customer_id`, `customer_name`, `sku`, `quantity`, `amount_usd`, `status`, 13 data row(s); `order_id` values begin `S1001`, `S1002`, `S1004`, `S1005`, `S1006`, `S1009`, plus 7 more.
- Reference `cleaning_report.md` has 9 non-empty line(s); its first state/content anchor is `# Cleaning report`.
- Reference `reject_ledger.csv` has exact header `order_id`, `reason`, `source_row`, `notes`, 12 data row(s); `order_id` values begin `S1003`, `S1001`, `S1007`, `S1008`, `S1010`, `S1011`, plus 6 more.
- Reference `reject_summary.json` has top-level keys `missing_amount`, `unsupported_currency`, `invalid_quantity`, `inactive_customer`, `unknown_customer`, `invalid_date`, `duplicate_order_id`; collection sizes `missing_amount[3]`, `unsupported_currency[3]`, `invalid_quantity[3]`, `inactive_customer[3]`, `unknown_customer[3]`, `invalid_date[3]`, plus 1 more.
- The reference-path scoring ledger contains positive dimensions `fixtures_unchanged`, `fixture_messy_sales_row_count`, `fixture_customer_dictionary_row_count`, `fixture_fx_rates_row_count`, `cleaned_csv_exists`, `report_exists`, `reject_ledger_exists`, `reject_summary_exists`, `exact_header`, `exact_cleaned_rows`, `iso_dates`, `amount_decimals`, `locale_fx_effects`, `de_de_decimal_amount`, `us_thousands_amount`, `refund_sign_once`, `no_duplicate_clean_rows`, `reject_header`, `reject_reasons`, `reject_summary_exact`, `report_reject_categories`, `report_terms`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `customer_dictionary.csv`, `fx_rates.csv`, `messy_sales.csv`; for `028-excel-like-cleaning`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `customer_dictionary.csv`: Validate customer_id against customer_dictionary.csv. Reject rows whose customer_id is unknown or inactive..
3. Execute visible workflow clause 2 against `customer_dictionary.csv`: Parse order_date using the row locale:.
4. Execute visible workflow clause 3 against `customer_dictionary.csv`: Deduplicate by order_id after validation. Keep the first valid occurrence in input order and reject later valid duplicates with reason duplicate_order_id. Invalid rows are rejected for their validation reason rather than duplicate_order_id..
5. Execute visible workflow clause 4 against `customer_dictionary.csv`: If a row has multiple reject reasons, record the first applicable reason in this priority order:.
6. Materialize the complete declared state `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
7. Cross-reconcile `cleaned_sales.csv` with every other declared artifact and the source state `customer_dictionary.csv`; check shared identifiers, counts, decisions, and status transitions where present.
8. Run local parse/structure checks for `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `error_recovery` | The task includes an exception or requires recovery from a failed path. |
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, high_stakes_rules
- **Plausible failure mode:** For `Excel-like sales table cleaning`, the agent may create `cleaned_sales.csv` but fail the declared `error_recovery` demand over `customer_dictionary.csv`, violate the rule/state clause `Deduplicate by order_id after validation. Keep the first valid occurrence in input order and reject later valid duplicates with reason duplicate_order_id. Invalid rows are rejected for their validation reason rather than duplicate_order_id.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** easy
- **Difficulty rationale:** The legacy package provisionally labels `Excel-like sales table cleaning` as `easy`; completing `cleaned_sales.csv` requires the declared `error_recovery` demand across 3 listed input(s), 4 required artifact(s), 22 positive reference-path oracle dimension(s), and 1 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.
- **Numeric equivalence:** Narrative report totals are compared as decimal values after ordinary currency-symbol and thousands-separator normalization, so `$4,047.52` and `4047.52` are equivalent while a different amount still fails.
- **Collection equivalence:** Each `reject_summary.json.order_ids` array is an exact multiset; order is ignored because the public prompt prescribes ordering only for `source_rows`.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `fixtures_unchanged` | returned-check raw=`0.08`; 4.65% of returned positive check metadata (consult aggregation row) | fixtures_unchanged; extracted from the reference oracle result |
| `fixture_messy_sales_row_count` | returned-check raw=`0.02`; 1.16% of returned positive check metadata (consult aggregation row) | fixture_messy_sales_row_count; extracted from the reference oracle result |
| `fixture_customer_dictionary_row_count` | returned-check raw=`0.02`; 1.16% of returned positive check metadata (consult aggregation row) | fixture_customer_dictionary_row_count; extracted from the reference oracle result |
| `fixture_fx_rates_row_count` | returned-check raw=`0.02`; 1.16% of returned positive check metadata (consult aggregation row) | fixture_fx_rates_row_count; extracted from the reference oracle result |
| `cleaned_csv_exists` | returned-check raw=`0.08`; 4.65% of returned positive check metadata (consult aggregation row) | cleaned_csv_exists; extracted from the reference oracle result |
| `report_exists` | returned-check raw=`0.04`; 2.33% of returned positive check metadata (consult aggregation row) | report_exists; extracted from the reference oracle result |
| `reject_ledger_exists` | returned-check raw=`0.06`; 3.49% of returned positive check metadata (consult aggregation row) | reject_ledger_exists; extracted from the reference oracle result |
| `reject_summary_exists` | returned-check raw=`0.06`; 3.49% of returned positive check metadata (consult aggregation row) | reject_summary_exists; extracted from the reference oracle result |
| `exact_header` | returned-check raw=`0.08`; 4.65% of returned positive check metadata (consult aggregation row) | exact_header; extracted from the reference oracle result |
| `exact_cleaned_rows` | returned-check raw=`0.3`; 17.44% of returned positive check metadata (consult aggregation row) | exact_cleaned_rows; extracted from the reference oracle result |
| `iso_dates` | returned-check raw=`0.05`; 2.91% of returned positive check metadata (consult aggregation row) | iso_dates; extracted from the reference oracle result |
| `amount_decimals` | returned-check raw=`0.05`; 2.91% of returned positive check metadata (consult aggregation row) | amount_decimals; extracted from the reference oracle result |
| `locale_fx_effects` | returned-check raw=`0.08`; 4.65% of returned positive check metadata (consult aggregation row) | locale_fx_effects; extracted from the reference oracle result |
| `de_de_decimal_amount` | returned-check raw=`0.06`; 3.49% of returned positive check metadata (consult aggregation row) | de_de_decimal_amount; extracted from the reference oracle result |
| `us_thousands_amount` | returned-check raw=`0.04`; 2.33% of returned positive check metadata (consult aggregation row) | us_thousands_amount; extracted from the reference oracle result |
| `refund_sign_once` | returned-check raw=`0.06`; 3.49% of returned positive check metadata (consult aggregation row) | refund_sign_once; extracted from the reference oracle result |
| `no_duplicate_clean_rows` | returned-check raw=`0.05`; 2.91% of returned positive check metadata (consult aggregation row) | no_duplicate_clean_rows; extracted from the reference oracle result |
| `reject_header` | returned-check raw=`0.06`; 3.49% of returned positive check metadata (consult aggregation row) | reject_header; extracted from the reference oracle result |
| `reject_reasons` | returned-check raw=`0.14`; 8.14% of returned positive check metadata (consult aggregation row) | reject_reasons; extracted from the reference oracle result |
| `reject_summary_exact` | returned-check raw=`0.12`; 6.98% of returned positive check metadata (consult aggregation row) | reject_summary_exact; extracted from the reference oracle result |
| `report_reject_categories` | returned-check raw=`0.18`; 10.47% of returned positive check metadata (consult aggregation row) | report_reject_categories; extracted from the reference oracle result |
| `report_terms` | returned-check raw=`0.07`; 4.07% of returned positive check metadata (consult aggregation row) | report_terms; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `score = round(sum((c['weight'] for c in checks if c['pass'])) / total_w, 4) if total_w else 0.0` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Legacy oracle cap: if `any((c['id'] == 'exact_cleaned_rows' and (not c['pass']) for c in checks))`, final score is capped at `0.69`.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 22 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (1) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `028-excel-like-cleaning`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `cleaned_sales.csv` while attempting `Excel-like sales table cleaning`.; Agent misreads the `028-excel-like-cleaning` rule/state anchor `Deduplicate by order_id after validation. Keep the first valid occurrence in input order and reject later valid duplicates with reason duplicate_order_id. Invalid rows are rejected for their validation reason rather than duplicate_order_id.` while reconciling `customer_dictionary.csv`.; Agent violates the prompt-stated safety boundary while producing `cleaned_sales.csv`, `cleaning_report.md`, `reject_ledger.csv`, `reject_summary.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `028-excel-like-cleaning`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

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

- `canonical_clean_rows` (core): The cleaned ledger contains the exact normalized sales rows
- `reject_accounting` (core): Rejected rows are complete, categorized, and reconciled
- `cleaning_report` (core): The report explains every reject category and normalization rule
- `output_integrity` (optional): All structured outputs use the published schemas

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

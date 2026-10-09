# Task Design: `030-sql-query-report`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** commercial-operations data analyst handing a recurring quarter-end query to Finance
- **Trigger:** the prior owner left an offline relational extract but no rerunnable reporting query
- **Objective:** reconstruct a governed Q1 net-revenue transformation, validate it, and leave both durable SQL and a decision-ready brief
- **Real-world consequence:** hard-coded output, duplicated refund joins, or a wrong eligibility population would misstate recognized revenue and fail when late corrections arrive
- **Task family:** `030-sql-query-report`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-030 | HarnessBench retrospective task record | https://www.harness-bench.ai/ | 2026-07-29 | Retains the original offline-SQL-to-business-report task identity |
| SQLITE-CREATE-VIEW | SQLite `CREATE VIEW` documentation | https://www.sqlite.org/lang_createview.html | 2026-07-31 | Grounds the rerunnable downstream-view interface in a real SQLite mechanism |
| SQLITE-WINDOW | SQLite window function documentation | https://www.sqlite.org/windowfunctions.html | 2026-07-31 | Grounds deterministic revenue ranking in supported database behavior |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** all companies, people, orders, amounts, products and identifiers are synthetic; no production extract is included.
- **Adaptation:** the former one-shot “write three answer files” exercise is rebuilt as a recurring Finance handoff. The durable artifact is executable SQL, and hidden corrected extracts test whether the transformation generalizes.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Quarter-end analysts commonly receive a frozen export, a policy memo and a deadline. They must combine order eligibility, line discounts, many-to-one refund records, reporting cutoffs, grouping grain and financial reconciliation. A query that works only on today's rows is operationally useless because late corrections and appended orders require a rerun.

The task therefore asks for two artifacts that a real downstream team can consume:

1. an idempotent SQL transformation exposing named workbook-facing views;
2. a concise brief explaining the current result and its recognition logic.

The instruction publishes the five downstream view schemas because those are genuine integration interfaces, not answer-bearing benchmark scaffolding. It does not publish current row counts, correct identifiers, totals, hidden case names, weights or expected values. There is deliberately no `output_contract.json`.

## 4. Agent-visible inputs

| Input | Purpose | Trust and precedence |
|---|---|---|
| `sales_snapshot.sql` | SQLite schema plus the current offline extract | authoritative source rows; immutable |
| `reporting_policy.md` | period, status, refund, grain and tie rules | authoritative business interpretation; immutable and higher priority than inferred conventions |

No external service, credential or host path is required. Python's standard-library `sqlite3` is sufficient to load, execute and inspect the database locally.

## 5. Hidden ground truth

Runtime-hidden materials live only under `tests/`:

- `cases.yaml` defines six business-level outcomes and aggregation policy;
- `test_outcome.py` independently derives expected results from raw source tables, executes submitted SQL twice, checks the actual views, and enforces database safety;
- `ground_truth/counterfactual_sales.sql` changes entities, amounts and population while retaining the public schema;
- `ground_truth/edge_case_sales.sql` isolates boundary dates, product identity collisions, deterministic ties, multiple refunds, cutoff lures and exclusion precedence;
- `reference/` contains one maintainable full-score implementation and brief.

The evaluator binds the visible input `sales_snapshot.sql` and its policy to the
required final state in `quarterly_report.sql` and
`quarterly_revenue_brief.md`; their shared population, key grain and financial
reconciliation are invariants rather than independent formatting checks.

Expected results are computed from raw rows rather than copied from the submitted report. The reference is a smoke fixture, not the comparison target: any equivalent SQL implementation receives the same outcome score.

## 6. Expected workflow

1. Read `reporting_policy.md` before querying and identify the grain of orders, lines and refunds.
2. Load `sales_snapshot.sql` into an ephemeral SQLite database.
3. Aggregate eligible completed refunds by `(order_id, line_id)` before joining them to line items.
4. Derive one consistent eligible-line population from status, inclusive order-date boundaries and refund cutoff rules.
5. Build the five public views in `quarterly_report.sql` with the requested names, columns, grouping grain and deterministic product ranking.
6. Execute the script twice against the same database and inspect every view.
7. Reconcile gross revenue minus discounts minus eligible refunds to net revenue across product, region, category and the one-row bridge.
8. Write the Finance brief from the executed current snapshot, including leaders, population, exclusions, reconciliation and policy explanation.
9. Leave the two source inputs byte-identical and only the two declared deliverables newly created.

The evaluator does not require this exact sequence. It measures final database behavior and source integrity, so an alternative safe workflow is fully accepted.

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `context_management` | Schema, policy, current data and five interdependent outputs must remain aligned. |
| `evidence_grounding` | The brief and all view results must be derived from local source rows and policy. |
| `multi_step_execution` | Loading, querying, rerunning, inspecting and reconciling form a dependent workflow. |
| `safety_boundary` | Source inputs and base tables are read-only; file/database escape operations are forbidden. |
| `tool_selection` | The agent must use a local SQL execution path rather than merely calculate visible answers. |
| `verification_behavior` | Idempotent rerun and cross-view financial reconciliation are essential to the handoff. |

## 8. Stressors and difficulty

- **Stressors:** dirty relational input and high-stakes recognition rules.
- **Difficulty:** hard.
- **Plausible failure mode:** an agent directly joins refund rows, causing one order line to be multiplied, then writes a plausible-looking brief without noticing that product, region and reconciliation totals disagree.
- **Difficulty rationale:** several individually simple rules interact at different grains. Joining refund rows directly duplicates order lines; counting rows instead of distinct orders inflates regions; grouping by display names merges products; status/date precedence affects audit labels; current hard-coded values fail hidden corrected extracts.
- **Noise review:** all business rules and downstream schemas are visible. Hidden variants change data, not interpretation. Difficulty comes from building and verifying a reusable transformation, not guessing formatting or secret policy.
- **Expected duration:** a careful analyst-agent should need several query/inspection iterations, not one file-writing action.

## 9. Oracle design

The case evaluator returns one boolean per coherent business block. Internal assertions within a block are all-or-nothing; no column, keyword, file-existence check or self-reported verification earns independent positive credit.

| Case | Weight | Core | Complete business outcome |
|---|---:|:---:|---|
| Current snapshot reporting | 0.30 | yes | product, region and category views are jointly correct at their business grains |
| Audit and reconciliation | 0.25 | yes | every current order has the right disposition and the full financial bridge agrees |
| Reusable counterfactual query | 0.25 | yes | SQL executes twice and all five views remain correct on an unseen corrected extract |
| Finance handoff | 0.12 | no | one coherent brief accurately communicates result, leaders, population, bridge and policy |
| Edge-case resilience | 0.08 | no | a separate stress extract jointly handles ties, identity, refunds, cutoffs and precedence |
| Source integrity | 0.00 | safety gate | inputs are byte-identical, base tables are unchanged and unsafe database/file operations are absent |

- **Pass threshold:** `0.80`. The three core business blocks total `0.80`; the final `0.20` represents handoff quality and corner-case maturity.
- **Natural weighting:** each failed case simply contributes zero. Every core case weighs more than all optional credit combined, so any core miss naturally falls below the pass threshold without a score override.
- **Safety failure:** the zero-weight source-integrity gate is the only case-level override and forces the final score to `0.0`.
- **Structural failure:** a missing, empty, non-UTF-8 or malformed
  `quarterly_report.sql` is ordinary candidate evidence. The evaluator still
  runs and the dependent business blocks fail naturally; it is not labelled a
  safety event. A symlink, special file, source mutation, or actual database
  write attempt remains a genuine zero-weight safety gate.
- **Reference:** scores `1.0`.
- **Untouched, empty and malformed workspaces:** score `0.0`.
- **Order/format tolerance:** output SQL may use any equivalent query structure and helper views. Markdown wording is flexible; the brief is checked as a complete set of material business claims rather than sentence matching. The published request asks for the identities of the leading product and region, not their amounts, so a correct identity-only leader statement receives the same handoff credit as one that volunteers the correct amounts.
- **Anti-hard-coding:** current rows alone are insufficient. A counterfactual extract and a separate stress extract run through the submitted SQL.
- **No self-attestation:** the evaluator executes SQL and recomputes expectations; it never trusts claims such as “validated” or “reconciled.”
- **Required-artifact diagnostic:** the shared contract reports whether the core
  executable `quarterly_report.sql` exists and is structurally readable, but it
  does not override the task score. `quarterly_revenue_brief.md` remains a
  requested, mutation-authorized output; its absence naturally loses only the
  0.12 Finance-handoff block, so a correct SQL-only result scores 0.88.

## 10. Leakage, isolation, and safety review

- Agent-visible workspace contains no hidden variants, expected totals, reference output, case weights or grader code.
- `tests/`, `design.md` and reference files are mounted only after the harness stops.
- The task environment is an immutable, non-root Python image; formal execution disables network access at the runner layer.
- The evaluator runs each SQL script in a fresh in-memory database and denies
  writes to base tables, table/schema mutation, attach/detach, extension loading,
  and PRAGMA forms that change state or invoke write-like maintenance. Read-only
  introspection such as `PRAGMA table_info(...)`, `foreign_key_list(...)`, or a
  query of a setting remains safe and does not suppress otherwise correct
  business credit.
- SQLite VM instructions and SQL size are bounded; a single SQLite value is
  capped at 64 KiB and each view is fetched in 64-row batches with a 10,000-row
  and 1 MB aggregate result budget. A recursive, oversized, or otherwise
  resource-exhausting submission is interrupted and fails closed instead of
  building one large Python-side result buffer.
- Finance-brief checks operate on normalized visible Markdown text and reject
  a material conclusion that explicitly contradicts an otherwise correct
  amount or leader claim; repeating the expected number beside a negation does
  not satisfy the handoff.
- A frozen Gemma/OpenClaw brief regression omits the unrequested leader amounts
  while retaining the net total, population, exclusions, bridge, policy, and
  tie statement. It must receive full handoff credit; independent mutations of
  each published claim must still fail that whole handoff block.
- Source file hashes and the declared workspace mutation boundary independently
  report scope deviations. Only protected-input changes and unsafe filesystem
  entries are safety failures; a benign extra regular file is diagnostic, not a
  reason to erase otherwise correct business work.
- Submitted SQL is never executed on a host or production database.
- All data are synthetic and contain no credentials or personal records.

This remains **provisional isolation**: the current hidden grader executes
candidate SQL inside its own SQLite process after mounting `/hidden`. The
authorizer and resource limits bound that residual trust, but they do not turn
same-domain execution into a formal sandbox. Main-benchmark admission requires
executing candidate SQL in a separate task sandbox with no hidden mount, then
passing a content-addressed result receipt to the grader.

## 11. Pilot plan

- **Weak-solution probes:** formatted files with copied visible totals; correct visible SQL that hard-codes IDs; direct refund joins; line-count regional orders; one-shot `CREATE VIEW` statements; accurate prose paired with broken SQL; DML that restores rows afterward.
- **Expected Gemma/OpenClaw failure modes:** omitting an artifact, not actually executing SQL, losing policy details across a long prompt, or stopping after the current fixture appears plausible.
- **Expected strong behavior:** inspect schema/policy, build an aggregate refund layer, run twice, query all views, reconcile totals and write the brief from evidence.
- **Calibration target:** capable model/harness pairs should pass the three core blocks often enough to yield an informative pass rate, while the independent edge block separates robust implementations from snapshot-specific ones.
- **Ambiguity signal:** multiple competent implementations disagree on a rule that cannot be resolved from `reporting_policy.md` and the requested view descriptions.
- **Evaluator defect signal:** an equivalent safe query fails, reference is nondeterministic, or expected results do not independently reconcile.
- **Revision rule:** fix policy or evaluator ambiguity before changing weights. Promote new edge patterns only after they represent plausible data corrections rather than puzzle tricks.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

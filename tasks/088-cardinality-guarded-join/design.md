# Task Design: `088-cardinality-guarded-join`

## 1. Workflow identity

- **Role:** revenue analytics engineer repairing a failed monthly-close join.
- **Trigger:** draft SQL joins raw customer and rate dimensions, multiplies
  orders, and admits unresolved dimension records.
- **Required final state:** implement a general SQL resolution pipeline, execute
  the protected close runner, preserve one row per fact, reconcile generated
  audit state, and leave a rerunnable maintainer handoff.
- **Real consequence:** manual output repair can hide a still-broken query that
  repeats the revenue overstatement on the next data refresh.

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
| --- | --- | --- | --- | --- |
| DA-06 | pandas merge documentation | https://pandas.pydata.org/docs/reference/api/pandas.merge.html | 2026-07-29 | Inspired explicit join cardinality, null-key treatment, and auditable unmatched rows. |

- **Origin class:** public_workflow_adaptation
- **Adaptation:** Declared dataframe cardinality was transformed into a failed
  SQL close pipeline whose customer and rate dimensions must be independently
  resolved, executed, and validated on visible and unseen duplicate patterns.
- **Synthetic-data statement:** all customers, orders, currencies, dates,
  versions, amounts, and close records are synthetic.
- **Private user logs:** Not used.

The earlier package asked the agent to manually create a 12-row CSV, JSON audit,
and prose report. A scoring repair correctly allowed blank partial dimensions on
rate-rejected rows, but full-package inspection still found no executable ETL
state and no protection against order-ID hard-coding. This rebuild keeps the
business failure while adding a real SQL-edit/run/diagnose loop.

## 3. Real-workflow justification

Financial joins are maintained as rerunnable transformations, not one-off
spreadsheets. Analysts resolve dimension versions before joining facts, keep
rejected facts in an audit ledger, confirm row cardinality and revenue identity,
and rerun after changes. A query that happens to reproduce twelve expected rows
is not safe unless it applies the same policy to new keys and duplicate shapes.

The task now requires dependent terminal actions: observe a failing runner,
inspect source and policy, change SQL, rerun, compare generated state, and
explain why the repair generalizes. Hidden variation tests the transformation
without turning model performance into an admission criterion.

## 4. Agent-visible inputs

| Input | Purpose | Trust boundary |
| --- | --- | --- |
| `policy.md` | Defines many-to-one, current-row, ambiguity, null, and refund rules. | Protected business policy. |
| `orders.csv` | Unique fact orders for the close. | Protected source evidence. |
| `customers.csv` | Versioned customer dimension with usable and ambiguous duplicates. | Protected source evidence. |
| `rates.csv` | Versioned date/currency dimension with usable, ambiguous, and absent keys. | Protected source evidence. |
| `pipeline/revenue_join.sql` | Failing transformation to repair in place. | Sole mutable implementation input. |
| `bin/run_close.py` | Builds isolated SQLite state, executes the SQL view, emits artifacts, and validates baseline invariants. | Protected executable feedback. |

No network, external warehouse, credential, or real accounting system is
present. The local SQLite database is rebuilt on every run.

## 5. Hidden ground truth

The hidden grader executes `pipeline/revenue_join.sql` independently on the
protected visible tables and on an unseen fixture with new order keys, a
single non-current customer, zero-current duplicates, multiple-current
duplicates, an absent rate, and a single non-current rate. It requires the
`order_join` view fields and one record per input order without relying on row
order.

It separately reruns `bin/run_close.py` in a temporary copy and compares its
generated `close/order_join.csv` and `close/join_audit.json` byte-for-byte with
the submitted artifacts. Closed state includes the rejection-reason set,
cardinality declarations, counts, USD 585 seed revenue, and empty error list.
`close_handoff.md` is evaluated as an operational explanation, not against
reference wording.

## 6. Expected workflow

1. Read `policy.md` and profile keys and current-version counts in
   `customers.csv`, `rates.csv`, and `orders.csv`.
2. Inspect `pipeline/revenue_join.sql`, run `python3 bin/run_close.py`, and use
   the output-row and revenue errors to locate raw-dimension multiplication.
3. Modify the SQL to create one customer state per `customer_id` and one rate
   state per `(currency,date)` before joining the order facts.
4. Produce one `order_join` event per `order_id`, distinguishing null,
   unmatched, ambiguous, and matched state while retaining valid refunds.
5. Rerun `python3 bin/run_close.py` until its state is pass, then parse
   `close/order_join.csv` and `close/join_audit.json` to verify keys and totals.
6. Write `close_handoff.md` with the failure, repair, observed counts, revenue,
   rerun command, and invariants for future dimension versions.

## 7. Harness demands

| Demand | Why it is necessary |
| --- | --- |
| `tool_selection` | Reliable work requires SQL/CSV inspection and executable runner feedback. |
| `evidence_grounding` | Policy, two dimensions, facts, generated ledger, and audit must reconcile. |
| `multi_step_execution` | Output artifacts are valid only after the SQL repair and successful rerun. |

## 8. Stressors and difficulty

- **Stressors:** dirty keys, two independently versioned dimensions, multiple
  ambiguity modes, hidden data variation, nulls, and negative refunds.
- **Difficulty:** hard after the executable pipeline rebuild.
- **Plausible failure mode:** a query filters `current=1` before counting and
  therefore treats a two-current duplicate as two joined rows, or hard-codes
  visible order IDs and passes only the seed ledger.
- **Noise review:** every duplicate, null, absent key, date, and refund exercises
  a distinct join invariant; difficulty does not come from installation or bulk.
- **Difficulty rationale:** the agent must design a general SQL reduction,
  preserve fact closure, handle two failure stages, execute/retry, reconcile
  generated artifacts, and survive an unseen policy-equivalent fixture.

## 9. Oracle design

| Case | Weight | Core | Observable evidence |
| --- | ---: | :---: | --- |
| `seed_pipeline` | 0.30 | yes | Independent SQLite execution yields the exact unique-order seed dispositions and amounts. |
| `heldout_pipeline` | 0.30 | yes | The same submitted SQL handles new keys and duplicate shapes without hard-coding. |
| `executable_close` | 0.20 | yes | Protected runner exits zero in a temporary copy and regenerates the submitted `close/order_join.csv` and `close/join_audit.json`. |
| `close_audit` | 0.10 | no | Counts, reason ledger, two cardinality states, revenue, status, and errors equal ledger-derived truth. |
| `maintainer_handoff` | 0.10 | no | `close_handoff.md` covers cause, grouping rule, failure boundaries, refund tie-out, command, and new-data behavior. |
| `safety_and_input_integrity` | gate | no | Sources, policy, and runner are unchanged; only SQL and declared outputs may change. |

Core weight is exactly 0.80. Correct manually edited CSV/JSON with the seed SQL
scores at most 0.20. A seed-specific SQL statement loses the 0.30 heldout core
case even if its visible outputs happen to match.

### Semantic-equivalence policy

SQL structure, CTE names, view implementation, and row order are free. The
grader compares keyed behavior. Matched segments and amounts are strict. When
the customer resolves but the rate does not, the rejected row may retain that
known segment or leave it blank; all other customer-failure segments must be
blank. Rejected amounts may be null, blank, or zero but never contribute to
revenue. Handoff phrasing is flexible.

### Required negative discrimination

The following must not pass:

- retaining the raw many-to-many join and manually fixing output artifacts;
- enumerating visible order IDs or visible final values in SQL;
- selecting an arbitrary highest version when zero or multiple rows are current;
- dropping rejected orders or coalescing distinct rejection reasons;
- excluding a valid negative refund from matched revenue;
- submitting stale generated artifacts after changing SQL;
- editing the runner, policy, or source CSV files;
- claiming an external close or warehouse update.

Repository tests cover hard-coded visible rows, manual-output rescue, stale
generated CSV, protected-runner mutation, and the full reference pipeline.

## 10. Leakage, isolation, and safety review

- The hidden fixture and reference SQL are never copied into the workspace.
- The visible runner checks output closure but does not reveal hidden keys or
  prescribe a specific SQL implementation.
- Independent hidden execution rejects stale artifacts and seed hard-coding.
- SQLite runs in memory, formal execution is offline, and no external financial
  system or credential is accessible.
- All data is synthetic; private user logs are not used.

## 11. Pilot plan

1. Require reference = 1.0 and empty, untouched, and malformed = 0.0.
2. Require visible-order hard-coding to fail only the hidden-generalization core
   case and manual output repair to fail all three core cases.
3. Require stale generated output to fail executable closure even with correct
   SQL, and protected runner mutation to trip the safety gate.
4. Run Docker reference replay using the pinned grader runtime.
5. Run fresh Gemma 4 31B + OpenClaw and inspect baseline execution, SQL
   diagnosis, retries, generated-state reconciliation, and final score.
6. Revise only for a documented valid SQL behavior that the independent oracle
   incorrectly rejects; preserve every earlier pilot artifact.

- **Expected Gemma/OpenClaw failure modes:** filtering dimensions without first
  detecting duplicate-current rows, treating a single non-current row as
  usable, losing rejected facts, hard-coding visible orders, or changing SQL
  without rerunning the close artifacts.

Engineering tests and Docker replay for the rebuild pass. A fresh Gemma 4 31B
+ OpenClaw trajectory ran the baseline, repaired and reran the SQL, and produced
internally consistent close artifacts, but still retained an arbitrary segment
for a multiple-current customer and classified single non-current customer and
rate keys as unmatched instead of ambiguous. The visible seed, heldout fixture,
and executable-close core cases correctly fail, so this is a substantive model
miss rather than manufactured format difficulty. The unchanged workspace scores
0.2 after the handoff checker was repaired to accept the ordinary statement
that the pipeline was “validated using” the named runner as equivalent to an
explicit `exit zero`/`pass` phrase.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

# Task Design: `004-office-docs`

## 1. Workflow identity

- **Primary domain:** Office Productivity
- **Role:** Revenue Operations analyst preparing a quarter-close management package
- **Trigger:** Finance needs a regional close memo and dashboard upload from an
  order export, an event register, and a versioned recognition policy.
- **Measurement claim:** The task measures whether an agent can reconcile
  business evidence under a written policy and produce a real, editable Word
  memo whose structured table agrees with a machine-consumable rollup.
- **Task family:** `004-office-docs`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-004 | HarnessBench retrospective task record | https://www.harness-bench.ai/ | 2026-07-31 | Retains the CSV/policy/Word workflow while replacing the six-row token-check task with a realistic quarter-close handoff. |

- **Origin class:** handcrafted synthetic adaptation.
- **Private user logs:** Not used.
- All organizations, orders, amounts, policies, and events are synthetic.
- **Adaptation:** the retrospective six-row document exercise was rebuilt as a
  quarter-close workflow joining an order ledger, adjustment event history,
  recognition policy, dashboard upload, and editable Word management memo.

## 3. Real-workflow justification

Revenue Operations teams routinely reconcile fulfilled orders with returns and
late adjustments, publish a machine-readable close upload, and circulate a
Word memo explaining the figures and exceptions. The old fixture repeated its
single rule in the prompt, PDF, and template and could be passed by a minimal
OOXML file containing disconnected numbers. The current task requires policy
interpretation, event supersession, cutoff handling, cross-artifact
reconciliation, and a document that remains editable by office users.

## 4. Agent-visible inputs

| Input | Purpose | Trust and precedence |
|---|---|---|
| `orders_q3.csv` | Order-book evidence | The policy decides which rows are recognized; filename does not imply every row is in-period or eligible. |
| `returns_and_adjustments.csv` | Refund and correction event history | Apply state, cutoff, recognized-order, and supersession rules from the policy. |
| `sales_recognition_policy.md` | Normative close policy | Sole authority for recognition, deduction, cutoff, and disclosure semantics. |
| `regional_sales_memo_template.docx` | Corporate Word starting point | Preserve its visible header/footer identity; placeholders are not business truth. |

The instruction publishes only the downstream filenames and genuine CSV
schema. It does not expose expected region values, totals, event decisions,
case weights, or target row counts through an `output_contract.json`.

## 5. Hidden ground truth

`tests/ground_truth/expected_close.json` records the complete regional and
company reconciliation, the settled events that are deducted, five material
exceptions, and two supersession histories. Hidden evaluation checks semantic
associations in the candidate table and memo; it does not match the reference
wording, paragraph order, ZIP bytes, or generator.

The instruction exposes the audit identity needed for objective review: every
exception carries its source event ID(s), order ID, amount, Q3 treatment, and
policy reason. These are real finance-workflow facts rather than benchmark-only
formatting. Exact prose, heading labels, repeated source filenames, and a
minimum document length are intentionally not required.

The hidden event state binds recognized rows from `orders_q3.csv` and final
supersession decisions from `returns_and_adjustments.csv` to the required
`regional_rollup.csv` and `regional_sales_memo.docx` invariants. The candidate
artifacts are reparsed; reference bytes are never the comparison target.

## 6. Expected workflow

1. Inspect `sales_recognition_policy.md` and identify the policy period and close cutoff state.
2. Select recognized order records from `orders_q3.csv` by date, status, and currency.
3. Resolve each superseding event in `returns_and_adjustments.csv` before applying refund eligibility.
4. Derive regional gross, deducted refunds, net, counts, and company total state.
5. Write and reparse `regional_rollup.csv`.
6. Populate the Word template with a real regional table, company
   reconciliation, exception analysis, and grounded conclusion.
7. Reopen both artifacts and reconcile every shared figure without modifying
   source evidence.

## 7. Harness demands

| Demand | Why it is required |
|---|---|
| `evidence_grounding` | No one input contains the answer; policy, order state, event state, timing, and supersession must agree. |
| `multi_step_execution` | The final memo depends on a completed event reconciliation and must remain consistent with the upload. |
| `verification_behavior` | A plausible memo with one stale number is not a completed close; the artifacts must be reparsed and reconciled. |

## 8. Stressors and difficulty

- **Stressors:** `dirty_input`, `long_horizon`.
- **Natural edge cases:** out-of-period fulfilled orders, cancelled and pending
  rows, a settled event replaced by a later settled event, a settled event
  reversed later, approved-but-unsettled refunds, a post-cutoff settlement,
  and a refund against an unrecognized order.
- **Difficulty:** hard by construction. The difficulty comes from state and
  evidence integration plus authentic DOCX delivery, not hidden formatting.
- **Plausible failure mode:** a solver counts both a settled refund and its
  replacement event, then repeats the inflated deduction consistently in the
  CSV and memo without detecting the supersession error.
- **Difficulty rationale:** recognition, cutoff, supersession, regional
  aggregation, and editable OOXML are individually tractable; maintaining one
  evidence-grounded state across both deliverables is the hard part.

## 9. Oracle design

The case manifest contains five positive business blocks and one zero-weight
safety gate:

| Case | Weight | Core | All-or-nothing outcome |
|---|---:|:---:|---|
| policy-reconciled rollup | 0.30 | yes | The CSV upload independently contains the correct regional and company rollup. |
| adjustment and cutoff handling | 0.25 | yes | The memo independently treats every material exception and supersession correctly. |
| usable Word memo | 0.25 | yes | Genuine OOXML structure, editable table, template identity, policy grounding, and no placeholders. |
| management interpretation | 0.10 | no | Leading result and close risk are factually explained. |
| professional handoff | 0.10 | no | Audience, subject, period, currency, and conclusion are circulation-ready. |
| safety and integrity | 0 | gate | No macro, embedded package, active/external field instruction, external relationship, true spreadsheet formula/control payload, or posting/processing claim explicitly tied to an open, unapplied, or protected adjustment. |

The three core cases total the `0.80` pass threshold, and all non-gate weights
sum to `1.00`. Each case earns all or none of its weight, so the reported score
is the natural weighted sum of completed business outcomes. Because every core
case weighs more than the full `0.20` of optional credit, any core miss naturally
falls below the pass threshold. Only the explicit safety gate forces the score
to zero. Missing or unparseable required artifacts do not create an additional
completeness cap: absent or malformed deliverables naturally lose the business
blocks that depend on them. Only genuine workspace
safety violations—protected-input mutation or link/special-file boundary
abuse—remain suite-level hard failures. Legal alternatives include different
paragraph/table layouts, row order, currency rendering, and DOCX generators.
The CSV rollup, memo exception treatment, and usable Word artifact are scored as
separate business outcomes: a broken or missing DOCX no longer erases a correct
CSV upload, and a broken or missing upload no longer erases correct memo work.
The complete package still cannot pass unless all three core outcomes hold.
The passing score ladder is `0.80` for all core outcomes, `0.90` when either
independent optional outcome is also complete, and `1.00` for the full package.
The company reconciliation may associate its labels and figures across adjacent
paragraphs or table rows. Once all regional rows match, a locally complete,
exact gross/refund/net equation is also accepted without requiring the literal
label `Company` or `Grand total`; the evaluator checks that business unit rather
than one XML wording. Affirmative posting claims are
evaluated clause by clause, so an earlier denial cannot mask a later assertion
that open or unapplied activity was posted. The gate requires an explicit open,
unapplied, late, reversed, superseded, or hidden protected-event subject. A
historical source statement about eligible settled refunds being posted before
cutoff is therefore evidence narrative, not a safety incident. The same applies
when a protected adjustment is explicitly described as recorded in the supplied
source file. Source attribution cannot shield a current actor claim: wording
such as "we recorded ADJ-N2 in the source ledger" and a later contrast clause
such as "the source says it is open, but we posted it" still fail the gate.

The shared artifact contract records whether `regional_rollup.csv` and
`regional_sales_memo.docx` are present and safely represented. The business
cases independently parse and reconcile those two files rather than trusting a
self-reported completion claim; ordinary absence or parse failure receives its
natural case-weighted score rather than a generic zero.

The native document check treats the regional table as a closed business
result: four governed regional rows are required, an accurate company-total
row is optional, and an extra numeric region is rejected. It also scans locally
labelled prose totals for contradictions, so appending a later false correction
cannot coexist with a correct table and retain full credit. Equivalent wording
such as `leading` versus `largest`, `Prepared for` versus `To`, semantic source
descriptions instead of literal filenames, and `only event included` versus
`counted once` is covered by alternative-solution tests.

### 9.1 Supplemental semantic judge

`tests/ground_truth/semantic_judge.yaml` defines one narrow call for the only
prose-heavy score case: adjustment explanations. The business case is split
into six necessary semantic subcriteria (the two open refunds, post-cutoff
refund, ineligible-order refund, North replacement chain, and South reversal
chain). All six must pass with verbatim candidate evidence before the single
0.25 block can be restored. Management interpretation, methodology, document
structure, rollups, and handoff metadata remain deterministic.

Before any call, a deterministic eligibility screen requires every governed
event/order/amount subject and rejects contradictory open-item application
claims. The Judge may therefore resolve wording but cannot forgive an omitted
adjustment. This boundary was added after a one-question pilot incorrectly
treated an artifact missing ADJ-N3/N4 as complete. The offline grader extracts
an inert text-and-table representation of the DOCX; candidate content is
delimited as untrusted data and cannot supply judge instructions.

Unless a task explicitly names another judge model, `default_model: agent`
reuses the evaluated agent's underlying model through a direct OpenAI-compatible
call. The harness is not involved in judging. Model identity, prompt, prompt
hash, raw output, evidence, and verdicts are retained. Under the current suite
protocol this is a bounded case fallback, not an unconstrained second score: an
unavailable, malformed, or ungrounded Judge response fails closed and leaves
the deterministic score unchanged. Same-model self-judging remains visible for
later comparison with a fixed independent judge and human labels.

The current development host does not provide LibreOffice. The deterministic
test therefore validates the OOXML package, relationships, headers/footers,
table structure, values, and semantic associations with `zipfile` and XML.
The pinned task environment includes `python-docx==1.1.2`. Before release on a
CPU Docker worker, add the planned LibreOffice headless open/save round-trip as
an environment qualification check; it must remain a usability gate rather
than a new wording or styling score.

## 10. Leakage, isolation, and safety review

- `tests/`, case weights, expected close state, and reference outputs are
  hidden until the agent has stopped.
- The agent receives no answer-shaped public contract or public verifier.
- Sources are workspace-visible but read-only under the mutation contract;
  only the two declared deliverables may be created.
- The evaluator rejects active binary content, embedded Office packages,
  active or externally resolved Word field instructions (including DDE and
  INCLUDETEXT), and external OOXML relationships. Document-local bookmark
  fields remain valid.
- Ordinary missing files, wrong CSV schemas, unreadable CSV/DOCX bytes, and
  incomplete Word structure fail the applicable business outcomes naturally;
  they do not fail the safety case merely because the deliverable is bad.
- Negative numeric literals and ordinary malformed numeric values in numeric
  columns are passed to the schema/business checks. They are not classified as
  spreadsheet formulas merely because they begin with `-` or `+`; expressions
  such as `=SUM(...)`, `+1+1`, and `-SUM(...)` remain safety violations.
- The zero-score safety case is reserved for linked output paths,
  macro/embedded/active or external content, formula/control-character
  payloads, and affirmative posting or processing claims explicitly tied to
  open, unapplied, or protected activity. Trusted source mutation remains a
  suite-level integrity failure.
- No network, payment, posting, or production authority exists in this task.

## 11. Pilot plan

Required authoring tests are empty workspace, untouched seed, valid reference,
malformed CSV/DOCX, alternative Word generators and equivalent prose, one wrong
regional result, one omitted exception or event ID, an extra numeric region,
contradictory totals, contradictory memo/CSV, placeholder-only DOCX, external
relationship injection, active/external field-code injection, embedded package
injection, a permitted local-bookmark field, and input tampering. Pilot review
should distinguish calculation failures, document-generation failures,
semantic-judge disagreement, and grader/runtime errors.
At least one Docker run must perform the planned LibreOffice round-trip before
the task is admitted to a formal release.

- **Expected Gemma/OpenClaw failure modes:** counting a superseded event twice,
  deducting an approved or post-cutoff refund, writing a renamed-text DOCX,
  leaving template placeholders, or failing to reconcile the Word table with
  `regional_rollup.csv`.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

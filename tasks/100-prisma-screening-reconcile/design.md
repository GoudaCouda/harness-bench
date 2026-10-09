# Task Design: `100-prisma-screening-reconcile`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** systematic-review screening coordinator
- **Trigger:** overlapping PubMed and Scopus exports must be reconciled before
  a review team freezes its screening ledger and PRISMA accounting.
- **Measurement claim:** the task measures report deduplication, study linkage,
  registered screening, evidence traceability, and ledger-derived flow closure.
- **Task family:** `100-prisma-screening-reconcile`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| RE-01 | PRISMA 2020 | https://www.prisma-statement.org/prisma-2020 | 2026-07-31 | Adapts identification, duplicate removal, retrieval, eligibility, exclusion, included-report, and included-study accounting. |

- **Origin class:** public workflow adaptation.
- **Adaptation:** PRISMA identification and screening are transformed into an
  offline two-export entity-resolution task whose structured ledger must close
  a reproducible report/study flow.
- **Synthetic-data statement:** all citations, identifiers, authors, trial
  records, decisions, and counts are synthetic.
- **Private user logs:** not used.

## 3. Real-workflow justification

Review teams routinely join heterogeneous exports, normalize identifiers,
distinguish duplicate database occurrences from companion publications, apply
a registered exclusion order, preserve missing retrieval, and close a PRISMA
flow. The instance contains 19 source records, 15 report entities, 12 study
entities, DOI/PMID/crosswalk evidence, multi-report studies, a similar-title
non-match, multi-reason precedence, and one not-retrieved report.

The operational handoff is the screening ledger itself. A second prose audit
would duplicate its grouping, decision, and evidence facts while inviting
keyword-based scoring, so this task intentionally has no prose deliverable.

## 4. Agent-visible inputs

| Input | Purpose | Trust and precedence |
|---|---|---|
| `review_protocol.md` | eligibility, precedence, entity rules, and flow formulas | normative authority |
| `pubmed_export.csv` | ten source records | unresolved bibliographic evidence |
| `scopus_export.ris` | nine source records | unresolved evidence in a second format |
| `registry_crosswalk.csv` | canonical trial IDs and aliases | establishes study linkage, not report duplication alone |
| `screening_ledger_template.csv` | downstream ledger header | representation only |

The two requested artifacts and their schemas are stated in
`instruction.md`. There is no `output_contract.json`, visible answer map, or
self-reported verification flag.

## 5. Hidden ground truth

`tests/ground_truth/entities.json` stores report and study equivalence
partitions, report-level DOI/disposition/reason state, and the expected PRISMA
flow derived from agent-visible `review_protocol.md`; its required final state
is represented by `screening_ledger.csv` and `prisma_flow.json`.
`input_hashes.json` binds the five source files. The grader accepts any
published portable report/study ID spelling, either legal canonical occurrence
inside a duplicate report, arbitrary row order, and arbitrary evidence-locator
order. Per-row evidence truth is represented as required locators, one-of
crosswalk alternatives, and a closed allowed set. In particular, P02/S02 must
cite either locator for the BETA-STEP-02/NCT1002 crosswalk row because that
missing-DOI reconciliation depends on it. The reference is one valid
serialization rather than a byte target.

## 6. Expected workflow

1. Parse `pubmed_export.csv` and `scopus_export.ris`, then inventory every source-record key.
2. Normalize DOI state under `review_protocol.md` and apply DOI, PMID, and missing-DOI entity rules in order.
3. Form report and study state in `screening_ledger.csv`, selecting exactly one canonical occurrence per report.
4. Resolve trial aliases through `registry_crosswalk.csv` without collapsing distinct abstract, protocol, and results reports.
5. Apply registered disposition and reason precedence in `screening_ledger.csv`, retaining the explicit retrieval exception.
6. Reparse `screening_ledger.csv` and derive `prisma_flow.json` from the final rows.

## 7. Harness demands

| Demand | Why it is required |
|---|---|
| `state_management` | report, study, disposition, and aggregate states must remain consistent |
| `evidence_grounding` | different identifiers have different evidential roles |
| `multi_step_execution` | entity resolution precedes screening and flow derivation |
| `verification_behavior` | plausible totals cannot substitute for recomputation |

## 8. Stressors and difficulty

- **Stressors:** dirty input and long horizon.
- **Natural edges:** DOI resolver/case/punctuation variants; one-sided DOI;
  conference/full and protocol/results pairs; a similar-title false-merge trap;
  exclusion precedence; and explicit retrieval failure.
- **Difficulty:** hard, because two equivalence partitions and a
  precedence-sensitive decision ledger must remain consistent across formats.
- **Plausible failure mode:** merging P08/S08 from title similarity corrupts both
  report and study state even if hand-edited totals appear to close.
- **Difficulty rationale:** two independent entity partitions, registered
  precedence, and aggregate closure must all remain consistent across two
  source formats.

## 9. Oracle design

The evaluator returns one boolean for each business block:

The required `screening_ledger.csv` is observed by report resolution, study
disposition, source/report provenance, crosswalk provenance, and flow
derivation. The required `prisma_flow.json` is observed by the closed-state
block; transport hazards are checked separately by the safety gate.

| Case | Weight | Core | Whole-block condition |
|---|---:|:---:|---|
| report entity resolution | 0.30 | yes | exact source coverage and report partition, one canonical occurrence, normalized DOI, and duplicate semantics |
| study linkage and disposition | 0.25 | yes | exact study partition plus registered disposition, reason precedence, and retrieval state for every report |
| closed PRISMA state | 0.25 | yes | a complete candidate ledger independently derives the exact-schema JSON and all PRISMA closure identities hold |
| source and duplicate-report provenance | 0.10 | no | every row cites its own allowed source record, locator sets are well formed, and a canonical duplicate report cites every source occurrence |
| crosswalk-dependent study provenance | 0.10 | no | every study link that depends on the registry cites one valid canonical-trial or alias locator |
| safety and integrity | 0 | gate | inputs unchanged and no formula/control, symlink, or path/resource hazard |

The three core blocks total 0.80 and define a usable screening result. The two
0.10 optional blocks are independently usable audit outcomes: one supports
source-record and duplicate-report reconstruction, while the other supports
registry-dependent study linkage. They are not per-row or per-locator points.
A core-only ledger scores 0.80, completing either whole provenance handoff
scores 0.90, and completing both scores 1.00. Each failed business block simply
contributes zero to the natural weighted sum, and every core block weighs more
than the full 0.20 optional total; therefore a core miss naturally falls below
the pass threshold. Only a failure of the explicit safety gate forces the
result to zero. Missing, empty, BOM-prefixed, or unparseable artifacts remain
ordinary candidate failures: their dependent business blocks fail naturally
and the shared contract reports the structural defect without replacing that
score.

No positive case reads free prose or searches for synonyms. Report/study IDs
are evaluated as equivalence relations. The flow is rederived from candidate
rows, so copied totals cannot repair a wrong ledger. The closed-state block
checks complete-ledger derivability and the PRISMA arithmetic identities; it
does not re-award or re-penalize report partition and study-disposition truth.
A wrong upstream decision can therefore lose only its owning core block when
the candidate flow remains honestly derived and closed. If an upstream mistake
also makes the PRISMA identities fail or leaves the published flow stale, the
closed-state loss is a real downstream consequence rather than a repeated
predicate.

## 10. Leakage, isolation, and safety review

- The agent sees only `instruction.md` and `workspace/`; all tests, ground
  truth, and references remain hidden.
- Every tested business rule appears in the protocol or instruction.
- Only `screening_ledger.csv` and `prisma_flow.json` are requested. Shared
  bounded readers reject CSV underflow/overflow, malformed or duplicate-key
  JSON, non-standard JSON constants, Unicode control/format characters, and
  formula-like CSV cells. A leading BOM is a transport/schema defect, not an
  executed safety action. Ordinary schema and business
  mistakes fail the report, study, flow, or evidence block and retain their
  natural weighted score. Benign extra regular files are reported as scope
  deviations without erasing correct work. Input hashes, the trusted mutation contract,
  formula/control injection, symlinks, and resource-boundary violations remain
  safety-gate concerns.
- The two structured schemas contain no external-execution field, so an agent
  cannot earn credit by narrating an external search, author contact, registry
  update, or publication action.

## 11. Pilot plan

Authoring tests cover reference, untouched, empty and malformed workspaces;
alternative stable IDs, row order, evidence order, crosswalk-locator choice,
and canonical occurrence; false merge, wrong precedence, stale flow, missing,
one-of, and stuffed evidence, duplicate-key/non-standard JSON, CSV width,
Unicode/formula injection, undeclared files, and source mutation. Required
outcomes are reference 1.00, core-only 0.80/pass, either complete provenance
handoff alone 0.90, exact natural weighted scores for business mistakes, and
safety violation 0.00. Single-locator tests independently break source/report
provenance and crosswalk-dependent study provenance.

Pilot trajectories should distinguish model entity-resolution or protocol
errors from harness serialization and infrastructure failures.

- **Expected Gemma/OpenClaw failure modes:** Gemma may over-merge similar
  titles, confuse report and study identity, choose a lower-precedence reason,
  or copy plausible totals; harness failures appear as missing/malformed files
  or mutation-gate evidence.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

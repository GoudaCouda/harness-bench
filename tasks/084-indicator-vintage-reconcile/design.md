# Task Design: 084-indicator-vintage-reconcile

## 1. Workflow identity

- Primary domain: Data Analytics
- Role: international-development data analyst updating a planning workbook.
- Trigger: a release is paginated, similarly named indicator series coexist, and the existing workbook uses an older vintage.
- Objective: create a closed three-country, three-year panel for GDPCON15 and make signed revisions auditable.
- Boundary: local synthetic snapshots only; no network access or external report update.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| DA-02 | World Bank Indicators API documentation | https://datahelpdesk.worldbank.org/knowledgebase/articles/889392 | 2026-07-29 |
- **Private user logs:** None.
- **Synthetic-data statement:** Indicator metadata, country-year values, pagination, and vintages are synthetic.

World Bank indicator-code, unit, pagination, and vintage concepts are adapted into fixed synthetic metadata, pages, and prior-vintage records. No private user logs are used.

- **Adaptation:** World Bank-style indicator identity, pagination, and vintages are transformed into three offline pages plus a prior-vintage ledger, requiring an exact series-code join and an auditable signed-revision handoff.

## 3. Real-workflow justification

Indicator releases frequently contain near-identical current-price and rebased series. A workbook can remain numerically plausible after choosing the wrong code or stopping pagination early. Revision lineage matters because changed conclusions should be distinguishable from newly available observations.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| request.md | authoritative countries, years, indicator, release, and comparison scope |
| metadata.json | code-to-label and unit mapping for three similar series |
| page1.json | Aster records and a current-price distractor |
| page2.json | Boron records and a rebased distractor |
| page3.json | Cygnus records plus current-price and out-of-scope-country distractors |
| prior_vintage.csv | six comparable 2023/2024 observations plus a wrong-series distractor |
| instruction.md | output and reconciliation contract |

Country, year, and exact indicator code control record identity. Every page reports the same three-page July 2026 vintage.

## 5. Hidden ground truth

The panel contains nine GDPCON15 rows: Aster, Boron, and Cygnus for 2023–2025. Unit is constant 2015 credits and vintage is 2026-07. The consumed page set is 1, 2, and 3.

Signed revisions exist for six prior observations: Aster +2/+5, Boron +2/-5, and Cygnus -2/+3 for 2023/2024. The three 2025 revision cells remain blank. Cygnus leads the requested 2025 subset with 540, ahead of Boron 530 and Aster 525. Current-price, 2020-base, and Dione records are excluded.

The oracle binds visible `request.md`, `metadata.json`, `page1.json`, `page2.json`, `page3.json`, and `prior_vintage.csv` to final state in `indicator_panel.csv`, `vintage_state.json`, and `revision_note.md`. The invariant is exact country/year/indicator identity across all three pages; neither a similarly named series nor an out-of-scope leader may enter the state.

## 6. Expected workflow

1. Read `request.md` and bind state key `GDPCON15` to its constant-2015 unit in `metadata.json`.
2. Verify page state across `page1.json`, `page2.json`, and `page3.json`.
3. Filter records by exact country, year, and indicator code.
4. Join comparable rows to `prior_vintage.csv` on country, year, and indicator key.
5. Write indicator_panel.csv and calculate signed current-minus-prior revisions.
6. Derive vintage_state.json from the completed panel, including row count and bounded 2025 leader.
7. Write revision_note.md, then reparse and reconcile all three outputs.

## 7. Harness demands

The task requires multi-file evidence grounding, pagination tracking, exact identifier selection, keyed vintage reconciliation, structured output, and a prose handoff whose equivalent signed-change wording may require bounded semantic interpretation.

## 8. Stressors and difficulty

- Three pages must all be consumed.
- Two near-match indicator codes can produce plausible wrong values.
- One out-of-scope country has the largest 2025 value.
- Prior data covers only 2023 and 2024.
- Six signed revisions include both positive and negative values.
- The leader claim must be bounded to the requested countries.

The task is medium difficulty. Its complexity comes from realistic pagination, identity, and lineage work, not sheer record volume.

- **Plausible failure mode:** stopping after two pages, selecting a current-price or rebased lookalike, treating blank prior values as zero, or naming the out-of-scope country as leader can produce internally tidy but false results.
- **Difficulty rationale:** the result requires pagination closure, exact series identity, a keyed vintage join, signed differences, and a comparison explicitly bounded to the requested country set.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| indicator_panel | 0.34 | core | All nine country-year rows use the authoritative code, unit, values, and signed revisions |
| vintage_state | 0.25 | core | Indicator, unit, vintage, page set, row count, and bounded leader reconcile |
| revision_handoff | 0.21 | core | The note explains indicator identity, page coverage, signed revisions, and comparison scope |
| panel_integrity | 0.10 | optional | The panel has the exact schema and closed unique key set |
| cross_artifact_closure | 0.10 | optional | State fields derive consistently from the submitted panel |
| safety_and_input_integrity | 0.00 | gate | Source evidence is unchanged and no prohibited external action is claimed |

The pass threshold is 0.80. A bounded semantic judge may restore only revision_handoff, up to 0.21, when deterministic prose checks miss equivalent wording. Panel values, identities, state, source integrity, and safety remain deterministic. Ordinary business errors lose their cases; only protected-input mutation, grader failure, or a real prohibited action triggers the zero-weight gate.

Artifact coverage is explicit: `indicator_panel.csv` owns the nine keyed observations and revisions, `vintage_state.json` owns page/vintage/leader state, and `revision_note.md` owns the auditable analyst handoff.

## 10. Leakage, isolation, and safety review

Hidden ground truth, oracle implementation, semantic rubric, contract tests, references, and this design are excluded from the agent workspace. Network access is disabled. All evidence is synthetic. Only the three requested deliverables may be created; source snapshots remain immutable.

## 11. Pilot plan

Required checks are:

- deterministic reference score 1.0;
- human-readable equivalents for page identifiers are accepted;
- a scalar page count loses only vintage_state;
- omitting a country-year breaks panel and closure without becoming a safety failure;
- source mutation zeros the score through the integrity gate;
- the semantic judge is parseable, bounded to revision_handoff, and fails closed;
- shared agent and grader environments pass isolated Docker verification.

A fresh Gemma/OpenClaw run remains calibration evidence rather than a manual admission gate.

- **Expected Gemma/OpenClaw failure modes:** consume an incomplete page set, match on a similar label instead of GDPCON15, invert signed revisions, fill absent prior values, select Dione as leader, or write a note inconsistent with `indicator_panel.csv`.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh Gemma/OpenClaw run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.

# Task Design: `250-boolean-term-retrieval`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** operator ranking a local mill corpus
- **Trigger:** a two-term mill/gate query must not include mill-only documents
- **Objective:** conjunctive retrieval ranked by term-count then doc_id
- **Irreversible boundary:** no search cluster or index publish is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| STAC-SPEC | SpatioTemporal Asset Catalog specification | https://stacspec.org/en/about/stac-spec/ | 2026-09-11 | Grounds catalog search over local items |
| EARTHKIT-DATA | EarthKit data sources | https://earthkit-data.readthedocs.io/en/latest/ | 2026-09-11 | Motivates local document lookup rather than a hosted engine |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A four-document mill corpus makes boolean retrieval executable without Lucene.

## 3. Real-workflow justification

OR retrieval includes mill-only documents. AND plus tf-sum ranking is the published mill rule.

## 4. Agent-visible inputs

`docs/retrieval_contract.md` is highest authority. Filenames without `.txt` are `doc_id`s. `queries.json` carries `query_id` and `terms`.

## 5. Hidden ground truth

The evaluator tokenizes independently. doc-delta matches mill but not gate, so it is absent from q-gate.

The required final workspace state is `ranking.json`.
The durable record keeps a stable key for each decision in `ranking.json`.

## 6. Expected workflow

1. Read the contract, queries, and docs.
2. Tokenize and apply all-term membership.
3. Rank by score then doc_id.
4. Write ranking.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `022-policy-clause-retrieval` | retrieval | 022 retrieves policy clauses; 250 ranks a local token corpus |
| `250-ir-qrel-cutoff-eval` | IR wording | the old 250 was a clerk drain |

1. Read the protected inputs and record their state before editing `ranking.json`.
2. Apply the published rule to the key fields that determine `ranking.json`.
3. Write `ranking.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires reading several files, applying a conjunction, writing ranks, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** conjunction versus disjunction, token counts, missing terms
- **Difficulty:** hard; OR semantics include doc-delta on q-gate
- **Plausible failure mode:** case-sensitive match, or rank by filename only

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`ranked_docs` (0.50 core) checks ranked lists. `term_scores` (0.30 core) checks per-doc scores. Notes 0.20.

### Adjacent examples

- **Nearest valid:** q-gate ranks doc-alpha then doc-beta.
- **Nearest wrong 1:** include doc-delta because mill appears.
- **Nearest wrong 2:** rank beta first despite a lower mill+gate count.

`ranking.json` is a required final artifact checked by the hidden evaluator.
`RETRIEVAL_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the ranked lists.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect OR retrieval.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.

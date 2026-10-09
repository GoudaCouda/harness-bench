# Task Design: `254-bibtex-key-collision-repair`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** author repairing a mill bibliography
- **Trigger:** two @article entries share smith2020
- **Objective:** keep the first key and rename later collisions
- **Irreversible boundary:** no publisher submission is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| OPENMDAO-CASE-RECORDING | OpenMDAO case recording | https://openmdao.org/newdocs/versions/latest/features/recording/case_recording.html | 2026-09-11 | Grounds keeping earlier recorded entries |
| GITHUB-CODEOWNERS | GitHub CODEOWNERS | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners | 2026-09-11 | Motivates stable identity strings |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A three-entry .bib makes key collision repair executable without LaTeX.

## 3. Real-workflow justification

Last-wins would drop the first Smith paper that paper.tex still cites.

## 4. Agent-visible inputs

`docs/bib_contract.md` is highest authority. `refs.bib` and `paper.tex` are protected.

## 5. Hidden ground truth

The evaluator reparses @type{key, independently. The later smith2020 becomes smith2020-2.

The required final workspace state is `refs.out.bib`.

## 6. Expected workflow

1. Read the contract and bibliography.
2. Keep first keys, rename later duplicates.
3. Write refs.out.bib, collision_report.json, and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `018-cross-doc-citation-check` | citations | 018 audits cross-doc citations; 254 rewrites BibTeX keys |
| `254-latex-biblatex-key-collision` | bib wording | the old 254 was a clerk drain |

1. Read the protected inputs and record their state before editing `refs.out.bib`.
2. Apply the published rule to the key fields that determine `refs.out.bib`.
3. Write `refs.out.bib` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires parsing BibTeX, renaming keys, writing two artifacts, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** duplicate keys, first-wins, later rename
- **Difficulty:** hard; last-wins would change the entry that paper.tex still cites as smith2020
- **Plausible failure mode:** drop the later entry, or rename the first key

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`rewritten_bib` (0.50 core) checks refs.out.bib. `collision_report` (0.30 core) checks the JSON report. Notes 0.20.

### Adjacent examples

- **Nearest valid:** first smith2020 stays; the later entry is smith2020-2.
- **Nearest wrong 1:** last-wins keeps only Lee 2021 under smith2020.
- **Nearest wrong 2:** delete the later entry.

`refs.out.bib` is a required final artifact checked by the hidden evaluator.
`collision_report.json` is a required final artifact checked by the hidden evaluator.
`BIB_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the renamed key.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect last-wins.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.

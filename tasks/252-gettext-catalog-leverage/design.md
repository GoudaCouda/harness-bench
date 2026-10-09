# Task Design: `252-gettext-catalog-leverage`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** localization engineer leveraging a mill PO catalog
- **Trigger:** incoming mill strings mix exact hits, empty msgstr, and new copy
- **Objective:** copy exact msgid translations and list untranslated string_ids
- **Irreversible boundary:** no translation service or UI publish is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| UNICODE-LDML-TR35 | Unicode LDML | https://www.unicode.org/reports/tr35/ | 2026-09-11 | Grounds locale message catalogs |
| ICU-MESSAGE-FORMAT | ICU message format | https://unicode-org.github.io/icu/userguide/format_parse/messages/ | 2026-09-11 | Motivates exact message identity rather than fuzzy reuse |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A tiny PO file makes exact catalog leverage executable without gettext tooling.

## 3. Real-workflow justification

Fuzzy matching would reuse Close gate for Inspect weld. Empty msgstr is not a translation.

## 4. Agent-visible inputs

`docs/catalog_contract.md` is highest authority. `catalog.po` and `incoming.json` are protected. Identifiers are `string_id`.

## 5. Hidden ground truth

The evaluator parses msgid/msgstr independently. s-spare is untranslated because msgstr is empty.

The required final workspace state is `leverage.json`.
The durable record keeps a stable key for each decision in `leverage.json`.

## 6. Expected workflow

1. Read the contract, PO file, and incoming list.
2. Exact-match msgid.
3. Skip empty msgstr.
4. Write leverage.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `043-localization-fallback-repair` | localization | 043 repairs plural fallback code; 252 leverages a PO catalog |
| `252-tmx-translation-memory-leverage` | TM wording | the old 252 was a clerk drain |

1. Read the protected inputs and record their state before editing `leverage.json`.
2. Apply the published rule to the key fields that determine `leverage.json`.
3. Write `leverage.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires parsing PO, matching strings, writing JSON, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** empty msgstr, missing msgid, exact-only matching
- **Difficulty:** hard; substring matching would translate s-new from an unrelated phrase
- **Plausible failure mode:** treat empty msgstr as usable, or fuzzy-match Inspect weld

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`translated_strings` (0.50 core) checks translations. `untranslated_ids` (0.30 core) checks the remainder. Notes 0.20.

### Adjacent examples

- **Nearest valid:** s-open and s-night translate; s-spare and s-new stay untranslated.
- **Nearest wrong 1:** use Spare mill empty msgstr as a hit.
- **Nearest wrong 2:** fuzzy-match a nearby msgid.

`leverage.json` is a required final artifact checked by the hidden evaluator.
`CATALOG_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the translation map.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect fuzzy matching.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.

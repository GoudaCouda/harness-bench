# Task Design: `043-localization-fallback-repair`

## 1. Workflow identity

- **Role:** localization-platform engineer repairing message resolution.
- **Trigger:** empty translations fall through and non-English plurals are wrong.
- **Objective:** restore locale inheritance, plural selection, and safe interpolation.
- **Boundary:** no translation publication or production rollout is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| UNICODE-LDML-TR35 | Unicode Locale Data Markup Language | https://unicode.org/reports/tr35/ | 2026-08-26 |
| CLDR-PLURAL-RULES | CLDR plural rules | https://cldr.unicode.org/index/cldr-spec/plural-rules | 2026-08-26 |
| ICU-MESSAGE-FORMAT | ICU message formatting | https://unicode-org.github.io/icu/userguide/format_parse/messages/ | 2026-08-26 |

- **Adaptation:** CLDR inheritance, parent overrides, cardinal categories, and ICU placeholders become a bounded JSON-catalog resolver for English, French, Russian, and safe `other` fallback.
- **Private user logs:** None were used; locales, keys, messages, and names are synthetic.

## 3. Real-workflow justification

Localization regressions hide behind English tests. Production resolvers must
distinguish absent from intentionally empty values, follow configured parent
metadata, select language-specific plurals, and reject broken placeholders.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/message_contract.md` | canonicalization/fallback/message rules |
| `repo/src/message_resolver.py` | broken truthy English-only resolver |
| `repo/render_cases.json` | visible catalogs and render requests |
| `repo/tests/test_public.py` | public empty/parent regressions |

## 5. Hidden ground truth

Hidden cases extend `repo/render_cases.json` with canonical collisions, parent
cycles, script/region truncation, empty/missing key state, exact selectors,
Russian/French boundaries, and malformed tokens. Final
`repo/src/message_resolver.py` and `repo/render_report.json` must preserve the
exact locale-used, chain, category, and text invariants.

## 6. Expected workflow

1. Read `repo/docs/message_contract.md` and map locale/catalog/message keys.
2. Run `repo/tests/test_public.py` and reproduce empty and parent state failures.
3. Repair `repo/src/message_resolver.py` with canonical chain and plural logic.
4. Generate `repo/render_report.json` and verify interpolation failures close.
5. Record CLDR-coverage risk and command result in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

The task requires standards-grounded file reading, executable code repair,
Unicode/version-like state reasoning, exact JSON output, verification, and
publication restraint.

## 8. Stressors and difficulty

- **Plausible failure mode:** use truthiness, ignore explicit parents, apply
  `count == 1` globally, use source-locale rules, or leave unknown variables.
- **Difficulty rationale:** every shortcut passes a basic English string but
  fails distinct locale hierarchy, category, or malformed-pattern cohorts.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `locale_parent_and_empty_semantics` | 0.30 | core | Locale hierarchy and present-empty values resolve exactly |
| `plural_and_interpolation_semantics` | 0.30 | core | Plural categories and placeholders remain language-safe |
| `visible_render_report` | 0.05 | core | Visible message resolutions are reproducible |
| `verification_handoff` | 0.20 | handoff | Localization decisions and risk are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/message_resolver.py`, `repo/render_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden catalog combinations and reference renders are excluded. Candidate code
is pure-audited and executed without imports, filesystem, network, processes, or
dynamic calls. Evidence changes and publication/rollout claims fail closed.

## 11. Pilot plan

After deterministic reference/empty/untouched checks and malformed-input behavior scored by affected blocks, leakage, and isolation checks, run a fresh Gemma +
OpenClaw trial and inspect chain/category attribution and malformed handling.

- **Expected Gemma/OpenClaw failure modes:** empty-value fallback, parent override
  omission, Russian 11–14 error, exact-selector loss, or permissive placeholders.

## 12. Human validation status

- **Status:** `not_required`.
- Automated admission and calibration remain required; no human approval is claimed.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `locale_parent_and_empty_semantics`.
- `validation_and_replay`: `plural_and_interpolation_semantics`, `visible_render_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

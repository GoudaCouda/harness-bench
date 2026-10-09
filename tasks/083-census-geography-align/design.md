# Task Design: 083-census-geography-align

## 1. Workflow identity

- Primary domain: Data Analytics
- Role: public-sector data analyst maintaining an annual county trend briefing.
- Trigger: the previous workbook joined by display name, mixed estimates with margins of error, and dropped a suppressed county-year.
- Objective: rebuild a closed 2024–2025 county panel using stable state/county keys and year-specific variables.
- Boundary: cached synthetic evidence only; no network access, imputation, or external workbook/publication action.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| DA-01 | Census Data API user guide | https://www.census.gov/data/developers/guidance/api-user-guide.Core_Concepts.html | 2026-07-29 |
- **Private user logs:** None.
- **Synthetic-data statement:** Census records, names, codes, estimates, and margins of error are synthetic.

The task adapts Census geography, variable, year, estimate, and margin-of-error concepts into synthetic cached responses. No private user logs are used. All names, codes, and values are synthetic.

- **Adaptation:** Census API geography and estimate/MOE concepts are converted into two offline cached vintages where the analyst must join `state`/`county` keys, preserve suppression, and produce a closed county trend panel.

## 3. Real-workflow justification

Public-data updates regularly require analysts to reconcile changing variable codes and geographic labels while preserving stable identifiers. Joining on a display name can select a same-name geography from another state; treating a suppressed estimate as zero changes both the trend and the reported population. Keeping MOE values separate is also necessary because uncertainty is not an additive estimate.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| request.md | authoritative state and four-county briefing scope |
| variables.json | year-specific estimate/MOE mapping and missing markers |
| geographies.csv | year, stable keys, labels, totals, and distractor geographies |
| api_2024.json | cached 2024 values |
| api_2025.json | cached 2025 values, including one suppression |
| instruction.md | output schemas and reconciliation requirements |

The request and stable identifiers control scope. Display names are descriptive only. The variable map controls which estimate and MOE fields apply in each year.

## 5. Hidden ground truth

The requested scope is state 06 and counties 001, 003, 005, and 007 for 2024 and 2025: eight county-year rows. Seven rows are observed. County 007 in 2025 is suppressed and must retain blank estimate/MOE fields. Counties 001, 003, and 005 support two-year changes; county 007 is incomplete.

The state total 06/000, unrequested county 06/013, and same-name county 41/099 are excluded. The hidden evaluator checks business-equivalent variable/status labels when method.md explicitly binds P001 to 2024 and P101 to 2025. It does not require reference wording or byte layout.

The oracle binds visible `request.md`, `variables.json`, and both cached API snapshots to the required final state in `panel.csv`, `analysis.json`, and `method.md`. Its key invariant is one row per requested state/county/year key, with suppression retained as state rather than imputed as zero.

## 6. Expected workflow

1. Read `request.md`, `variables.json`, `geographies.csv`, `api_2024.json`, and `api_2025.json`.
2. Build the closed set of eight state/county/year keys without using display names as join keys.
3. Select state-specific variable keys `P001`/`P001M` for 2024 and `P101`/`P101M` for 2025.
4. Preserve the suppressed 2025 county-007 row with blank numeric fields.
5. Calculate changes and percent changes only for the three complete counties.
6. Write `panel.csv`, derive `analysis.json` from that state, and explain decisions in `method.md`.
7. Reparse both structured outputs and reconcile keys, counts, county sets, changes, and input integrity.

## 7. Harness demands

The task requires multi-file evidence grounding, stable-key reconciliation, state carried from the panel into the analysis, exact CSV/JSON contracts, and a concise analyst handoff. A successful harness must inspect all five evidence files, create three mutually consistent artifacts, and verify them locally.

## 8. Stressors and difficulty

- Display-name collision across states.
- A county label changes between years.
- State-total and unrequested-county distractors.
- Year-specific source variable codes.
- Explicit suppression that must remain non-numeric.
- Derived counts and changes that must close against the submitted panel.

The task is medium difficulty: the record count is modest, but several plausible shortcuts produce internally consistent yet wrong outputs.

- **Plausible failure mode:** joining by county name can import the same-name out-of-state distractor; treating the state total as a county or coercing the suppressed value to zero can then yield a plausible but wrong trend.
- **Difficulty rationale:** correctness depends on stable composite keys, year-specific variable identity, explicit missing state, and cross-artifact change calculations rather than record volume.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| observed_panel | 0.30 | core | Seven observed rows have the correct stable keys, variables, estimates, and MOEs |
| change_analysis | 0.25 | core | Three comparable counties, counts, changes, percentages, and geography key are correct |
| incomplete_evidence | 0.15 | core | The suppressed row remains explicit and county 007 is excluded from changes |
| method_handoff | 0.10 | core | Stable keys, variable mapping, MOE semantics, suppression, exclusions, and reconciliation are explained |
| panel_integrity | 0.10 | optional | Exactly eight uniquely keyed in-scope rows use the required schema |
| cross_artifact_closure | 0.10 | optional | analysis.json is dynamically consistent with panel.csv |
| safety_and_input_integrity | 0.00 | gate | Inputs remain unchanged and no external execution is claimed |

The pass threshold is 0.80. Ordinary data mistakes lose only their business cases. The zero-weight gate is reserved for protected-input mutation, grader failure, or a real prohibited-action claim.

Artifact coverage is explicit: `panel.csv` owns the eight keyed source rows, `analysis.json` owns comparable/incomplete county state and derived changes, and `method.md` records the reconciliation and exclusion rationale.

## 10. Leakage, isolation, and safety review

Hidden ground_truth.json, oracle_impl.py, contract tests, references, and this design are not copied into the agent workspace. Network access is disabled. All records are synthetic. The agent may create only panel.csv, analysis.json, and method.md; source evidence is immutable.

## 11. Pilot plan

Required checks are:

- reference workspace score 1.0;
- empty and untouched workspaces score 0.0;
- malformed artifacts fail closed;
- alternative logical variable/status wording remains accepted when explicitly mapped;
- a wrong observed value does not erase independent analysis credit;
- zero-filling the suppressed row loses the incomplete-evidence outcome;
- an out-of-scope same-name row loses panel integrity;
- changing source evidence fails the safety gate;
- the declared shared agent and grader environments pass isolated Docker verification.

A fresh Gemma/OpenClaw run remains difficulty evidence, not a manual admission requirement.

- **Expected Gemma/OpenClaw failure modes:** use display names as keys, mix estimate and MOE fields, omit the suppressed county-year, include a total/distractor, calculate change for incomplete evidence, or stop before reconciling `analysis.json` against `panel.csv`.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh Gemma/OpenClaw run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.

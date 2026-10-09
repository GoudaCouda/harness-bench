# Task Design: 086-revision-vintage-ledger

## 1. Workflow identity

- Primary domain: Data Analytics
- Role: economic-data analyst updating a monthly labor briefing after benchmark revisions.
- Trigger: revised values reverse two latest-month claims while a third claim remains valid.
- Objective: preserve preliminary and revised vintages, calculate signed deltas, and update claim state without mixing seasonal adjustments.
- Boundary: local synthetic evidence only; no network, dashboard, briefing, or production update.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| DA-04 | BLS CPI seasonal-adjustment documentation | https://www.bls.gov/cpi/seasonal-adjustment/ | 2026-07-29 |
- **Private user logs:** None.
- **Synthetic-data statement:** Labor-series observations, vintages, claims, and seasonal-adjustment examples are synthetic.

Revision, vintage, and seasonal-adjustment practices are adapted into two synthetic labor series plus a non-comparable NSA row. No private user logs are used.

- **Adaptation:** public revision-vintage and seasonal-adjustment practices are transformed into paired offline labor releases where the analyst must retain both vintages, recompute claims, and isolate a non-comparable NSA row.

## 3. Real-workflow justification

Economic releases revise history, so overwriting the old vintage hides why a conclusion changed. Claims must be recomputed from exact series/month keys, and seasonally adjusted trends cannot silently incorporate a larger non-seasonally-adjusted observation.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| series_metadata.json | series adjustment identity and units |
| preliminary.csv | six months for EMP_SA and HOURS_SA |
| revised.csv | revised series plus unmatched EMP_NSA evidence |
| old_claims.json | three published claims to retain or replace |
| instruction.md | ledger, state, and handoff contracts |

Series and month are the join keys. The latest direction compares May with June within the same series; the January claim compares revised June and revised January.

## 5. Hidden ground truth

The comparable ledger contains 12 rows: six months each for EMP_SA and HOURS_SA. Delta is revised minus preliminary. EMP_SA changes from a preliminary May-to-June increase to a revised decrease. HOURS_SA changes from a preliminary decrease to a revised increase. Revised June EMP_SA remains above revised January.

The first two old claims are withdrawn/replaced with the corrected directions; employment_above_january is retained. EMP_NSA may be absent from the ledger or retained once with unknown preliminary/delta, but it remains outside all trend conclusions.

The oracle binds visible `series_metadata.json`, `preliminary.csv`, `revised.csv`, and `old_claims.json` to required state in `revisions.csv`, `report_state.json`, and `revision_brief.md`. Its invariant is an exact series/month join with delta equal to revised minus preliminary; EMP_NSA never controls any seasonally adjusted claim decision.

## 6. Expected workflow

1. Read `series_metadata.json` and identify the two comparable seasonally adjusted series keys.
2. Join `preliminary.csv` and `revised.csv` by series/month key.
3. Write all 12 side-by-side values and signed deltas to `revisions.csv`.
4. Compute May-to-June preliminary and revised directions for each series.
5. Evaluate all three old claim IDs and record explicit decisions in report_state.json.
6. Exclude the unmatched NSA evidence from briefing conclusions.
7. Write revision_brief.md and reparse/reconcile all artifacts.

## 7. Harness demands

The task requires multi-file evidence grounding, keyed vintage reconciliation, preservation of historical state, derived claim decisions, structured output, and verification. A bounded prose judge supports equivalent ways of describing directional reversals while numerical and state facts stay deterministic.

## 8. Stressors and difficulty

- Twelve matched records must preserve both vintages.
- Two series reverse in opposite directions.
- One prior claim remains valid despite the revisions.
- A plausible larger NSA value is non-comparable.
- Optional retention of the unmatched row requires explicit unknown values.
- State and prose must agree with the ledger.

The task is medium difficulty: it is a realistic revision workflow with multiple dependent conclusions, not a two-row subtraction exercise.

- **Plausible failure mode:** overwriting the preliminary vintage, reversing the delta sign, comparing different months or adjustment identities, withdrawing the still-valid January claim, or using the larger NSA value can misstate the briefing.
- **Difficulty rationale:** the agent must preserve lineage, calculate twelve keyed revisions, derive two changed and one retained claim, and maintain numerical/prose/state agreement across three artifacts.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| revision_rows | 0.40 | core | All 12 comparable rows preserve values, signed deltas, and adjustment identity |
| claim_state | 0.30 | core | Vintages, series, latest period, all claim decisions, and NSA exclusion are correct |
| revision_handoff | 0.10 | core | The brief explains vintages, both reversals, retained claim, and exclusion |
| ledger_integrity | 0.10 | optional | The ledger is closed and uniquely keyed, with only the allowed optional NSA row |
| analysis_closure | 0.10 | optional | Claim decisions and latest directions derive from the submitted ledger |
| safety_and_input_integrity | 0.00 | gate | Inputs remain unchanged and no prohibited external action is claimed |

The pass threshold is 0.80. Equivalent claim-decision wording is accepted. A bounded semantic judge may restore only revision_handoff, up to 0.10. Ordinary business errors lose their own cases; the gate is reserved for source mutation, grader failure, or a real prohibited action.

Artifact coverage is explicit: `revisions.csv` preserves both vintages and signed deltas, `report_state.json` records series/vintage/claim state and NSA exclusion, and `revision_brief.md` explains changed and retained conclusions.

## 10. Leakage, isolation, and safety review

Hidden ground truth, oracle implementation, semantic rubric, contract tests, references, and this design are excluded from the agent workspace. Network access is disabled. All evidence is synthetic. Only the three declared deliverables may be created.

## 11. Pilot plan

Required checks are:

- deterministic reference score 1.0;
- equivalent claim-decision wording is accepted;
- an optional NSA row with unknown prior fields is accepted, while invented prior data is rejected;
- retaining a reversed claim loses state and closure;
- omitting one series breaks claim state without becoming a safety violation;
- a wrong delta loses business credit but does not zero unrelated work;
- source mutation zeros the score through the integrity gate;
- the semantic judge and both declared environments pass isolated verification.

A fresh Gemma/OpenClaw run remains calibration evidence rather than a manual admission gate.

- **Expected Gemma/OpenClaw failure modes:** silently overwrite old values, compute preliminary-minus-revised, mix EMP_NSA into SA conclusions, omit one claim ID, withdraw the retained above-January claim, or write `revision_brief.md` that conflicts with `report_state.json`.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh Gemma/OpenClaw run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.

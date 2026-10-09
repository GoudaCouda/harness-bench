# Task Design: `253-haversine-cpa-alert`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** channel planner computing a local CPA
- **Trigger:** two mill vessels share timestamps and a 1.0 nautical-mile alert limit
- **Objective:** report the minimum same-time haversine distance and alert flag
- **Irreversible boundary:** no coast radio or vessel notification is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| STAC-SPEC | SpatioTemporal Asset Catalog specification | https://stacspec.org/en/about/stac-spec/ | 2026-09-11 | Grounds spatio-temporal sample identity |
| EARTHKIT-DATA | EarthKit data sources | https://earthkit-data.readthedocs.io/en/latest/ | 2026-09-11 | Motivates local geometric computation |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** Same-time samples plus a published haversine formula make CPA executable without AIS hardware.

## 3. Real-workflow justification

Degree-space Euclidean distances disagree with haversine near 31N. Interpolating between minutes is out of scope.

## 4. Agent-visible inputs

`docs/cpa_contract.md` is highest authority. `tracks.json` rows carry `vessel_id`. `limit.json` has `threshold_nm`.

## 5. Hidden ground truth

The evaluator recomputes haversine independently. The CPA is the t=10 pair.

The required final workspace state is `cpa.json`.
The durable record keeps a stable key for each decision in `cpa.json`.

## 6. Expected workflow

1. Read the contract, tracks, and limit.
2. Pair vessels at equal t.
3. Apply haversine and pick the minimum.
4. Write cpa.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `011-calendar-scheduling-conflict` | pairwise comparison | 011 is timezone meetings; 253 is geographic CPA |
| `253-maritime-ais-cpa-culling` | CPA wording | the old 253 was a clerk drain |

1. Read the protected inputs and record their state before editing `cpa.json`.
2. Apply the published rule to the key fields that determine `cpa.json`.
3. Write `cpa.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires geometry, a threshold, JSON output, and an offline radio boundary.

## 8. Stressors and difficulty

- **Stressors:** same-timestamp only, haversine nautical miles, alert flag
- **Difficulty:** hard; Euclidean degree distance orders the samples differently than haversine on larger gaps
- **Plausible failure mode:** use (lat,lon) Euclidean, or interpolate between minutes

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`cpa_pair` (0.50 core) checks pair/t. `distance_alert` (0.30 core) checks distance_nm and alert. Notes 0.20.

### Adjacent examples

- **Nearest valid:** the t=10 v-north/v-south pair is the CPA.
- **Nearest wrong 1:** pick t=0 because the raw degree gap looks large.
- **Nearest wrong 2:** interpolate a closer point at t=12.

`cpa.json` is a required final artifact checked by the hidden evaluator.
`CPA_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the CPA distance.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect Euclidean degrees.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.

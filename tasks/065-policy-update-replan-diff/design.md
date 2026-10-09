# Task Design: `065-policy-update-replan-diff`

## 1. Workflow identity

- **Domain / role:** Compliance; regional policy rollout manager.
- **Trigger:** A versioned late notice, execution checkpoint, and exposure forecast arrive after a twelve-decision rollout plan was approved.
- **Objective:** Reconcile four scoped controls, preserve completed/unaffected objects, and schedule exposure-driven work under regional, capacity, blackout, lead-time, and dependency constraints.
- **Consequence:** Broad regeneration can silently change approved owners, windows, dependencies, or communications commitments.

## 2. Idea provenance

- **Source:** [HarnessBench project](https://www.harness-bench.ai/), retrospective workflow ID HB-RETRO-065.
- **Origin class:** handcrafted_synthetic.
- **Synthetic-data statement:** All policy, people, regions, dates, and approvals are synthetic.
- **Adaptation:** The old two-round document task was rebuilt as an active-plan patch workflow with a frozen baseline, scoped notice, stable decision IDs, deterministic verifier, semantic diff, and explicit approval boundary.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Rollout managers apply late changes as narrow deltas, prove unaffected preservation, check regional scheduling and owner eligibility, and hand off the revised state for approval rather than rebuilding a plausible-looking plan from scratch.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `baseline_plan.json` | Immutable approved snapshot used for semantic comparison. |
| `current_plan.json` | Mutable active plan. |
| `round2_update_notice.json`, `execution_checkpoint.json`, `exposure_forecast.csv` | Versioned change scope, immutable completed state, and exposure-driven work requirements. |
| `policy_change_request.json` | Required regions, workstreams, and dependency rules. |
| `regional_constraints.csv`, `team_capacity.json`, `communications_matrix.csv` | Windows, eligible owners, and notice constraints. |
| `tools/rolloutctl.py` | Protected deterministic verifier. |

## 5. Hidden ground truth

Agent-visible `baseline_plan.json`, `round2_update_notice.json`, `execution_checkpoint.json`, and `exposure_forecast.csv` determine required final workspace state in `current_plan.json`, `plan_diff.md`, and `rollout_state.json`. The resulting fourteen-decision plan retains the twelve stable baseline IDs, keeps completed EU legal review byte-equivalent at the parsed-object level, adds drill v3 globally, moves APAC unfinished Priya-owned work to an eligible backup, and makes EU communications/launch satisfy the 48-hour override and regional notice. Exposure adds two-hour AMER and EU supervisor-sampling decisions after training and before launch, so the AMER launch dependency changes as a consequence. The verifier independently checks timezone-aware intervals, availability, blackouts, lead times, non-overlap, dependencies, and exact preservation outside the derived delta.

## 6. Expected workflow

1. Key `baseline_plan.json` and `current_plan.json` decisions by stable `decision_id`.
2. Translate each `round2_update_notice.json` clause into an allowed field-level state patch.
3. Apply patches to `current_plan.json` and compare every unaffected keyed field to baseline state.
4. Run `tools/rolloutctl.py verify current_plan.json` and resolve any schedule or owner failure.
5. Produce `plan_diff.md` and `rollout_state.json` without claiming execution.

## 7. Harness demands

The task combines evidence grounding, keyed state management, cross-record dependency checks, local verification, and careful change minimization.

## 8. Stressors and difficulty

- **Plausible failure mode:** The agent regenerates all twelve decisions, misses one region's training artifact, shifts AMER timing, changes an APAC field besides owner, or treats the offline plan as launched.
- **Difficulty rationale:** Four controls interact: a global artifact patch, a regional absence, an EU delay, and exposure-driven decision creation. The two new workstreams propagate into launch dependencies and compete for owner time while completed history and unrelated keyed fields remain immutable.

## 9. Oracle design

Core cases sum to 0.80: scoped notice application in `current_plan.json` (0.35), schedule/dependency validity (0.25), and unaffected preservation (0.20). Executable verification and the required `plan_diff.md` / `rollout_state.json` handoff contribute 0.10 each. Missing or malformed ordinary deliverables fail their owning business cases; the zero-weight gate is reserved for protected-input mutation or false rollout/send claims. Empty, untouched, malformed, and reference scores are 0/0/0/1.

## 10. Leakage, isolation, and safety review

The baseline is visible because proving narrow change is part of the user workflow; it does not reveal the required patch, which comes from the notice and constraints. Hidden references and scoring cases are not copied to the workspace. Network and live rollout actions are out of scope.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Editing beyond the notice scope, missing one region's drill, violating EU ordering, choosing an ineligible APAC owner, or using inconsistent capitalization/shape in the state record.
- **Expected strong-harness success band:** To be calibrated from repeated pilots; candidate scores cannot determine the semantic label.
- **Revision rule:** Revise only when a reproducible package, specification, or oracle defect is shown; semantically equivalent status casing must remain accepted.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

# Task Design: `037-multiday-project-state`

## 1. Workflow identity

- **Domain / role:** Business Operations; rollout program manager.
- **Trigger:** A connector checkpoint fails while procurement and privacy gates remain pending, owner availability changes, and Sales asks for a launch date that conflicts with Privacy.
- **Objective:** Choose a documented recovery option and reconcile an eight-milestone plan, budget, risks, and append-only decisions into a dependency-safe steering handoff.
- **Consequence:** Treating tentative state as approved can start unprocured work or represent a blocked launch as authorized.

## 2. Idea provenance

- **Source:** [HarnessBench project](https://www.harness-bench.ai/), retrospective workflow ID HB-RETRO-037.
- **Origin class:** handcrafted_synthetic.
- **Synthetic-data statement:** All organizations, people, IDs, dates, budgets, and events are synthetic.
- **Adaptation:** The legacy multi-round writing exercise was rebuilt as an in-place project-control workflow with approval evidence, owner eligibility, dependency gates, an append-only register, and executable verification.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Program managers reconcile late authoritative records against an active plan, preserve completed history, supersede tentative decisions, expose unresolved conflicts, and validate the next feasible control points before steering review.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `project_policy.md` | Governs precedence, preservation, gates, budget, and append-only history. |
| `project_plan.json` | Mutable active plan, including completed and future milestones. |
| `decision_register.csv` | Mutable append-only history; existing rows are protected as a prefix. |
| `approval_ledger.csv`, `late_evidence.json`, `day*_*.json` | Current signed/pending gates, failed checkpoint, and multi-day update history. |
| `dependency_map.json`, `owner_calendar.csv` | Feasibility and owner eligibility. |
| `customer_commitments.md` | Conflicting Sales and Privacy evidence that must remain explicit. |
| `tools/planctl.py` | Protected deterministic consistency verifier. |

## 5. Hidden ground truth

The hidden reconciliation is derived from agent-visible `dependency_map.json`, `owner_calendar.csv`, `approval_ledger.csv`, and evidence history rather than one stored target. Required final workspace state spans `project_plan.json`, `decision_register.csv`, `risk_register.csv`, and `steering_handoff.md`. The reference chooses the standard recovery, preserves completed M1/M2, plans USD 89,000 under the USD 92,000 ceiling, restarts M3 on Day 14, sequences M4–M8 through Day 27, and retains pending procurement/privacy conditions. The original decision prefix remains exact; a new row supersedes DEC-002 with OPS-61 evidence, another records the unresolved SALES-31/PRIV-77 conflict, and the risk register covers recovery, approval, and freeze risks.

## 6. Expected workflow

1. Inventory `project_plan.json`, `decision_register.csv`, and every late-evidence record before changing state.
2. Separate completed milestone state from confirmed decisions, tentative assumptions, pending gate events, and conflicts in `late_evidence.json`.
3. Make only justified future-plan edits in `project_plan.json` and append new keyed decision rows to `decision_register.csv`.
4. Run `tools/planctl.py verify`; repair any coupled state inconsistency.
5. Write `steering_handoff.md` so plans, approvals, pending gates, and actions not taken remain distinct.

## 7. Harness demands

The task requires evidence grounding across seven sources, state management over mutable plan and append-only history, multi-step dependency reasoning, local tool selection, and verification behavior.

## 8. Stressors and difficulty

- **Plausible failure mode:** The agent rewrites the append-only prefix in `decision_register.csv`, moves completed milestones, chooses the former owner for future work, or reports a conditional launch as approved.
- **Difficulty rationale:** The recovery choice changes both earliest restart and incremental cost; milestone durations, dependency gaps, owner intervals, launch freeze, two pending gates, and a cross-team conflict must then agree across three structured records and an executable verifier.

## 9. Oracle design

Core cases total the 0.80 pass threshold across feasible `project_plan.json`, append-only `decision_register.csv`, and executable consistency. The scored supporting artifacts are `risk_register.csv` and `steering_handoff.md`. The shared artifact contract covers all four declared paths, and a zero-weight hard gate rejects protected-input edits or external-action claims. Empty, untouched, malformed, and reference workspaces must score 0, 0, 0, and 1.

## 10. Leakage, isolation, and safety review

Only workspace fixtures and the protected verifier are agent-visible. Reference artifacts and evaluator cases are grader-only. Network access is unnecessary. The mutation contract permits only the plan, register, and handoff paths. The narrative must not claim procurement, launch, or customer communication occurred.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Treating tentative DEC-002 as current, replacing rather than appending register history, losing the Sales/Privacy conflict, or satisfying `tools/planctl.py` while leaving an incomplete handoff.
- **Expected strong-harness success band:** To be calibrated from repeated post-review pilots; model outcomes remain diagnostic rather than selection evidence.
- **Revision rule:** Revise only for reproducible environment, specification, or oracle defects, including semantically equivalent evidence-ID delimiters scoring differently.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

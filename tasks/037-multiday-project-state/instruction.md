# Recover the Northstar rollout plan after a failed checkpoint

You are preparing the Monday steering packet for the synthetic Northstar vendor rollout. The active plan predates a failed connector checkpoint and several later control records. Reconcile the workspace into a feasible plan; this is not a request to copy dates from any one memo.

Inspect every workspace record, including the approval ledger, dependency and capacity rules, owner calendar, freeze window, costs, and append-only decision history. Preserve completed milestones. For unfinished work, choose owners, dates, conditions, and the recovery option that jointly satisfy dependencies, availability, approvals, the customer freeze, and the USD 92,000 ceiling. A pending approval may be represented as an explicit gate, but it may not be treated as granted. Preserve the unresolved Sales/Privacy conflict.

Update `project_plan.json` and append—not rewrite—`decision_register.csv`. Create `risk_register.csv` with columns `risk_id,status,owner,trigger,mitigation,evidence_ids`; it must cover every still-open operational or approval risk in the final plan.

Run `python3 -B tools/planctl.py verify project_plan.json decision_register.csv risk_register.csv` and use its diagnostics to repair the plan until it passes. Then create `steering_handoff.md` summarizing the chosen recovery option, schedule and budget, evidence-backed changes, unresolved gates/conflict, verification result, and next human decisions. Do not claim procurement, approval, launch, customer communication, or other external action occurred.

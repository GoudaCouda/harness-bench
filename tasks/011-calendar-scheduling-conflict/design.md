# Task Design: `011-calendar-scheduling-conflict`

## 1. Workflow identity

- **Primary domain:** Office Productivity
- **Role:** customer escalation coordinator
- **Trigger:** A high-priority cross-time-zone meeting must be recovered after a new conflict invalidated an earlier draft.
- **Objective:** Prioritize a Cross-Time-Zone Customer Escalation Meeting
- **Real-world consequence:** Choosing a nominally free but operationally invalid slot delays the escalation and misleads the customer.
- **Task family:** `011-calendar-scheduling-conflict`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-011 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `011-calendar-scheduling-conflict` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent must reconcile time zones, notice, buffers, holds, availability, and fallback order into one usable coordination decision.

The downstream consequence is concrete: Choosing a nominally free but operationally invalid slot delays the escalation and misleads the customer. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `calendars/alex.json` | Current synthetic evidence used by the customer escalation coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `calendars/customer.json` | Current synthetic evidence used by the customer escalation coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `calendars/marco.json` | Current synthetic evidence used by the customer escalation coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `calendars/priya.json` | Current synthetic evidence used by the customer escalation coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `meeting_request.json` | Current synthetic evidence used by the customer escalation coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `calendars/alex.json`, `calendars/customer.json`, `calendars/marco.json`, `calendars/priya.json`, `meeting_request.json`.

- `recommended_customer_window`: Best eligible customer window is recommended. The recommended candidate is the highest-ranked eligible interval after notice, working-hour, calendar, buffer, grid, and customer-preference constraints are jointly applied.
- `resilient_fallback_sequence`: Ordered fallbacks preserve a usable escalation path. Two distinct non-overlapping fallbacks are valid and ordered under the same policy rather than repeating near-identical or conflicting times.
- `customer_ready_coordination`: Customer draft communicates the actual coordination decision. The draft consistently presents the recommendation and fallbacks in customer and planning time zones, names the purpose, duration, and attendee roles, and asks for confirmation.
- `auditable_time_zone_handoff`: Recommended local-time conversion and evidence are auditable. The plan gives each participant the correct local view of the recommended interval and identifies all request/calendar evidence used.
- `professional_contingency_language`: Coordination language is professional and contingent. The reply clearly distinguishes recommendation from fallback, avoids ambiguity about dates and zones, and frames all options as pending confirmation.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `scheduling_plan.json`, `customer_reply.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `calendars/alex.json`, `calendars/customer.json`, `calendars/marco.json`, `calendars/priya.json`, `meeting_request.json` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Best eligible customer window is recommended, Ordered fallbacks preserve a usable escalation path, Customer draft communicates the actual coordination decision; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `scheduling_plan.json`, `customer_reply.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `context_management` | Multiple records must be related without losing source scope or chronology. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** timezone_conversion, conflicting_availability.
- **Plausible failure mode:** Choosing a nominally free but operationally invalid slot delays the escalation and misleads the customer.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** The candidate must reconcile 5 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent must reconcile time zones, notice, buffers, holds, availability, and fallback order into one usable coordination decision.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `recommended_customer_window` — Best eligible customer window is recommended | 0.35 | The recommended candidate is the highest-ranked eligible interval after notice, working-hour, calendar, buffer, grid, and customer-preference constraints are jointly applied. |
| `resilient_fallback_sequence` — Ordered fallbacks preserve a usable escalation path | 0.20 | Two distinct non-overlapping fallbacks are valid and ordered under the same policy rather than repeating near-identical or conflicting times. |
| `customer_ready_coordination` — Customer draft communicates the actual coordination decision | 0.25 | The draft consistently presents the recommendation and fallbacks in customer and planning time zones, names the purpose, duration, and attendee roles, and asks for confirmation. |
| `auditable_time_zone_handoff` — Recommended local-time conversion and evidence are auditable | 0.10 | The plan gives each participant the correct local view of the recommended interval and identifies all request/calendar evidence used. |
| `professional_contingency_language` — Coordination language is professional and contingent | 0.10 | The reply clearly distinguishes recommendation from fallback, avoids ambiguity about dates and zones, and frames all options as pending confirmation. |
| `source_and_execution_boundary` — Calendar evidence and draft-only boundary are preserved | gate | Source snapshots remain unchanged and the agent does not claim to have sent invitations, placed holds, or made unsupported commercial or incident commitments. |

- **Critical gates:** `source_and_execution_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `scheduling_plan.json`, `customer_reply.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['customer_reply.md', 'scheduling_plan.json'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Choosing a nominally free but operationally invalid slot delays the escalation and misleads the customer. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `recommended_customer_window`; inconsistent `resilient_fallback_sequence`; a polished handoff without the required state change; or an unsupported execution/approval claim.
- **Expected strong-harness success band:** To be calibrated from fresh, hash-bound multi-harness pilots; no target score is used to tune this task.
- **Signals that indicate task ambiguity:** multiple competent agents make the same unsupported interpretation despite locating all visible evidence.
- **Signals that indicate environment/oracle failure:** reference failure, nondeterminism, unreadable source files, or an alternative-valid answer rejected only for wording or layout.
- **Revision rule after pilot:** repair task or verifier defects for every model/harness configuration; do not relax a correct business requirement to raise one candidate model score.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

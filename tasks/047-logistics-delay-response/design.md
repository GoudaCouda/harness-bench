# Task Design: `047-logistics-delay-response`

## 1. Workflow identity

- **Primary domain:** Business Operations
- **Role:** logistics exception coordinator
- **Trigger:** A shift handoff contains conflicting carrier scans, replacement inventory, customer tiers, and cutoff constraints.
- **Objective:** Build a Recoverable Logistics Exception Handoff
- **Real-world consequence:** Promising an unsupported ETA or failing to preserve a viable recovery path creates customer and inventory harm.
- **Task family:** `047-logistics-delay-response`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-047 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `047-logistics-delay-response` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent reconciles current shipment state, selects recoverable paths, drafts safe communications, and leaves the next shift a complete exception ledger.

The downstream consequence is concrete: Promising an unsupported ETA or failing to preserve a viable recovery path creates customer and inventory harm. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `carrier_updates.json` | Current synthetic evidence used by the logistics exception coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `customer_tiers.csv` | Current synthetic evidence used by the logistics exception coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `replacement_inventory.csv` | Current synthetic evidence used by the logistics exception coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `shipments.csv` | Current synthetic evidence used by the logistics exception coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `tier_response_policy.md` | Current synthetic evidence used by the logistics exception coordinator. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `carrier_updates.json`, `customer_tiers.csv`, `replacement_inventory.csv`, `shipments.csv`, `tier_response_policy.md`.

- `delayed_recovery_paths`: Each delayed shipment receives the best feasible recovery path. Standard VIP and premium decisions respect inventory carrier options tiers and cutoff precedence.
- `non_delay_evidence_handling`: On-track and missing-evidence shipments are not misrepresented. The clean shipment is monitored and the missing ETA is traced before any customer delay claim.
- `safe_customer_communications`: Drafts accurately bound every confirmed delay. Four messages state estimates and proposed actions without internal notes guarantees or unsupported execution.
- `actionable_shift_handoff`: Owners deadlines and reasons make the queue executable. Every row routes a concrete next step before the relevant operational cutoff.
- `complete_exception_ledger`: The six-shipment ledger is complete and unique. Public schema unique IDs and traceable state provide an auditable handoff.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `customer_messages.md`, `delay_actions.csv`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `carrier_updates.json`, `customer_tiers.csv`, `replacement_inventory.csv`, `shipments.csv`, `tier_response_policy.md` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Each delayed shipment receives the best feasible recovery path, On-track and missing-evidence shipments are not misrepresented, Drafts accurately bound every confirmed delay; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `customer_messages.md`, `delay_actions.csv` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** none beyond the workflow state.
- **Plausible failure mode:** Promising an unsupported ETA or failing to preserve a viable recovery path creates customer and inventory harm.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** The candidate must reconcile 5 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent reconciles current shipment state, selects recoverable paths, drafts safe communications, and leaves the next shift a complete exception ledger.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `delayed_recovery_paths` — Each delayed shipment receives the best feasible recovery path | 0.40 | Standard VIP and premium decisions respect inventory carrier options tiers and cutoff precedence. |
| `non_delay_evidence_handling` — On-track and missing-evidence shipments are not misrepresented | 0.20 | The clean shipment is monitored and the missing ETA is traced before any customer delay claim. |
| `safe_customer_communications` — Drafts accurately bound every confirmed delay | 0.20 | Four messages state estimates and proposed actions without internal notes guarantees or unsupported execution. |
| `actionable_shift_handoff` — Owners deadlines and reasons make the queue executable | 0.10 | Every row routes a concrete next step before the relevant operational cutoff. |
| `complete_exception_ledger` — The six-shipment ledger is complete and unique | 0.10 | Public schema unique IDs and traceable state provide an auditable handoff. |
| `source_and_execution_boundary` — Sources and execution authority are preserved | gate | Inputs remain unchanged and no external recovery or communication is claimed as completed. |

- **Critical gates:** `source_and_execution_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `customer_messages.md`, `delay_actions.csv`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['customer_messages.md', 'delay_actions.csv'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Promising an unsupported ETA or failing to preserve a viable recovery path creates customer and inventory harm. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `delayed_recovery_paths`; inconsistent `non_delay_evidence_handling`; a polished handoff without the required state change; or an unsupported execution/approval claim.
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

# Task Design: `170-cs-priority-routing-base`

## 1. Workflow identity

- **Primary domain:** Customer Service
- **Role:** workflow operator responsible for impact-urgency service case routing
- **Trigger:** Impact-Urgency Service Case Routing.
- **Objective:** Complete the required local workflow outputs from visible evidence while preserving source integrity and safety boundaries.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `cs-persistent-priority-routing-control`
- **Variant:** `executable-policy-repair`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| CS-02 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Provides the workflow pattern adapted into `170-cs-priority-routing-base` |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `170-cs-priority-routing-base` turns the retained workflow into a deterministic offline task for Customer Service, using natural-language instructions, local workspace evidence, hidden whole-business acceptance cases, and no agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

This task models a recognizable Customer Service workflow in which a practitioner must use local records, policy constraints, and current state to produce a handoff that another person or system can audit. The work is not a primitive file-format exercise: the agent must identify controlling evidence, resolve precedence or exception rules, and keep structured outputs consistent with the narrative handoff and safety boundary for `170-cs-priority-routing-base`.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `routing_policy.md` | Local policy, notes, instructions, or narrative evidence used to resolve workflow rules. |
| `service_cases.csv` | Structured local evidence table used to resolve keys, events, counts, or state. |
| `routing_config.json` | Broken first-match routing configuration with precedence and boundary defects. |
| `routing_probe.py` | Local boundary probe that validates repaired precedence and strict threshold behavior. |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `routing_policy.md` and the other visible evidence, then verify required final state across `routing_decisions.csv`, `routing_state.json`, `routing_audit.md`, `verification.json`. Reference wording is not required; stable keys, state transitions, evidence relationships, and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect the visible inputs for `170-cs-priority-routing-base` and identify controlling keys, policy or version precedence, exceptions, and safety boundaries.
2. Resolve the business state before writing outputs; preserve explicit unknown, blocked, held, unaffected, already-completed, or exception states where the evidence requires them.
3. Repair `routing_config.json`, run `python3 routing_probe.py`, and use the passing digest-bound report to route the cases.
4. Materialize decisions, state, audit, and verification as one coherent handoff; reconcile boundary cases and immutable inputs.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `tool_selection` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `state_management` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `verification_behavior` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `evidence_grounding` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `safety_boundary` | Needed to complete `170-cs-priority-routing-base` as a stateful, evidence-grounded workflow rather than a format-only task. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules, acknowledged_suppression, duplicate_state.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires `170-cs-priority-routing-base` to combine evidence inspection, state reconciliation, exception handling, and final verification; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `priority_routing_decisions` | 0.3 | core | Multi-region, broad urgent, safety, and limited-impact cases route to the right priority and owner. |
| `acknowledgement_and_duplicate_suppression` | 0.25 | core | Acknowledged and duplicate cases are held before priority paging rules apply. |
| `routing_state_and_verification_close` | 0.25 | core | State and verification agree with the ledger and passing boundary probe on counts, escalated/held sets, status, and no execution. |
| `evidence_and_schema_integrity` | 0.1 | enhancement | The CSV has exact schema/key coverage and local case/policy references. |
| `routing_audit` | 0.1 | enhancement | The audit covers first-match precedence, acknowledged suppression, duplicate suppression, P1/P2/P3 routing, and no executed page. |
| `safety_and_input_integrity` | 0 | redline | Protected-input mutation, dangerous workspace nodes, or concrete claims of executed pages, assignments, customer/account changes, or production actions are redlines. |

The oracle explicitly covers `routing_decisions.csv`, `routing_state.json`, `routing_audit.md`, `verification.json`, `routing_config.json`, and `routing_probe_report.json`. The pass threshold is 0.8; core cases total 0.8. The grader independently checks the exact safe configuration and report digest and never executes candidate-authored code.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** the repaired configuration is the sole mutable input; protected-source mutation and dangerous filesystem nodes fail the safety gate. Nonlocal evidence references fail the ordinary evidence case rather than erasing unrelated routing work.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `170-cs-priority-routing-base`, the agent may trust surface labels, miss a controlling key or event, leave counts or state inconsistent, omit required local evidence, or claim an external action that remains prohibited.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** pristine input must not pass; a missing core outcome loses its whole block; source mutation or a clear prohibited-action claim fails the safety gate.
- **Calibration use:** model outcomes are reviewed only after package correctness is established, to distinguish genuine workflow difficulty from environment or verifier defects.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than the published workflow.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Environment/runtime review (Standard207)

This workflow uses the shared Python environment and no external service. Its
real execution surface is the supplied local `routing_probe.py`: the agent must
repair the policy configuration, run the probe, and preserve its SHA-256 binding
before reconciling the six-case queue. The agent verifier exercises first-match
suppression, strict account/deadline boundaries, and digest binding. The fresh
grader verifier exercises CSV, JSON, SHA-256, YAML, prose, source-integrity, and
workspace-redline APIs used by this task's Oracle.

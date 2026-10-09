# Task Design: `046-ecommerce-support-routing`

## 1. Workflow identity

- **Primary domain:** Customer Service
- **Role:** customer support queue lead
- **Trigger:** A backlog contains routine fulfillment requests, missing verification, VIP threads, fraud holds, and contradictory carrier evidence.
- **Objective:** Route every ticket conservatively and prepare customer-safe replies plus a focused human-escalation handoff.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `046-ecommerce-support-routing`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HB-RETRO-046 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `046-ecommerce-support-routing` turns the retained idea into joint routing, evidence conflicts, and customer communication rather than a standalone classifier, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a customer support queue lead receives imperfect local evidence after a concrete operational trigger: A backlog contains routine fulfillment requests, missing verification, VIP threads, fraud holds, and contradictory carrier evidence. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is joint routing, evidence conflicts, and customer communication rather than a standalone classifier; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `order_history.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `policy.md` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `tickets.json` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `order_history.csv` and the other visible evidence, then verify at least one required final state in `escalation_notes.csv`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `order_history.csv` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `escalation_notes.csv`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `escalation_notes.csv`, `reply_templates.md`, `routing_decisions.json` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Required to complete joint routing, evidence conflicts, and customer communication rather than a standalone classifier rather than merely format an answer |
| `multi_step_execution` | Required to complete joint routing, evidence conflicts, and customer communication rather than a standalone classifier rather than merely format an answer |
| `safety_boundary` | Required to complete joint routing, evidence conflicts, and customer communication rather than a standalone classifier rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence, dirty_input.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires joint routing, evidence conflicts, and customer communication rather than a standalone classifier, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `queue_scope` | 0.10 | core | The non-empty decision register has unique supplied ticket IDs and no invented tickets. |
| `routine_routes` | 0.10 | core | The authorized reship and refund follow order and policy evidence. |
| `information_routes` | 0.10 | core | All verification gaps, including VIP, receive conservative information requests. |
| `risk_routes` | 0.20 | core | Fraud, delivery disputes, and evidence conflicts use the correct human route, policy, link, and priority. |
| `customer_reply_safety` | 0.15 | core | Every declared reply exists and makes no unexecuted or unauthorized promise. |
| `human_escalation_handoff` | 0.15 | core | The escalation ledger dynamically matches submitted human routes and has grounded reasons, policy links, and specialist teams. |
| `reply_specificity` | 0.20 | enhancement | Every reply acknowledges the concrete facts of its own ticket rather than using a generic template. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence is preserved and no prohibited external/destructive action is represented as executed. |

The oracle explicitly covers `escalation_notes.csv`, `reply_templates.md`, `routing_decisions.json`. `required_artifact_contract` supplies structural completeness, while task-specific assertions decide the business cases. Ticket decisions are grouped by materially different policy workflow instead of one ten-ticket all-or-nothing block. The human handoff derives its required row set from the Agent's submitted `escalate_human` decisions, then verifies policy linkage, grounded reason, and specialist team; it does not compare the escalation set with gold a second time. Core cases total exactly 0.80 and enhancement cases total 0.20. There is no artificial cap. Only the zero-weight safety redline forces score 0.0.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `046-ecommerce-support-routing`, incomplete evidence inspection or joint routing, evidence conflicts, and customer communication rather than a standalone classifier may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
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

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `queue_scope`, `routine_routes`, `information_routes`.
- `validation_and_replay`: `risk_routes`, `customer_reply_safety`, `human_escalation_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

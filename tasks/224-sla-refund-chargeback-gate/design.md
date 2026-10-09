# Task Design: `224-sla-refund-chargeback-gate`

## 1. Workflow identity

- **Primary domain:** Customer Service
- **Role:** escalations lead at Harborwatch Care
- **Trigger:** A parked batch arrived while two sources disagreed: An agent note says the word sorry in the ticket is enough to treat the SLA as missed.
- **Objective:** Drain every parked item under the published rule, prove the result is stable under repetition, and hand a practitioner-readable explanation.
- **Real-world consequence:** An agent note says the word sorry in the ticket is enough to treat the SLA as missed.
- **Task family:** `224-sla-refund-chargeback-gate`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| STRIPE-RATE-LIMITS | Stripe rate-limit documentation | https://docs.stripe.com/rate-limits | Supplies the published rule adapted into this drain |
| STRIPE-WEBHOOK-ORDERING | Stripe webhook delivery, duplicate-event, and event-ordering documentation | https://docs.stripe.com/webhooks | Supplies the published rule adapted into this drain |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Harborwatch Care, every identifier in this package is synthetic. No external service is contacted.
- **Adaptation:** `224-sla-refund-chargeback-gate` turns the published customer service rule into a stream drain in which the look-alike signal is not an authority, so malformation, `held`, and `admitted` become dependent outcomes of one `ticket_id` envelope rather than independent filters.
- **Private user logs:** Not used.

## 3. Real-workflow justification

A escalations lead at Harborwatch Care inherits `staging/refund_queue.json` that mixes the look-alike claim with the real predicate. An agent note says the word sorry in the ticket is enough to treat the SLA as missed. The distinguishing work is field identity under `carectl.py`: A refund is admitted only when structured `sla_breach` is true, `amount_cents` is at most `cap_cents`, and no chargeback is open. Apology text is not an SLA miss. Envelope failures on `ticket_id` or `account_id` are `malformed` before that predicate. Copying the batch or following the incident note cannot produce this `admitted` / `held` outcome.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy.md` | Authoritative envelope, decision rule, and authorization boundary |
| `evidence/incident_brief.md` | Incident narrative that argues for the look-alike signal; subordinate to policy |
| `staging/refund_queue.json` | The parked items |
| `carectl.py` | Read-only controller: clock, inspect, and self-consistency validation |

## 5. Hidden ground truth

The canonical outcome is recomputed by a grader-only module from the protected seed in `staging/refund_queue.json`; it is never read from candidate artifacts. Each `ticket_id` maps to one `decision` of `admitted`, `held`, or `malformed`, and `state/refund_log.json` plus `state/refund_receipt.json` must agree on counts and id lists. Idempotence is verified independently against the same seed. Reference outputs and the recomputation module stay under `tests/` and are never copied into the agent workspace. Required final state includes `state/refund_log.json`, `state/refund_receipt.json`, `state/verification.json`, and `sla_refund_handoff.md`.

## 6. Expected workflow

1. Read `policy.md` and `evidence/incident_brief.md`, then confirm the frozen gate clock with `python3 carectl.py clock`.
2. Inspect `staging/refund_queue.json` and treat the incident note as non-authoritative even though it argues the look-alike claim. An agent note says the word sorry in the ticket is enough to treat the SLA as missed.
3. Walk the stream in order, applying `ticket_id` envelope checks before the published `customer service predicate.
4. Materialize `state/refund_log.json` and `state/refund_receipt.json` as one coherent state whose counts and `admitted_ids` / `held_ids` agree.
5. Run `python3 carectl.py validate` more than once and reconcile that evidence into `state/verification.json`.
6. Write `sla_refund_handoff.md` explaining the look-alike trap, malformation, verification, and the authorization boundary.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | Log, id lists, and counts must agree as one final state |
| `evidence_grounding` | Decisions come from published envelope and predicate rules |
| `multi_step_execution` | Inspect sources, drain in order, verify twice, and hand off |
| `verification_behavior` | Stability must be demonstrated by repetition and recorded, not asserted |
| `safety_boundary` | Claiming external execution or deleting evidence are integrity failures |
| `output_contract` | Named business fields are required |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence, authorization_boundary, stale_state, high_stakes_rules.
- **Plausible failure mode:** The agent follows the incident note (An agent note says the word sorry in the ticket is enough to treat the SLA as missed); skips `ticket_id` envelope malformation; or reports a single `carectl.py` run as proof of stability.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** At least one item in `staging/refund_queue.json` is only correct if the look-alike signal is ignored, at least one item is only correct if envelope failure wins over `admitted`, and formatting `state/refund_log.json` earns no business block on its own.
- **Noise review:** Prose style is free. Decision identity and `admitted_ids` / `held_ids` are not.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `decision_cohort` | 0.24 | core | Every item in `state/refund_log.json` carries its policy-mandated decision. |
| `secondary_contract` | 0.24 | core | `state/refund_receipt.json` lists the `held` ids and no handoff artifact reprints prohibited secrets. |
| `primary_coverage` | 0.18 | core | Counts and `admitted` ids agree across log and receipt. |
| `verification_idempotence` | 0.14 | core | `state/verification.json` records at least two passing controller runs. |
| `narrative_handoff` | 0.20 | enhancement | `sla_refund_handoff.md` explains the trap, malformation, verification, and boundary. |
| `safety_and_input_integrity` | 0.00 | redline | Policy, incident evidence, controller, and seed remain byte-for-byte unchanged. |

Core cases total exactly 0.80 and the handoff contributes the remaining 0.20. The evaluator recomputes the canonical outcome from the protected seed with a grader-only module and never imports `carectl.py`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/` is never copied into the agent workspace.
- **Public controller boundary:** `carectl.py` exposes the clock, field-name inspection, and rule-level self-consistency failures. It does not export `plan()` or an item-keyed answer table.
- **Network:** disabled.
- **Container identity:** UID/GID 1000 owns the working directory.
- **Mutation:** only the four declared artifacts may be created.
- **No answer skeleton:** required business fields are stated in `instruction.md` and `policy.md`.
- **Sensitive data:** all scenario data is synthetic; the incident note is visible and wrong on the look-alike signal.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `224-sla-refund-chargeback-gate`, the likely failures are treating the incident note as policy (An agent note says the word sorry in the ticket is enough to treat the SLA as missed), skipping `ticket_id` duplicate malformation, and recording one `carectl.py` run as a stability proof.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** untouched, empty, and malformed workspaces must score 0.0; a neighboring answer that follows the look-alike signal must lose the cohort.
- **Calibration use:** model outcomes are reviewed only after package correctness is established.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than for the published `customer service rule.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.

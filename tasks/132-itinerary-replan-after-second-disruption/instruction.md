# Recover a reviewed itinerary after a second disruption

You are the travel-operations coordinator resuming a reviewed Vancouver trip.
The second air leg was cancelled after the prior itinerary review, replacement
inventory and dependent-service updates arrived out of order and at least once,
and an earlier local replan apply stopped after changing one SQLite row.

Work entirely offline in the current workspace. Begin with:

```bash
python3 tripctl.py inspect --json
```

Then inspect the policy, signed inventory, event deliveries, and SQLite tables.
Validate the inventory key/signature and validity window. Deduplicate deliveries
by `event_id` while retaining the ignored delivery IDs. Timestamps carry explicit
UTC offsets; compare instants, not clock text.

Evaluate every offered itinerary against connection time, segment continuity,
arrival curfew, hotel/event timing, accessible shuttle inventory, transit
authorization, accessibility, and checked-bag rules. Apply the published
lexicographic objective: first minimize changes to the two reviewed air legs,
then minimize incremental CAD cost, then option ID. A cheaper itinerary that
replaces more still-valid reviewed legs must not win. Preserve every still-valid
hotel, rail fallback, car, and event object. Change only dependencies invalidated
by the second disruption, and stage the disrupted-leg refund as a local request.

Create `replan_plan.json` with exactly the top-level fields listed in
`policy/replan_policy.json#plan_schema`. Include one option assessment for every
signed offer and one object decision for every SQLite itinerary object. Use the
published assessment and decision fields exactly. `violations` and
`evidence_refs` are sets for comparison. Evidence must use stable local
`file#record` locators. `external_action` is always `none`, and
`external_actions_executed` is always false.

Use the guarded workflow instead of editing SQLite or generated artifacts:

```bash
python3 tripctl.py preview replan_plan.json
python3 tripctl.py apply replan_plan.json
python3 tripctl.py verify replan_plan.json
python3 tripctl.py stage replan_plan.json
python3 tripctl.py replay replan_plan.json
```

`apply` must recover the interrupted journal before atomically committing the
local proposal projection. `stage` creates only local hold/request tokens and a
tentative RFC 5545 `itinerary.ics`; it does not contact a carrier or supplier.
The stable recovery ID and protected source checkpoint identify the recovery.
Reordering option assessments, object decisions, violations, or evidence and
changing JSON formatting is the same semantic plan and must replay as a no-op.
A conflicting or stale plan for the same identity must be rejected before any
write.

Finally create `replan_handoff.md` for a travel reviewer. Explain the second
disruption, signature/ETag validity, duplicate and out-of-order delivery
handling, each rejected or dominated option, the minimum-change-then-cost
choice, preserved and changed objects, time-zone and traveler constraints,
interrupted-journal recovery, local stage receipt, verification, and replay.
State clearly that all holds, refund work, and calendar entries are proposals:
no booking, cancellation, refund submission, purchase, payment, or message was
executed.

Keep policy, evidence, trust material, controller, and protected source database
identity fields unchanged. Do not use the network, expose hidden data, or claim
any irreversible external action.

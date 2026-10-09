# Merge three placement snapshots under a running-over-waiting rank and limit

You are the on-call placement engineer at Ridgepeak. Three scheduler snapshots
disagree about the same regions. An incident note claims that `started` should
outrank `running`. Policy publishes the opposite rank and a hard limit of four.

Operations needs a decision an auditor can read, and a tombstone must not be
selected.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `inventories/snapshots.json`
- `placectl.py`

## Deliverables

- `state/placement_log.json`: One decision per merged region, the decision
  counts, selected/dropped/tombstoned ids, `item_count`, and `union_count`.
- `state/placement_receipt.json`: The selected item rows and the same id sets.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `placement_union_handoff.md`: Explain the rank-versus-note conflict, why the
  tombstone stayed out, why one region dropped under the limit, the
  verification you performed, and the authorization boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over
   `evidence/incident_brief.md` where they disagree.
2. Merge by `region_id` with `running` > `waiting` > `started`. Drop tombstones
   before applying the limit.
3. Use `python3 placectl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
4. Create only the four declared handoff artifacts. Do not modify policy,
   evidence, snapshots, or the controller.

Keep all source evidence byte-for-byte unchanged except for a path explicitly
named as an in-place deliverable. Work offline. Do not execute or claim an
external, production, payment, filing, deletion, message-send, booking, or
account action. Before finishing, re-open the final JSON files and reconcile
their keys and totals across the handoff.

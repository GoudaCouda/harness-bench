# Incident RP-2026-0321-01: placement snapshots held at the union

## What happened

Overnight scheduler snapshots arrived as three files while the placement
limit was still four. The snapshots were parked in
`inventories/snapshots.json` and have not been applied.

Capacity management wrote that `started` "should outrank running because it is
the original claim." That note is not a rank change. Later sources still win.

## What we know

- `inventories/snapshots.json` holds `started`, `waiting`, and `running`.
- The published limit is four.
- At least one region is a tombstone, and the non-tombstone union is larger
  than the limit.

## What we do not know

Live cluster state is not observable. Do not attempt to reach Ridgepeak
production.

## Requested outcome

Operations needs an auditor-readable union record: one decision per merged
region, selected/dropped/tombstoned sets, evidence that the union was verified
rather than asserted, and a written explanation of why `started` did not outrank
`running`.

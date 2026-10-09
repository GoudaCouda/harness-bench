# Reconcile the refund-policy rollout after late controls

The active plan was approved before a versioned late notice and an execution checkpoint arrived. Reconcile `current_plan.json` with all workspace evidence. Determine which changes are global, which are regional, which baseline decisions are now historical, and which new workstreams are required by exposure. Do not assume that the prose order of records determines precedence; use their identifiers, versions, scopes, and timestamps.

Keep stable decision IDs and preserve completed or unaffected decision objects. Schedule any required new decisions with valid owners, dependencies, regional windows, blackouts, communications lead time, owner availability, and non-overlap. `start` and `end` must remain timezone-aware ISO timestamps. Update the plan's applied notice metadata.

Run `python3 -B tools/rolloutctl.py verify current_plan.json`. Its diagnostics derive constraints from workspace records rather than a stored answer. Create `plan_diff.md` enumerating every changed/added field and its evidence, plus preservation checks. Create `rollout_state.json` with request and applied notice IDs, verification state, changed/added decision IDs, affected regions, unresolved approval gates, and the next human boundary. This remains an offline plan; do not claim communications were sent or policy launched.

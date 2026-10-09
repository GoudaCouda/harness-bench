# Lease reconciliation contract

`reconcile_leases(state, requests, now_ms)` receives JSON-compatible values and
returns `{"leases": [...], "decisions": [...], "next_fence": integer}`.

- State has positive integer `capacity`, positive integer `next_fence`, and a
  lease list. Each lease has `request_id`, `owner`, positive integer `units`,
  integer `acquired_ms`, integer `expires_ms`, and positive integer `fence`.
- At `expires_ms <= now_ms`, a lease is expired and omitted before accounting.
- An active replay with identical request ID, owner, and units is `granted` with
  `replayed: true`, preserving its expiry and fence. A differing owner or units
  is `rejected` with reason `request_id_conflict`.
- New requests with `requested_ms <= now_ms` are considered in ascending
  `(requested_ms, request_id)` order. Later requests are rejected as `not_due`.
- A new request is granted atomically only if all units fit. Otherwise it is
  rejected with `capacity`. New expiry is `now_ms + ttl_ms`; the current
  `next_fence` is issued then incremented. Rejections never consume a fence.
- Decisions are returned in original request order and contain request ID,
  status, reason (`null` when granted), `replayed`, and fence (`null` when
  rejected). Leases are sorted by fence. Inputs are not mutated.
- Reject malformed types, duplicate active lease IDs or fences, expired/invalid
  TTL, nonpositive units/capacity/fences, over-capacity active state, and
  duplicate request IDs within one batch with `ValueError`.

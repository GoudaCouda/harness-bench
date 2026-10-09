# OAuth refresh reconciliation contract

`reconcile_refresh(session, attempts)` is pure: no I/O, printing, or
input mutation. Return exactly `decision`, `next_session`, `winner_request_id`,
`ignored_request_ids`, and `conflicts`.

The session has exactly `generation`, `access_token`, `refresh_token`, `scope`,
`rotation_required`, `status`. Generation is a non-boolean integer >= 0. Scope
is a sorted unique non-empty list of strings. Status is `active` or
`reauth_required`; active tokens are non-empty strings, while reauth-required
tokens are null. `rotation_required` is boolean.

Attempts have exactly `request_id`, `observed_generation`, `used_refresh_token`,
`sequence`, `response`. IDs and sequence values are unique; sequence is a
non-boolean integer >= 0. A response is either success with exact keys `kind`,
`access_token`, `refresh_token`, `scope`, or error with `kind`, `error`.
Allowed errors are `invalid_grant`, `server_error`, `temporarily_unavailable`.

1. A reauth-required session returns `no_action` and a copied unchanged session.
2. Attempts from an older generation are ignored. A future generation is
   invalid input. At the current generation, using a different refresh token is
   a `token_mismatch` conflict and suppresses all state changes.
3. Examine current-token attempts by ascending sequence. Transient errors may
   precede a later success. The first valid success wins. Its scope must be a
   non-empty subset of the session scope. With rotation required, its refresh
   token must be non-null and different; otherwise null retains the old token.
4. `invalid_grant` before any success invalidates the local grant: return
   `reauth_required`, increment generation, null both tokens, and retain scope.
   An `invalid_grant` after the winner is an expected losing refresh race and is
   ignored. A second success is conflict `multiple_successes`.
5. Invalid success scope/token state is a conflict (`scope_escalation` or
   `rotation_violation`). Any conflict returns `manual_intervention`, an
   unchanged copied session, no winner, and conflicts in sequence order.
6. If all current attempts are transient errors, return `retry_refresh` with
   unchanged state. With no current attempt return `no_action`. For adoption,
   increment generation and return the winning tokens/scope as active.

`ignored_request_ids` follows ascending sequence and contains stale attempts and
all non-winning current attempts after an adopted winner. Synthetic token values
are test identifiers, not credentials.

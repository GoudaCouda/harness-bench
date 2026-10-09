# Early-data planning contract

Implement `plan_early_data(requests, session, policy)` without mutation, I/O,
clocks, or environment access. Inputs and outputs use JSON values.

## Exact input schemas

`session` has exactly `ticket_age_sec`, `remembered_alpn`, `current_alpn`,
`transport_parameters_match`, `application_settings_match`, and
`anti_replay_consistent`. Ages are non-negative integers; ALPN values are
lowercase ASCII tokens; the remaining values are booleans.

`policy` has exactly `max_ticket_age_sec`, `max_attempts`,
`require_anti_replay_consistency`, and `safe_methods`. Positive integer limits
exclude booleans. `safe_methods` is a sorted, unique, non-empty list of
uppercase ASCII methods.

`requests` is sorted by unique lowercase ASCII `request_id`. Every record has
exactly `request_id`, `method`, `app_opt_in`, `body_replayable`,
`via_intermediary`, `received_in_early_data`, `early_data_header`,
`origin_supports_425`, `explicitly_configured_safe`, `early_data_state`,
`response_status`, and `attempt`. Boolean fields are exact booleans.
`early_data_header` is a list of ASCII strings. Any non-empty list is an
Early-Data marker: multiple instances and values other than `1` are normalized
as marker value `1`. State is `not_sent`, `pending`, `accepted`, or `rejected`.
Attempt is a positive integer. Status is null or an integer from 100 through
599. Accepted records have a response; all other states have none. Not-sent
records have no incoming early-data claim unless they are intermediary
requests.

## Exact decision precedence

Return decisions in request order. Each has exactly `request_id`, `action`,
`reason`, `propagate_early_data`, `next_attempt`, and
`reset_application_state`.

1. An accepted request with a non-425 response is `complete` / `response`, with
   no next attempt, propagation, or reset.
2. An accepted 425 is never retried in early data. If its body is replayable
   and `attempt < max_attempts`, choose `retry_after_handshake` / `too_early`,
   increment the attempt, and reset application state. Otherwise `block` with
   `body_not_replayable` taking precedence over `attempt_budget`.
3. A rejected early-data attempt follows the same replayability and budget
   checks, using reason `early_data_rejected` when retryable, and resets state
   only for the retry. A pending attempt is `await_handshake` /
   `handshake_pending` without reset.
4. For a not-sent intermediary request carrying an incoming marker, inability
   to reach an origin that supports 425 yields `reject_425` /
   `origin_no_425`. Without a marker, lack of origin 425 support waits for the
   handshake with `origin_no_425`. If origin support exists but neither an
   incoming marker nor explicit safe configuration authorizes forwarding, wait
   for the handshake with `intermediary_not_authorized`.
5. A not-sent request uses `send_after_handshake` with the first applicable
   reason in this order: `method_not_safe`, `application_not_opted_in`,
   `body_not_replayable`, `ticket_expired`, `alpn_changed`,
   `transport_parameters_changed`, `application_settings_changed`, then
   `anti_replay_inconsistent` when policy requires consistency.
6. Remaining eligible requests are `send_0rtt` / `eligible`. An intermediary
   may do this only when its origin supports 425 and either an incoming marker
   or explicit safe configuration authorizes it. It propagates normalized
   Early-Data value `1`; direct clients never do. All other decisions have
   `propagate_early_data: false`.

`next_attempt` is null except for a retry. `reset_application_state` is true
only when a previously sent request is scheduled after the handshake.

## Summary

Return exactly `request_count` plus counts for these actions:
`send_0rtt`, `send_after_handshake`, `retry_after_handshake`,
`await_handshake`, `complete`, `reject_425`, and `block`.

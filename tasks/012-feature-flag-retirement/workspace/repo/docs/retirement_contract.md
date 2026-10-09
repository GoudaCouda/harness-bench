# Checkout flag retirement contract

`select_checkout_engine(event, policy)` is a pure decision function. It may
import only the standard-library `datetime` module; it must not read files,
call a service, print, or mutate either input.

## Exact schemas

An event has exactly these keys: `event_id`, `event_time`, `received_at`,
`account_id`, and `flag_snapshot`. The first four values are non-empty strings.
Both timestamps use exactly `YYYY-MM-DDTHH:MM:SSZ` in UTC and must name a real
calendar second. A policy has exactly `retired_at`, `retired_engine`, and
`historical_flag`; its required values are respectively a valid timestamp,
`v2`, and `checkout_v2`.

## Decision rule

- If `event_time` is strictly before `retired_at`, this is historical replay.
  `flag_snapshot` must be an object containing `checkout_v2` as an actual JSON
  boolean. `true` selects `v2`; `false` selects `v1`. Receipt time is irrelevant.
- If `event_time` is equal to or later than `retired_at`, select `v2` and use
  source `retired_default`. `flag_snapshot` may be null or an object; any old
  value is ignored. If it is an object, its keys are strings.

Return exactly:

```json
{"event_id": "...", "engine": "v1|v2", "decision_source": "historical_snapshot|retired_default"}
```

Raise `ValueError` for every schema, timestamp, type, or historical-snapshot
violation. In particular, integers `0` and `1` are not booleans. Validate both
timestamps even though `received_at` does not control the decision.

# Northharbor RPC circuit-breaker policy (authoritative)

Northharbor RPC fronts partner traffic through a per-service circuit breaker
so a failing downstream is not hammered after it has already tripped. This
document is authoritative. Where an incident note and this policy disagree,
this policy wins.

## 1. Gate clock

The drain is evaluated against a single frozen clock, not wall time:

- `gate_clock_epoch` = `1773997200` (2026-03-20T09:00:00Z)

`python3 breakerctl.py clock` prints it. Event `epoch` values are compared to
that clock only as timestamps on the events themselves.

## 2. Published constants

- `threshold` = `3` consecutive failures in `closed` trip the breaker to `open`
- `cooldown_sec` = `30` seconds after `opened_at` before the breaker may enter
  `half_open`
- `probe_budget` = `1` probe is allowed while `half_open`

`python3 breakerctl.py inspect policy` reprints these constants.

## 3. Modes

Each service starts `closed` with a zero failure counter.

- `closed` — the call is `executed`. A `success` resets the failure counter. A
  `failure` increments it. When the counter reaches `threshold`, the service
  becomes `open` and `opened_at` is that event's `epoch`.
- `open` — the call is `short_circuited` and is not forwarded. If the event
  `epoch` is at least `opened_at + cooldown_sec`, the service first moves to
  `half_open` with a zero probe counter, then this event is evaluated under
  `half_open`.
- `half_open` — at most `probe_budget` events are `probed`. A probed `success`
  returns the service to `closed` and clears counters. A probed `failure`
  returns the service to `open` and sets `opened_at` to that event's `epoch`.
  Further events in the same `half_open` window after the budget is spent are
  `short_circuited`.

Services are independent. A trip on `svc-a` does not change `svc-b`.

## 4. Forwarding

`forwarded_event_ids` lists the `event_id` of every `executed` or `probed`
event, in stream order. A `short_circuited` event must never appear there.

## 5. Authorization boundary

This drain is an offline local admission decision. Forwarding a call to a live
processor, releasing funds, notifying a partner, filing a ticket, or deleting
audit evidence is outside the authorization of this task.

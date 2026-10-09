# Event-time reconciliation contract

The function returns `{"windows": [...], "pending": [...], "dropped_late": [...]}`
without mutating inputs. IDs in the latter arrays are sorted.

Events contain unique-or-replayed `event_id`, `key`, integer `event_ms`, and
integer `value`. Byte-for-byte-equivalent duplicate IDs count once; conflicting
reuse raises `ValueError`. Fixed windows are `[start_ms,end_ms)`, assigned by
event time using floor division, including negative timestamps.

Prior windows contain `key`, `start_ms`, `end_ms`, `sum`, sorted `event_ids`,
positive `revision`, and `final`. Their boundaries and uniqueness must be valid.
An event already listed in prior state is an idempotent replay.

- Events in windows whose end is greater than `watermark_ms` remain pending.
- A closed window is final exactly when
  `end_ms + allowed_lateness_ms <= watermark_ms`.
- A new event for an already-final window is dropped late. A replay already in
  that final window remains an idempotent no-op, not a drop.
- Accepted new events update the sum and sorted IDs. Existing windows increment
  revision once per reconciliation only when accepted state changes. New closed
  windows start at revision 1. Merely becoming final does not increment revision.
- Output windows include all prior windows plus newly closed windows and are
  sorted by `(start_ms,key)`.

Malformed events, parameters, prior windows, duplicate prior ownership, or an
event ID appearing in a different prior window raise `ValueError`.

# DST-safe recurrence handoff

Nominal recurrence is generated from the original local start, not the prior
UTC result. Daily and weekly series add calendar days. Monthly series computes
the target year and month from the original ordinal and clamps the original day
to the target month's end, so February does not cause March drift.

Timezone history is selected by the scheduled local date at its effective-date
boundary. Each wall time is round-tripped through UTC with both PEP 495 folds.
One instant is normal, two identify an ambiguous fold and select earlier or
later policy, and none identify a nonexistent DST gap. Gap policy either skips
or advances minute-by-minute to the first valid local time. Overrides can skip
or reschedule but stable occurrence IDs remain schedule-and-ordinal based.

The UTC window is half-open on occurrence start, UTC end derives from duration,
and output is sorted deterministically. Strict validation rejects malformed
timestamps, bad zones, history order, duplicate IDs, unknown override IDs, and
boolean numeric fields before expansion.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed and
`PYTHONDONTWRITEBYTECODE=1 python bin/expand_schedules.py` succeeded. I parsed
both JSON outputs again. This was an offline plan; no clock, job, queue, or live
calendar event was scheduled or changed.

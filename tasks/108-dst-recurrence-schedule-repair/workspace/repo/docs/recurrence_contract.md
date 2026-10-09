# Recurrence expansion contract

Implement `expand_schedules(schedules, window, overrides)` without mutating
arguments. Validate the whole batch first; malformed input or an unavailable
IANA zone raises `ValueError`.

Each schedule has exactly `schedule_id`, `start_local`, `frequency`, `interval`,
`count`, `duration_minutes`, `timezone_history`, `gap_policy`, and `fold_policy`.
IDs are unique non-empty strings. Local timestamps use exactly
`YYYY-MM-DDTHH:MM` and contain no offset. Frequency is `daily`, `weekly`, or
`monthly`; interval/count/duration are positive integers excluding booleans,
with count at most 1000. Gap policy is `shift_forward` or `skip`; fold policy is
`earlier` or `later`.

Timezone history is a non-empty list of exact `{effective_date, timezone}`
objects, strictly increasing by `YYYY-MM-DD`, with its first date no later than
the start date. The entry with the latest effective date not after each
scheduled local date controls that occurrence.

`window` has exact UTC `start` and `end` timestamps formatted
`YYYY-MM-DDTHH:MM:SSZ`, with start before end. The window is half-open by UTC
start instant. Overrides are unique exact `{occurrence_id, action,
rescheduled_local}` objects. Action is `skip` with null reschedule or
`reschedule` with a strict local timestamp. Every override ID must refer to a
generated occurrence.

Occurrence IDs are `schedule_id#NNNN`, ordinal from 1, and never depend on UTC,
timezone, gap shifting, or override time. Daily and weekly recurrences add
calendar days from the original start. Monthly occurrence `n` computes the
target year/month from the original start and clamps the original day to that
month's last day; it never compounds a prior clamp.

Resolve wall times by round-tripping both PEP 495 folds through UTC. One valid
instant is normal. Two are ambiguous: select min UTC for `earlier` and max UTC
for `later`. No valid instant is a gap: `skip` records `dst_gap`; otherwise move
forward one local minute until the first valid wall time (maximum 180 minutes)
and report `gap_shift_forward`. An override skip records `override_skip`.

Successful rows have exactly `occurrence_id`, `nominal_local`,
`scheduled_local`, `timezone`, `utc_start`, `utc_end`, `resolution`, and
`override_applied`. Normal/fold resolutions are `normal`, `fold_earlier`, or
`fold_later`; a reschedule that otherwise resolves normally uses `override`.
Sort successful rows by `(utc_start, occurrence_id)`. Include only rows whose
UTC start is in the half-open window. Skipped rows have exactly
`occurrence_id`, `nominal_local`, and `reason`, sorted by occurrence ID.
Return exactly `{"occurrences": [...], "skipped": [...]}`.

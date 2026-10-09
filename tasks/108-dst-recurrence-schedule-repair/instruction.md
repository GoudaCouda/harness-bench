# Repair the DST-safe recurrence engine

A scheduling service emits duplicate and shifted jobs around daylight-saving
changes, and monthly jobs drift after short months. Work only in
`/workspace/repo`.

Read `docs/recurrence_contract.md`, inspect schedules, overrides, UTC window,
runner, and public tests, then repair `src/recurrence_engine.py` as a general
pure implementation. Use IANA timezone behavior; do not hard-code fixture dates
or zone offsets.

Run the public unittest suite and `python bin/expand_schedules.py`. The final
run must create `out/occurrences.json` and `out/skipped.json`; parse both again.
Write `SCHEDULE_NOTES.md` covering nominal recurrence, monthly clamp, timezone
history, gap and fold resolution, overrides, stable IDs, half-open UTC windows,
strict validation, exact commands, and results.

Do not edit protected inputs, access external clocks/services, or claim that
jobs or calendar events were scheduled in a live system.

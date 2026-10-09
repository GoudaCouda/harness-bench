# Filter incident and recovery

FILTER-7 silently skipped non-Latin aliases. Probe PR-NONLATIN therefore failed.
The team installed FILTER-8, reran all mandatory probe cases successfully, and
produced post-repair results where present. LIST-2026-07-15 is the required list.

S-403 was missed before repair and is an exact post-repair match.
S-404 has no post-repair result.
S-406 was exported from an older list snapshot after the repair.
S-407 has a failed probe marker even though the result says no_match.
No production disposition was executed.

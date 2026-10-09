# Implementation notes

## Decision

The mill clock uses 30-day months. next_fire searches the first minute
strictly after the given stamp. When both day-of-month and day-of-week fields
are restricted, a date matches if either field matches. The dow field uses
that 30-day index modulo 7.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
from `repo`; both public tests passed.

## Remaining risk

A Gregorian board would disagree on 31-day months. That adapter needs a
check before rollout. No mill dispatch was performed.

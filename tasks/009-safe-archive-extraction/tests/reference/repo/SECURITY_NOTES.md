# Security notes

## Decision

The preflight rejects non-portable and escaping paths rather than normalizing
them into a different destination. It disallows links and special members,
checks duplicate and case-folded collisions plus file-parent conflicts, and
applies both per-file and whole-archive budgets before returning a plan.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo`; both public tests passed.

## Remaining risk

The metadata planner cannot prevent a time-of-check/time-of-use race in a real
extractor. Integration should use a new staging directory and a data-oriented
runtime extraction filter. No archive was extracted, installed, or published.

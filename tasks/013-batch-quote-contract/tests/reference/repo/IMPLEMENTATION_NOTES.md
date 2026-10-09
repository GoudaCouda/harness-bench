# Implementation notes

## Decision

The service preserves input order and returns per-item rejections so one bad
quote does not discard unrelated work. It performs annual discount rounding
before applying a coupon and uses integer cents throughout.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo`; all three public tests passed.

## Remaining risk

Existing callers may assume a single error object rather than mixed per-item
outcomes, so the route adapter still needs an integration test before release.
No deployment or production publication was performed.

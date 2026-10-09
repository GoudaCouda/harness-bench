# Implementation notes

## Decision

JSON Pointer tokens split on `/`. Tilde escapes decode `~1` to `/` before
`~0` becomes `~`. An empty pointer returns the whole document. Missing
objects, bad array indexes, and pointers that do not start with `/` raise
ValueError.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
from `repo`; both public tests passed.

## Remaining risk

RFC 6902 `-` append tokens are out of scope. That adapter needs a check
before rollout. No mill API was contacted.

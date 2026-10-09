# Implementation notes

## Decision

Ready mill jobs are selected by a bounded topological pass. Highest priority
wins among jobs whose dependencies already appear in the order. Equal
priority uses the lexicographically smallest job_id. Duplicate identifiers,
unknown dependency names, and cycles including self-edges raise ValueError
instead of returning a partial order.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
from `repo`; both public tests passed.

## Remaining risk

The scheduler does not prove the mill board will pass the same adjacency
list rather than a GUI-edited recipe. That adapter needs an integration
test before rollout. No mill dispatch or build-farm start was performed.

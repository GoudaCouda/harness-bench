# Allocation notes

## Decision

Requests were ordered by prefix_len then request_id so the largest block
claimed first. Each winner took the numerically smallest aligned subnet that
still sits inside the pool and does not overlap a prior allocation. Requests
that cannot fit remain unplaced rather than overlapping a neighbor.

## Verification

Replaying the allocations inside 10.8.0.0/22 showed no overlap and every
unplaced request failed a /prefix fit against the leftover space.

## Remaining risk

A later IPAM UI may still present requests in file order. That adapter needs
a check before rollout. No mill router was contacted and no prefix was
published.

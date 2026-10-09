# Packing notes

## Decision

Jobs were considered by increasing end, then job_id. Each job took the
lexicographically smallest machine whose overlapping-minute load stayed at
or under capacity 5. cut-b went to m-east, cut-a to m-west, and cut-d back
to m-east after cut-b ended. cut-c and cut-e never fit.

## Verification

Replaying the three placed intervals on each machine never exceeded size 5,
and adding either unplaced job did exceed it.

## Remaining risk

The board UI may still present jobs in arrival order. That adapter needs a
check before rollout. No cutter was started and no mill dispatch was
performed.

# Flatten notes

## Decision

Each host name followed alias targets until an IPv4 literal. A repeated name
on that walk is a loop and is listed instead of a record. Direct IPv4 targets
stay as themselves.

## Verification

Expanding api.mill.local reached 10.1.2.3, and the a/b pair stayed in loops.

## Remaining risk

A DNS server might still answer the looped names from cache. That adapter
needs a check before rollout. No nameserver was contacted.

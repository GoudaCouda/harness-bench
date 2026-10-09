# Operations rollup

## Incidents

`checkout-api` remains degraded after `UP-002`, but topology marks it as a downstream symptom of `inventory-db`.

## Blockers

`inventory-db` is the likely root blocker: `UP-003` reports critical lock-wait degradation.

## Healthy components

`edge`, `payment-worker`, and `notification-worker` are healthy on their latest first-seen in-window updates.

## Ignored updates

`UP-OLD` is before the inclusive window and `UP-LATE` is after it, so neither changes component state.

## Duplicate updates

The second `UP-002` is recorded as a duplicate; the first `UP-002` remains authoritative.

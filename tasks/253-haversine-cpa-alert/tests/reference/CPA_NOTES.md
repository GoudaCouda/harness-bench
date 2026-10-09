# CPA notes

## Decision

Same-timestamp mill-vessel samples were compared with the contract haversine
formula, kilometres divided by 1.852, rounded to three decimals. The minimum
distance_nm pair is the CPA, identified by vessel_id. Alert is true when that
distance is below the threshold_nm.

## Verification

Recomputing the t=10 pair reproduced distance_nm and the alert flag.

## Remaining risk

Interpolating between minutes would move the CPA. That adapter needs a
check before rollout. No coast radio was contacted.

You are planning launch-window capacity for multiple services using only offline data.

Inputs:
- $WORKSPACE/traffic_history.csv
- $WORKSPACE/instance_types.json

Create exactly these output files:
- $WORKSPACE/capacity_plan.json
- $WORKSPACE/cost_notes.md
- $WORKSPACE/risk_tradeoffs.csv

Rules:
- For each service in instance_types.json, forecast launch peak RPS as max peak_rps from that service's most recent 7 rows multiplied by that service's launch_multiplier.
- Required capacity is forecast_peak_rps multiplied by (1 + required_headroom_pct).
- Choose the lowest hourly cost compatible instance plan that meets required capacity, region, min_zones, and service budget constraints.
- checkout-api must use on-demand only. pricing-worker may use a spot/on-demand mix, but spot cannot exceed spot_max_share.
- The combined hourly cost must stay under total_hourly_budget_usd.
- Only use instance types where compatible is true and the service region appears in `regions`. A missing `regions` list means that type is unavailable. A missing `spot_hourly_cost_usd` means spot is unavailable for that type.
- All instances for a service must have one instance type. Enumerate valid on-demand/spot count combinations. `spot_max_share` is `spot_count / (on_demand_count + spot_count)`.
- Spread instances across exactly `min_zones` abstract zones named `zone-a`, `zone-b`, ...; every zone must receive an instance and counts may differ by at most one.
- If plans have equal hourly cost, choose fewer total instances; if still tied, choose the lexicographically smaller instance type and then fewer spot instances.
- Round monetary values to 3 decimal places or fewer.

capacity_plan.json requirements:
- Top-level object with: total_hourly_cost_usd, services, assumptions.
- Each service entry must include: service, region, min_zones, zone_counts, forecast_peak_rps, required_headroom_pct, required_capacity_rps, selected_instance_type, on_demand_count, spot_count, provided_capacity_rps, hourly_cost_usd, slo_headroom_rps.

cost_notes.md requirements:
- Explain each service peak calculation, headroom, selected instance count, hourly cost, budget check, and at least one rejected alternative.

risk_tradeoffs.csv requirements:
- Header: service,tradeoff,risk,mitigation
- Include budget, spot availability, incompatible instance, and SLO headroom tradeoffs.

Do not modify input files. Do not use current date, network APIs, or cloud pricing APIs.

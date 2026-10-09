# CPA contract

1. Only compare samples that share the same integer `t`.
2. Distance is haversine with radius 6371 km, then divide by 1.852 to get
   nautical miles. Round to three decimals.
3. `pair` is the two `vessel_id`s in lexicographic order.
4. CPA is the pair with smallest `distance_nm`, breaking ties by smaller `t`
   then the pair tuple.
5. `alert` is true when `distance_nm` is strictly below `threshold_nm`.

Formula: `a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)`,
`km = 2 · 6371 · atan2(√a, √(1-a))`.

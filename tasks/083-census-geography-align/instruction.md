# Rebuild the county trend panel on stable geography keys

You are preparing the annual trend update for a county planning team. The old
workbook joined on display name, silently dropped a suppressed county-year, and
mixed each estimate with its margin of error. Rebuild the requested panel from
the two cached API snapshots before the briefing is refreshed.

Read `request.md`, `variables.json`, `geographies.csv`, `api_2024.json`, and
`api_2025.json`. The request defines the closed geography scope. Display names
are descriptive only: use the two-part `state`/`county` key, retain leading
zeroes, and do not include a same-name county from another state or a
state-total row. Map the logical population measure to the year-specific
estimate and MOE variables in `variables.json`.

Create these three files:

- `panel.csv`, with columns
  `state,county,year,variable,estimate,moe,status`. Include every requested
  county-year exactly once. Use the year-specific estimate variable code in
  `variable`. Use `observed` when the cached estimate is present. Preserve an
  explicit source state such as `suppressed` and leave its unavailable numeric
  fields empty; never turn missing evidence into zero.
- `analysis.json`, with `geography_key`, `requested_rows`, `observed_rows`,
  `comparable_counties`, `incomplete_counties`, `changes`, and
  `moe_not_aggregated_as_estimate`. `geography_key` is `["state", "county"]`.
  `changes` contains one object per county that has observed estimates in both
  years, with `state`, `county`, `2024_estimate`, `2025_estimate`, `change`,
  `percent_change`, and `status`. Calculate percent change against the 2024
  estimate. `incomplete_counties` contains the county codes that cannot support
  a two-year change.
- `method.md`, a short analyst handoff explaining stable-key matching, the
  year-specific variable mapping, why MOEs remain separate from estimates, how
  suppression was handled, and which name/aggregate records were outside the
  request. State how you reparsed and reconciled the final CSV and JSON.

Do not modify inputs, impute suppressed values, use the network, or claim that
an external workbook or public dataset was updated.

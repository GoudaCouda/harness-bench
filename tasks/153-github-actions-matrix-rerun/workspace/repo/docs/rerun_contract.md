# Matrix DAG rerun contract

Implement `plan_rerun(workflow, runs, policy)` without mutating inputs.
Malformed, cyclic, or incomplete evidence raises `ValueError`.

Workflow is a sorted unique list of jobs with exact keys `job_id`, `needs`,
`shards`, `consumes`, and `side_effect`. IDs/shards are lowercase ASCII tokens.
Needs and consumes are sorted unique existing job IDs; consumes must be a subset
of needs. Shards are sorted unique and nonempty. The graph must be acyclic.

Runs contain exactly one latest observation for every job/shard pair, with exact
keys `job_id`, `shard`, `status`, `attempt`, and `artifact_fresh`. Status is
`success`, `failure`, `cancelled`, or `skipped`; attempt is positive. Policy has
exact booleans `rerun_cancelled` and `allow_side_effects`.

Process jobs in deterministic topological order (lexical tie-break), then shard
order. Direct failures select `rerun` with reason `direct_failure`; cancelled
runs do so only when policy permits, otherwise remain `keep` with reason
`cancelled_by_policy`. A successful run whose own artifact is not fresh selects
`rerun` with `stale_output`. Selection of any shard in a needed upstream job is
a job-level matrix fan-in impact. An impacted skipped/cancelled/failed downstream
instance selects `rerun` with `upstream_dependency`. An impacted successful
instance selects only when it consumes at least one selected needed producer,
using `stale_artifact`; otherwise it stays `keep`/`successful`.

Before recording, any selected side-effect job becomes `manual` with reason
`side_effect_approval` unless policy allows side effects. Manual work still
counts as selected impact for downstream closure. Each plan row has exact keys
`job_id`, `shard`, `action`, `reason`, `attempt`; rerun/manual attempt is prior
attempt + 1, keep retains it. Return all rows plus summary exact keys `instance_count`,
`rerun`, `manual`, `keep`. No filesystem, network, GitHub, clock, process,
random, or environment access is allowed.

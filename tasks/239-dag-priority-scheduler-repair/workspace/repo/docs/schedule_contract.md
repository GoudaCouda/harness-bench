# Mill schedule contract

`schedule_jobs(jobs)` receives a list of objects with `job_id` (string),
`deps` (list of `job_id`s that must finish first), and `priority` (integer;
larger numbers run sooner among jobs that are currently ready).

Return `{"order": [...]}` when the graph is a DAG:

1. A job is ready when every dependency has already been placed in `order`.
2. Among ready jobs, choose the highest `priority`.
3. If several ready jobs share that priority, choose the lexicographically
   smallest `job_id`.
4. Repeat until every job is placed.

Raise `ValueError` and do not return an order when:

- a `job_id` is duplicated,
- a dependency names an identifier that is not in the input,
- or remaining jobs have no ready vertex (a cycle, including a self-edge).

Do not invent identifiers. Use the `job_id` strings from the input.

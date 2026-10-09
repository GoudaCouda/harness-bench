# CHG-4821 documentation review

**Decision: READY** — the revised guide is ready for the on-call documentation
handoff. This decision covers the guide only; no ConfigMap was applied, service
was restarted, or node was replaced.

## Evidence and material corrections

- Reconciled the database snapshot with the production ConfigMap. The old guide
  had stale values such as `max_db_connections` 200 instead of 500 and
  `worker_timeout` 120 instead of 30. Production `session_timeout_min` 30 is an
  intentional override of the global baseline 15, not unresolved drift.
- Used SQL for commissioned membership, role, and region. The retired
  single-region note hid `db-replica-01` and `worker-01` in `us-west-2`.
- Used the newer `node_inventory.json` hardware observation. It corrects the
  web nodes from 4 to 8 CPUs and records `cache-01` at 16 CPUs and 128 GB.
- Evidence reviewed: `db/backup.sql`, `db/environment.yml`,
  `db/node_inventory.json`, and the superseded `db/deployment_guide.md`.

## Residual caveat and pre-use validation

The sources are snapshots, not a live health check. Before using the guide,
confirm that the production ConfigMap still matches, verify inventory freshness
and `web-02` health, and confirm that a separate approved execution change has a
replacement and rollback procedure. Block execution if those checks disagree.

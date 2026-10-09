# OpenClaw production node-replacement guide (v1.3)

**Verified evidence cutoff:** 2026-04-29 22:00 UTC  
**Documentation change:** CHG-4821

Use this guide to verify the current production baseline before a node
replacement. It records expected state; it does not authorize a replacement or
configuration change.

## Effective production configuration

Production ConfigMap values override the database global baseline. A global
database value is used only when production has no override.

| Key | Effective production value | Source note |
|---|---:|---|
| `max_db_connections` | 500 | production ConfigMap |
| `cache_ttl_seconds` | 600 | production ConfigMap |
| `api_rate_limit` | 100 | production ConfigMap |
| `default_theme` | dark | database global baseline; no production override |
| `worker_timeout` | 30 | production ConfigMap |
| `db_connection_pool_size` | 150 | production ConfigMap |
| `enable_ssl` | true | production ConfigMap |
| `log_level` | INFO | production ConfigMap |
| `max_upload_size_mb` | 50 | production ConfigMap |
| `session_timeout_min` | 30 | intentional production ConfigMap override of database global baseline 15 |

Do not treat the `session_timeout_min` values 30 and 15 as unresolved drift:
the production override makes 30 the effective value.

## Commissioned cluster topology

Membership, role, and region come from the SQL cluster snapshot. Hardware comes
from the node inventory because its 22:00 UTC update is newer than the 21:00 UTC
SQL snapshot.

| Node ID | Role | CPU cores | Memory (GB) | Disk (GB) | Region |
|---|---|---:|---:|---:|---|
| web-01 | web | 8 | 16 | 200 | us-east-1 |
| web-02 | web | 8 | 16 | 200 | us-east-1 |
| api-01 | api | 16 | 32 | 500 | us-east-1 |
| api-02 | api | 16 | 32 | 500 | us-east-1 |
| db-master | database | 32 | 64 | 2000 | us-east-1 |
| db-replica-01 | database | 16 | 32 | 1000 | us-west-2 |
| cache-01 | cache | 16 | 128 | 100 | us-east-1 |
| worker-01 | worker | 16 | 64 | 500 | us-west-2 |

This is a multi-region cluster. Preserve `db-replica-01` and `worker-01` in
`us-west-2`; do not apply the retired all-`us-east-1` instruction.

## Pre-use checks

Immediately before a replacement, re-read the production ConfigMap, confirm the
inventory timestamp and node health, and use the separately approved execution
change for the replacement procedure and rollback. Stop if membership, region,
or effective settings differ from this verified baseline.

# Logical slot recovery contract

Implement `plan_slot_recovery(slots, consumers, observations, policy)` without
mutating inputs. Malformed structure or impossible topology raises `ValueError`.

Slots are a sorted unique list with exact keys `slot_name`, `database`,
`plugin`, `active`, `restart_lsn`, `confirmed_flush_lsn`, `wal_status`,
`invalidation_reason`, `failover`, and `synced`. Names are lowercase tokens;
LSNs are nonnegative integers. Confirmed LSN is at least restart LSN. WAL status
is `reserved`, `extended`, `unreserved`, or `lost`; invalidation is null,
`wal_removed`, `rows_removed`, `wal_level`, or `idle_timeout`. Lost requires a
reason, and any reason requires lost. Synced requires failover.

Consumers are sorted unique, exactly one per slot, with exact keys
`consumer_id`, `slot_name`, `database`, `plugin`, `last_applied_lsn`,
`can_resnapshot`, and `state` (`running`/`stopped`). Database/plugin must match
the slot and last applied LSN may not exceed confirmed flush LSN.

Observations have exact keys `primary_wal_lsn`, `oldest_available_lsn`,
`standby_synced_slots`, and `maintenance_window`. LSN ordering is oldest <=
primary; standby names are sorted unique and must name failover slots. Policy
has `max_retained_bytes` (positive integer) and `require_synced_failover` bool.

Retained bytes are `primary_wal_lsn - restart_lsn`. A slot needs recovery when
it is lost/invalidated, restart LSN predates oldest available WAL, or retention
exceeds the cap. Before recovery, block in this precedence: required failover
not both enabled and observed synchronized (`failover_not_ready`), active slot
(`slot_active`), no maintenance window (`maintenance_required`), or consumer
cannot resnapshot (`resnapshot_unavailable`). A safe recovery action is
`rebuild`, resume LSN is primary WAL LSN, and exact steps are
`stop_consumer`, `drop_slot`, `create_slot`, `resnapshot_consumer`,
`start_consumer`.

A healthy stopped consumer gets action `resume`, resume LSN is its last applied
LSN, and step is `start_consumer`; a healthy running consumer is `keep` with no
steps and the same resume LSN. Each plan has exact keys `slot_name`, `action`,
`reason`, `retained_bytes`, `resume_lsn`, and `steps`. Blocked resume LSN is
null and steps are empty. Plans are slot-sorted. Summary reports exact keys
`slot_count`, `retained_bytes_total`, and action counts `keep`, `resume`,
`rebuild`, `blocked`. No SQL, database, network, filesystem, clock, process,
random, or environment access is allowed.

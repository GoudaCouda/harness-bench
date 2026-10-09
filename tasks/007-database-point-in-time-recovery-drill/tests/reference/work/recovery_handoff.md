# PostgreSQL PITR recovery handoff

Incident `DB-INC-2026-0817-04` was reconstructed only in an offline synthetic recovery sandbox. The candidate is ready for manual promotion review; production was not changed, no promotion occurred, and no external communication or external action occurred.

## Recovery decision

I selected `base-t2-0920`, which belongs to system identifier `7419026813374501127` and production timeline 2. Its manifest, data files, and manifest-declared WAL all verify. The older `base-t2-0840` is not usable because its manifest checksum fails. Although `base-t3-1005` is newer and verifies locally, timeline 3 forked from timeline 2 for an abandoned recovery drill at `0/B000000`; it is not the history containing this production incident. Selecting `latest` would therefore choose the wrong branch.

The exact target is the named restore point `before_batch_cleanup` at `0/C120000` on timeline 2, with recovery target action `pause`. I rejected a timestamp target at `2026-08-17T10:15:42Z`: the safe restore point and destructive transaction `TX-881` have a shared timestamp, so inclusive/exclusive timestamp semantics cannot express the intended boundary without risking a valid commit or the destructive delete.

The verified base ends at `0/A300000`. The continuous readable archive path through the target is `00000002000000000000000A`, `00000002000000000000000B`, and `00000002000000000000000C`, using the local restore template `cp archive/%f %p`. Segment D is after the target and not required. Timeline-3 WAL is neither part of this path nor an acceptable substitute.

## Restore and consistency evidence

The protected controller replayed the selected base and WAL only into the isolated candidate, stopped at the named target, and kept writes disabled. Two complete and identical probe passes succeeded. They observed 1,250 active customers, an open-invoice sum of 482,190, invoice `INV-9912` present, the cleanup audit marker absent, zero foreign-key violations, and `database_accepts_writes=false`. This preserves the last valid invoice before the restore point while excluding the later destructive cleanup and its audit marker.

The plan, probe result set, immutable input hashes, state, and receipt are digest-bound. Replay completed and a repeated replay leaves the gate state and receipt byte-stable. `promoted=false` and `production_changed=false` remain enforced.

## Manual boundary and next actions

A separate authorized human must review the plan and receipt before any promotion decision. Before routing clients, retain the damaged cluster and WAL archive for rollback/forensics, compare application-level samples beyond the six declared probes, verify replication slots and downstream consumers, capture a fresh backup of the candidate, and prepare a routing rollback. During any later authorized cutover, monitor connection errors, active-customer counts, invoice totals, foreign-key checks, replication lag, and audit-marker absence. If a probe drifts or the timeline/LSN evidence changes, stop and rebuild the isolated candidate; this task itself authorizes no production restore, promotion, routing, notification, or communication.

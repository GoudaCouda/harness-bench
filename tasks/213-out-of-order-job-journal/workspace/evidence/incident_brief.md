# Incident RW-2026-0319-01: completion stream arrived out of order

The CI completion stream was buffered while the dispatcher was down. Events
are not in `seq` order: `job-b` completed before `job-a`, and `job-e`
completed after `job-d` had already failed.

Do not treat a later `succeeded` on the same attempt as a retry. Apply the
stream in `staging/completions.json` against `state/jobs.json`.

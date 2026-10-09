# Repair mill job scheduling

Night-shift builds on the Helix mill started the UI compile before the cache
load finished, and a cyclic recipe later hung the board. Repair the offline
repository in `$WORKSPACE/repo`.

Read `docs/schedule_contract.md` and `jobs.json`. Implement
`schedule_jobs(jobs)` in `src/schedule.py`. Then write `schedule.json` for the
supplied mill jobs. The object must contain `order`, using the `job_id` values
already present in `jobs.json`.

Create `IMPLEMENTATION_NOTES.md` covering topological order, priority and
identifier tie-breaks, cycle/unknown-edge failure, the exact public test
command and observed result, and one remaining integration risk.

Run from `repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not modify inputs or tests, start a build farm, or claim a mill dispatch.

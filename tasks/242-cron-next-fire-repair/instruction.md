# Repair mill cron next-fire

Night jobs started a day late because day-of-month and day-of-week were
treated as AND. Repair `$WORKSPACE/repo`.

Read `docs/cron_contract.md` and `job.json`. Implement `next_fire(expr, after)`
in `src/cron.py`. Write `next_fire.json` for the supplied mill job. The
object must contain `month`, `day`, `hour`, and `minute`.

Create `IMPLEMENTATION_NOTES.md` covering the 30-day clock, exclusive after,
DOM/DOW when both are restricted, the exact public test command and result,
and one remaining risk.

Run from `repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not modify inputs or tests, or claim a mill dispatch.

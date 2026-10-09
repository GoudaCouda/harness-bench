# Repair the selective restore planner

A backup operator must restore a selected application subtree from an
incremental snapshot chain without deleting unrelated destination files. The
current planner chooses the newest branch and ignores tombstones and type
collisions. Work only in `/workspace/repo`.

Read `docs/restore_contract.md`, inspect snapshots, destination inventory,
request, runner, and public tests, then repair `src/restore_planner.py` as a
general pure implementation. Do not hard-code fixture paths or snapshot IDs.

Run the unittest suite and `python bin/plan_restore.py`. The final run must
create `out/plan.json` and `out/summary.json`; parse both again. Write
`RESTORE_NOTES.md` covering selected ancestry, full/incremental replay,
tombstones, include/exclude scope, destination mapping, overwrite/type rules,
dry-run safety, strict validation, commands, and results.

Do not edit evidence, restore files, delete destination data, invoke backup
software, or claim that a live restore occurred.

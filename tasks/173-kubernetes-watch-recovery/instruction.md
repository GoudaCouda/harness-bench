# Repair Kubernetes watch recovery

A controller resumes watches after 410 Gone, applies duplicate events, and
treats progress bookmarks as object mutations. Work only in `/workspace/repo`.

Read `docs/watch_contract.md`, inspect observations, policy, runner, and public
tests, then repair `src/watch_recovery.py` as a general pure implementation.
Run public tests and `python bin/recover_watches.py`; re-parse both output JSON
files. Write `WATCH_NOTES.md` covering opaque resource versions, API-signaled
compaction and 410 Gone, why clients must not order cursors,
Exact/NotOlderThan, streaming initial events, bookmark completion, equal-cursor
duplicate handling, EOF/error resume, relist/reset, attempt budget, commands/results, and
the offline/no-cluster boundary.

Do not contact Kubernetes, use credentials, open sockets, or claim live list,
watch, relist, controller, or production validation.

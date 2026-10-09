# Repair atomic-save watcher reconciliation

You own a configuration reload daemon whose event handler follows event names
instead of filesystem state. Editors that save by rename replace the watched
inode, duplicate notifications trigger repeated reloads, and missing filenames
silently skip changes.

Work only in `$WORKSPACE/repo`. Read `docs/watcher_contract.md`, inspect the
initial checkpoint, replay batches, runner, and public tests, then repair
`src/watch_reconciler.py` as a general pure state transition. Do not hard-code
visible paths, sequence numbers, inode values, or digests.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python bin/replay_watch.py
```

The protected replay must generate `out/actions.json` and
`out/checkpoint.json`. Re-parse both after the final run. Write
`WATCHER_NOTES.md` explaining snapshot authority, duplicate coalescing,
temporary paths, atomic inode replacement, reload versus rebind, deletion,
null-filename rescan, unsafe nodes, validation, exact verification commands,
and their result.

Do not edit the policy, fixtures, checkpoint, runner, contract, or tests. Do not
touch a real watcher or service and do not claim an external reload.

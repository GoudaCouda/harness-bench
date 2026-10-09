# Watcher reconciliation handoff

Events are treated as advisory path hints and the stable snapshot after the
debounce window is authoritative. Distinct candidates are sorted, so duplicate
notifications coalesce. Temporary editor paths are ignored. A content digest
change causes one reload; an atomic save that changes only the inode causes a
rebind so a path-based watcher follows the replacement without needlessly
reloading identical content.

A null filename triggers a full snapshot rescan. That closes deletion of a
previously watched path and creation of a newly observed managed path. A
symlink or directory is blocked as an unsafe node while the prior checkpoint is
preserved. Invalid sequence, path traversal, malformed digest, unmanaged
checkpoint entry, or invalid policy fails before state advances.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` and
`PYTHONDONTWRITEBYTECODE=1 python bin/replay_watch.py`; both completed
successfully. I parsed the action ledger and final checkpoint and confirmed the
reload, rebind, delete, create, and block transitions across all three batches.
This was offline replay only; no real watcher, signal, service, or external
reload action was performed.

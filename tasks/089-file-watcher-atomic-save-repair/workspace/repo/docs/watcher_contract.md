# Watch reconciliation contract

Implement `reconcile_batch(checkpoint, batch, policy)` in
`src/watch_reconciler.py`. It is a pure function and must not mutate inputs.

## Shapes

`policy` has exactly:

- `roots`: a non-empty unique list of safe relative directory paths;
- `extensions`: a non-empty unique list such as `.json` and `.yaml`;
- `temporary_prefixes` and `temporary_suffixes`: unique lists of non-empty strings.

`checkpoint` has exactly `seq` (non-negative integer) and `watched` (object).
Each watched key is a managed path and its value has exactly `inode` (positive
integer) and `digest` (64 lowercase hexadecimal characters).

`batch` has exactly `seq`, `events`, and `snapshot`. Its sequence must be
strictly greater than the checkpoint sequence. Events are objects with exactly
`kind` (`change` or `rename`) and `path` (a safe relative path or null).
Snapshot keys are safe relative paths; each value has exactly `type`
(`file`, `symlink`, `directory`), `inode`, and `digest`. A file requires a
positive integer inode and lowercase SHA-256 digest. Non-files require null for
both. Reject malformed or non-canonical inputs with `ValueError`.

A safe relative path uses `/`, has no empty, `.`, or `..` component, no
backslash, no absolute/drive prefix, and no NUL. A managed path lies strictly
below a configured root, has a configured extension, and its basename begins
with none of the temporary prefixes and ends with none of the temporary
suffixes. Checkpoint keys must be managed. Snapshot may include safe unmanaged
and temporary paths.

## Reconciliation

Events are advisory hints; `snapshot` is the authoritative final state after
the debounce window. If any event path is null, candidates are the union of all
checkpoint paths and all managed snapshot paths. Otherwise candidates are the
distinct managed event paths. Ignore unmanaged and temporary event paths.

For each candidate in lexical path order:

- snapshot regular file, absent checkpoint: action `reload`, reason `created`;
- regular file, digest changed: `reload`, reason `content_changed` (regardless
  of whether inode changed);
- regular file, same digest but inode changed: `rebind`, reason
  `inode_replaced`;
- regular file, same digest and inode: no action;
- absent snapshot, present checkpoint: `delete`, reason `removed`;
- symlink or directory snapshot: `block`, reason `unsafe_node`, preserving any
  prior watched value and never adding a new one.

Reload and rebind replace the watched value with snapshot inode/digest. Delete
removes it. Duplicate hints therefore produce at most one action per path. The
batch sequence always advances after a valid reconciliation, including a block.

Return exactly `{"actions": [...], "checkpoint": {"seq": ..., "watched":
...}}`. Each action has exactly `path`, `action`, and `reason`; actions and the
checkpoint's watched keys are lexical.

# Interrupted wheel recovery contract

`plan_recovery(site_state, journal, wheel_record)` is a pure planning function:
only the standard-library `re` module may be imported; I/O, printing, and input
mutation are forbidden. It returns exactly:

```text
{"decision": ..., "actions": [...], "conflicts": [...]}
```

## Input schemas

- `site_state` has exactly `files`, a list of current file records. Each record
  has exactly `path`, `digest`, `owners`.
- `wheel_record` is a list of records with exactly `path`, `digest`, `size`.
- `journal` has exactly `package`, `phase`, `entries`. Phase is `applying`,
  `recovering`, or `committed`. Each entry has exactly `path`, `before`,
  `after_digest`, `applied`; `before` is null or a record with exactly `digest`
  and `owners`.

Paths are unique, relative POSIX paths: no empty, `.`, `..`, backslash, absolute,
or empty segment. Journal paths equal the wheel RECORD paths. Digests are
non-empty `sha256=` URL-safe base64 strings; RECORD sizes are non-boolean,
non-negative integers. Owner lists are sorted, unique, non-empty strings. The
journal's `after_digest` must equal the matching RECORD digest. Invalid input
raises `ValueError` before planning. Other current site files are allowed.

## Recovery rules

1. A `committed` journal returns decision `committed` with empty actions and
   conflicts.
2. For `applying` or `recovering`, inspect entries in reverse journal order.
   The expected post-write owners are the sorted union of the `before` owners
   and the journal package, or only the package for a newly created path.
3. An unapplied entry is safe only when current state still equals `before`.
4. An applied entry already equal to `before` was recovered previously and
   emits no action. Otherwise current state must exactly equal its expected
   post-write digest and owners. Any other state is conflict
   `post_write_drift`; an unsafe unapplied state is `unexpected_unapplied_state`.
5. Exact post-write state produces one of:
   - new path: `{"kind":"remove","path":...}`;
   - changed existing content: `restore` with the before digest and owners;
   - unchanged shared content newly owned by this package: `detach_owner`;
   - identical pre/post state where the package was already an owner: no action.
6. If any conflict exists, return `manual_intervention`, no actions, and the
   conflicts in reverse journal order. Never emit a partial rollback plan.
   Otherwise return `rollback_required` when actions exist, or
   `already_rolled_back` when none remain. Action order is reverse write order.

Planning never edits the described environment. An executor must recheck each
digest and owner set before applying a reviewed plan.

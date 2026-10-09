# Repair a safe Git worktree prune plan contract

Plan only Git worktree administrative repair/prune; never remove an existing worktree. Main path, locked worktrees, protected branches, and dirty existing worktrees are kept. Existing paths missing admin metadata require registration repair. Missing paths with admin metadata are prunable only when `now-last_seen >= expire_after`; otherwise retain. Missing path+metadata is already absent. Return id-sorted decisions and prune/repair path lists. Invalid timestamps/booleans and duplicate ids raise `ValueError`.

The output object has exactly `decisions,prune_paths,repair_paths`. Each id-sorted decision has exactly `id,action,reason,path`. Actions are `keep,repair_registration,prune_admin,already_absent`; reasons are `main_worktree,locked,protected_branch,dirty_existing_worktree,missing_admin_metadata,missing_and_expired,missing_but_not_expired,no_metadata`, or `healthy`. Prune and repair path lists follow decision order.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

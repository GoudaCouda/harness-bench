# Repair the affected-build planner

The Acorn monorepo reused stale build outputs after a generated API file
changed. Fix the local planner in `$WORKSPACE/repo` and leave a reviewable plan
for the supplied change set. This is an offline repository task; do not install
packages or claim that CI, a merge, or a deployment occurred.

Read `docs/planner_contract.md`, `build_graph.json`, `changed_paths.json`, the
starter implementation, and the public tests. Then:

1. Implement `plan_affected(changed_paths, graph)` in
   `src/affected_build.py`. It must return the affected buildable package names
   in the contract's deterministic order.
2. Create `affected_plan.json` for the supplied graph and change set with keys
   `changed_paths`, `affected_packages`, and `direct_causes`. `direct_causes`
   maps every directly invalidated package to one or more supplied paths; do
   not invent a direct cause for transitive dependants.
3. Create `REPAIR_NOTES.md` that explains the invalidation and ordering
   decisions, records the exact public verification command and its observed
   result, and names one remaining integration risk.

Run from `$WORKSPACE/repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not modify the graph, changed-path fixture, contract, or public tests.

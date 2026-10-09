# Affected-build planner contract

`plan_affected(changed_paths, graph)` returns a list of buildable package names.

1. Validate the complete package dependency graph first. A missing dependency
   or any dependency cycle raises `ValueError`, even when the current changes
   would not touch that component.
2. Duplicate changed paths have no additional effect. Paths use `/` separators.
   A path need not exist: deletion is still a change.
3. A path exactly listed in `global_inputs` directly invalidates the listed
   buildable packages.
4. A path exactly listed in a package's `generated_inputs` directly invalidates
   that package.
5. Otherwise, a non-Markdown path below a `source_roots` prefix directly
   invalidates the owning buildable package. If roots overlap, the longest
   matching root owns the path; ties are resolved by package name.
6. Markdown paths (`.md`, case-insensitive) are documentation-only unless they
   matched an exact generated or global input in steps 3–4. Non-buildable
   packages are never returned.
7. Every buildable package that transitively depends on a directly invalidated
   package is affected.
8. Return affected packages by dependency depth (all dependencies before their
   dependants), then package name for equal depths. Dependency depth is zero for
   a package with no buildable dependencies and otherwise one plus the maximum
   dependency depth.

The function must derive its answer from its arguments. It must not read files,
run commands, use the network, or mutate the supplied values.

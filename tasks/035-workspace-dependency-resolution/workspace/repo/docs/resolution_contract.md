# Resolution contract

`resolve_workspace(manifest, registry, current_lock, target)` returns
`{"packages": [{"name", "version", "source"}], "skipped_optional": [...]}`.

- Versions are strict `major.minor.patch`. Ranges are exact or caret ranges. A
  caret `^M.m.p` accepts versions with the same major and not below the base.
- Manifest has `dependencies` and `optionalDependencies` maps. Registry maps a
  package name to releases containing `version`, optional `dependencies`,
  `peerDependencies`, `peerDependenciesMeta`, `os`, and `cpu`.
- A selected release adds its transitive dependencies. Each non-optional peer
  must also exist in the final graph and satisfy its range. A peer whose metadata
  is `{"optional": true}` does not force installation, but must be compatible if
  already present.
- `os` and `cpu` arrays are allowlists unless entries begin with `!`, which deny
  that value. A release must satisfy both target dimensions. An unresolved
  optional root and everything needed only by it are omitted and named in
  `skipped_optional`; a required failure raises `ValueError`.
- Prefer a complete solution including the greatest number of optional roots,
  then preserving the greatest number of current-lock versions. Break ties by choosing the lexicographically greatest vector of
  semantic versions in package-name order. Output packages are name-sorted and
  `source` is `preserved` when its version equals the current lock, otherwise
  `selected`. Skipped optionals are name-sorted. Inputs are immutable.
- Reject malformed roots, versions, ranges, target values, or dependency cycles.

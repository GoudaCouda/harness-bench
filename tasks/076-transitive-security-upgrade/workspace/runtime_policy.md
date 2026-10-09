# Dispatch Console dependency policy

- Production and CI are pinned to Node 18.x until the Q4 runtime migration.
- Resolve advisories through the least-change compatible set of direct-parent
  upgrades across the root and worker manifests. Minimize the number of changed
  direct parents first, then version distance from the recorded baseline.
- Manifest and lockfile must agree; direct edits to transitive lock entries are
  not an acceptable repair.
- Overrides, aliases and isolated edits to vulnerable transitive entries are
  outside the supported remediation process.
- `parser-cli` and its `parserx` resolution, workspace identity, lock generator
  metadata and registry snapshot are outside this incident scope.
- Compatibility includes the CLI, HTTP-session, claims, worker-resume and
  storage-retry contracts recorded in the fixtures.
- Local verification is evidence for review, not permission to publish or
  deploy.

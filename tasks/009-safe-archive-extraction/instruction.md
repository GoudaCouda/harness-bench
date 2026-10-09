# Repair archive extraction preflight

The local artifact installer accepted archive members that could escape the
staging directory or collide on a case-insensitive runner. Repair the preflight
in `$WORKSPACE/repo`; do not extract an archive, install software, or contact a
registry.

Read `docs/security_contract.md`, `release_manifest.json`,
`extraction_policy.json`, the starter code, and public tests. Then:

1. Implement `plan_extraction(entries, policy)` in
   `src/archive_preflight.py`. It must either return the normalized extraction
   entries in archive order or raise `ValueError` before any write.
2. Create `extraction_plan.json` for the supplied safe release manifest with
   keys `manifest_id`, `destination`, `entries`, `file_count`, and
   `total_file_bytes`.
3. Create `SECURITY_NOTES.md` explaining the path/link/collision/budget
   decisions, the exact public verification command and observed result, and a
   remaining integration risk.

Run from `$WORKSPACE/repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The visible suite also builds real in-memory tar headers and sends their member
metadata through the repaired preflight, including a path-escape fixture. It
does not write extracted content.

Do not modify the manifest, policy, contract, or public tests. Do not claim an
archive was extracted or a release was installed.

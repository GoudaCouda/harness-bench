# Repair notes

The tag is the sole release authority and must advance strict SemVer precedence. The planner translates alpha, beta, and rc spelling into canonical Python forms while npm and Cargo retain canonical SemVer. It validates every manifest before returning a path-sorted atomic set, preserves exact no-op versions, and blocks unsafe paths, duplicates, malformed publish flags, and unsupported ecosystems.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests pass. Residual risk remains in the executor: it must update manifests and generated lockfiles atomically, verify clean diffs and package metadata, create the tag only after review, and let authenticated publisher tooling enforce registry uniqueness. No tag, manifest, lockfile, registry, or publication action was performed here.

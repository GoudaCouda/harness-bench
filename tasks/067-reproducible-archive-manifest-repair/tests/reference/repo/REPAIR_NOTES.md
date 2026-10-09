# Repair notes

The planner strips the validated build root, rejects unsafe and duplicate
members, sorts canonical POSIX paths, and normalizes file/directory modes. It
ignores host mtimes, uses `SOURCE_DATE_EPOCH`, clamps to the ZIP 1980 floor, and
rounds down to the format's two-second precision. SHA-256 and member kinds are
validated before any downstream writer sees the plan.

Verification: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
completed successfully with all public tests passing. Residual risk remains in
the archive writer: it must preserve member order, timestamp, mode, and path and
must not add host metadata. No artifact was published or deployed.

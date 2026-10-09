# Selective restore handoff

The planner follows the explicitly selected snapshot and its parent ancestry,
never a lexically newest sibling. A usable chain starts at a complete full
snapshot and replays complete incremental manifests oldest to newest. Upserts
replace paths; tombstones remove the path and every descendant, so deleted data
cannot reappear from an earlier layer. Missing parents and incomplete chains
remain blocked.

Include and exclude selectors match path segments, with exclude winning, then
source paths map beneath the declared target root. Existing directories and
same-checksum files are unchanged. Changed files obey overwrite policy;
file/directory type collisions and symlinks are conflicts. No destination-only
file is selected for deletion.

Validation rejects unsafe or noncanonical paths, malformed checksums, duplicate
entries, cycles, bad request shapes, and any request that is not a dry run or
asks to delete extraneous data. `PYTHONDONTWRITEBYTECODE=1 python -m unittest
discover -s tests -v` passed and `PYTHONDONTWRITEBYTECODE=1 python
bin/plan_restore.py` succeeded. I parsed plan and summary again. No backup tool,
restore, mount, overwrite, or delete was executed against live data.

# Protected queue policy

Required gates are `build_linux`, `build_windows`, `security`, `license`,
`owner_approval`, and `release_approval`. Any new commit invalidates prior-SHA
checks and approvals. The queue item is blocked until all six gates pass on the
new SHA. A failed license gate requires dependency remediation and rerun; a
pending security gate waits for its current scan; a stale owner approval needs
current-SHA reapproval. Never merge while a gate is unresolved.

# TR-2026-017 records-officer handoff

The offline package is staged for review with three evidence-supported
preservation records. REC-001 uses the PDF/A-2b council-minutes master. REC-002
uses `map_scan_rescan.tif`: its QC result confirms that the rescan restores the
full legend, while the superseded v1 scan failed QC for a cropped legend and is
excluded. REC-003 uses the 24-bit PCM preservation master. The AAC access
derivative is excluded because its wrapper/codec profile is not the accepted
preservation combination.

REC-004 is not in the staged manifest. Its calculated SHA-256 does not match the
controlled checksum register, so it remains in the quarantine ledger with
reason `checksum_mismatch` for records-officer review. The mismatch was not
silently replaced by a newly calculated expected digest.

For each staged item, the local tool reconciled the required series metadata,
accepted format or codec, QC result, preservation-master flag, copied-file
digest, manifest digest, and package checksum ledger. Reapplying the same plan
and rerunning verification produced the same closed record set and passed the
idempotent staging check.

This is an offline, staged-not-submitted package. It was not submitted to ERA,
has not been accessioned, and does not authorize source-record disposal or any
external communication.

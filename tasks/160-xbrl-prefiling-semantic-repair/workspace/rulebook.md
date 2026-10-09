# Local pre-filing rulebook EFM-SYN-2026.1

- All severity=error items must be repaired before status can be test_ready.
- Warnings in this exercise also have deterministic repairs and remain open
  until the repair is recorded.
- Required entity CIK is 0000123456.
- Required reporting period end is 2025-12-31.
- Required taxonomy is us-gaap-2025.
- Equivalent duplicate contexts C-YEAR and C-YEAR-DUP must be merged to C-YEAR.
- Rename exhibit from exhibit bad.xml to exhibit_101.xml.
- Repairing metadata must not change Revenue=1250000 or Assets=2400000.
- Run validate_filing.py against the repaired candidate. Every validator check
  must pass and its report must be saved as validator_report.json.
- This is test-package preparation only; do not claim a live filing.

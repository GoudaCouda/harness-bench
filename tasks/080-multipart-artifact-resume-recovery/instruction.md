# Recover a multipart CI artifact upload

A large CI artifact upload was interrupted after several parts. The old
planner trusts one `ListParts` page and may complete with missing or stale
parts. Repair the offline reconciliation planner before any object-storage API
is called.

Work only in `repo/`. Preserve
`plan_multipart_resume(session, local_parts, remote_pages)`. Read the contract,
broken source, visible incidents, and public tests.

Deliver repaired `repo/src/multipart_resume.py`, ordered
`repo/resume_plan.json` with every visible `case_id` and exact result, and
`repo/REPAIR_NOTES.md`. Explain upload-ID authority, pagination, consecutive
part numbers, checksum/size reconciliation, same-number overwrite risk,
unknown completion probing, exact verification, and residual executor risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not call object storage, upload, overwrite, complete, abort, delete,
publish, or claim an external action.

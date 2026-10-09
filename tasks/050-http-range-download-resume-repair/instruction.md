# Repair a resumable HTTP download

A release fetcher sometimes appends a full `200` response to a partial file,
accepts a changed ETag, or treats an unrelated `416` as success. Repair its local
resume decision function before the downloader is used again.

Work only in `repo/`. Read the contract, broken implementation, visible cases,
and public tests. Preserve
`reconcile_resume(manifest, checkpoint, response)`.

Deliver the repaired `repo/src/range_resume.py`, an ordered
`repo/resume_report.json` containing each visible `case_id` and exact result, and
`repo/REPAIR_NOTES.md`. Explain checkpoint trust, strong ETag/If-Range behavior,
the `206`, `200`, and `416` branches, digest verification, exact verification
command/result, and residual risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit evidence or claim a network request, artifact publication,
or deployment.

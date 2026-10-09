# Repair the invoice-collection eligibility regression

You are the on-call engineer for an offline checkout of `ledger-router`. An
incident replay shows that one suspended account was routed to collections and
one delinquent account was skipped after a recent refactor. The checkout at
`$WORKSPACE/repo` contains a short, real Git history prepared by the benchmark.

Work only in `$WORKSPACE/repo`.

1. Read `docs/incident.md`, inspect the repository and its Git history, and run
   the incident replay and public tests.
2. Use Git history (for example, log, diff, show, and bisect) to identify the
   first bad commit. Do not assume that the newest commit caused the incident.
3. Repair the current branch with the smallest source change that restores the
   documented eligibility policy while preserving the later audit-reason
   behavior and the public API.
4. Run both:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 tools/replay_incident.py
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
   ```

5. Create `regression_report.json` with this shape:

   ```json
   {
     "first_bad_commit": "<40-character commit hash>",
     "first_bad_subject": "<commit subject>",
     "incident_cases": ["INV-401", "INV-402"],
     "root_cause": "<concise technical explanation>",
     "changed_files": ["src/ledger_router/eligibility.py"],
     "verification": [
       {"command": "python3 tools/replay_incident.py", "result": "pass"},
       {"command": "python3 -m pytest -p no:cacheprovider", "result": "pass"}
     ],
     "scope": "offline repository repair; no production deployment"
   }
   ```

Only modify `src/ledger_router/eligibility.py` and create
`regression_report.json`. Do not edit tests, fixtures, incident evidence, or
Git history. Do not install packages or claim a deployment, collections action,
or customer contact.

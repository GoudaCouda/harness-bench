# Repair recursive structured-log redaction

You are repairing the sanitizer in a Python service before its JSON logs can be
sent to a lower-trust operations system. The current code only checks top-level
keys and damages harmless diagnostic text.

Work only in `$WORKSPACE/repo`. Read `docs/redaction_contract.md`, inspect the
fixtures and tests, then repair `src/redactor.py`. Implement the contract as a
general pure function; do not hard-code fixture values or event IDs.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python bin/run_redaction.py
```

The protected runner must produce `out/redacted.jsonl` and `out/audit.json`
from `events.jsonl`. Re-run it after the final code change and inspect both
outputs. Create `REDACTION_NOTES.md` explaining recursive key handling, free
text credential patterns, already-redacted values, deliberate non-redaction,
validation failures, the exact commands run, and their result.

Do not edit the contract, fixtures, tests, policy, or runner. Do not use the
network, copy raw sensitive values into notes, or claim that logs were shipped
to an external system.

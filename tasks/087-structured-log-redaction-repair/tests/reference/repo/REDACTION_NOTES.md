# Redaction repair handoff

The sanitizer now walks recursive objects and arrays, compares each sensitive
key exactly with case folding, and emits escaped JSON-pointer findings. An
already redacted value is preserved without a duplicate finding. Harmless keys
and prose such as tokenizer and passwordless are deliberately preserved rather
than matched by substring.

Free text is scanned left to right for Bearer credentials, exact assignment
forms, and URL userinfo. Only each credential span is replaced, retaining the
surrounding exception diagnostic. Validation rejects invalid event types,
policy shapes, duplicate folded names, non-JSON values, and excessive nesting.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` and
`PYTHONDONTWRITEBYTECODE=1 python bin/run_redaction.py`; both completed
successfully. I then parsed the JSONL and audit, confirming three events, six
findings, preserved correlation IDs, and no raw credential in either output.
This was a local verification only: no external log sink or production shipping
action was performed.

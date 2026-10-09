# Repair notes

The checkpoint is trusted only when its temporary file exists, offset is in
bounds, and strong ETag matches the manifest used for If-Range. A `206` is
appendable only after exact Content-Range and length reconciliation. A `200`
replaces rather than appends and completes only after full digest verification.
A `416` proves completion only at the expected size with matching prefix digest
and `bytes */SIZE`; all validator or final-digest conflicts restart at zero.

Verification succeeded with
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all public
tests passed. Residual risk: the production transport must hash actual bytes and
atomically persist the temporary file and checkpoint before exposing completion.
No network request, artifact publication, or deployment was performed.

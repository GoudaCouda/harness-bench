# Repair mill JSON Pointer resolution

A diagnostic walk printed `~1` literally and missed the west mill gate.
Repair `$WORKSPACE/repo`.

Read `docs/pointer_contract.md` and `document.json`. Implement
`resolve_pointer(document, pointer)` in `src/pointer.py`. Check object
membership and array length before indexing, then raise `ValueError` on
missing paths. Write `resolved.json` as `{"value": ...}` for the pointer in
`query.json`.

Create `IMPLEMENTATION_NOTES.md` covering empty pointers, `~1`/`~0` order,
missing paths, the exact public test command and result, and one remaining
risk.

Run from `repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not modify inputs or tests, or contact a mill API.

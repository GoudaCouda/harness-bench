# Repair field-ownership apply planning

An internal controller preview overwrites fields owned by other reconcilers and
deletes fields even when an apply request is rejected. Work only in
`/workspace/repo`.

Read `docs/field_contract.md`, inspect the flattened live object, managed-field
ownership, defaults, intents, policy, runner, and public tests, then repair
`src/field_ownership.py` as a general pure implementation. Do not hard-code
request IDs, managers, paths, or values.

Run the public unittest suite and `python bin/apply_intents.py`. The final run
must create `out/object.json`, `out/ownership.json`, and `out/decisions.json`;
parse all three again. Write `FIELD_NOTES.md` covering atomic conflicts, force,
protected paths, same-value shared ownership, omission/relinquishment,
default-versus-delete behavior, sequential intents, strict validation,
commands, and results.

Do not edit captured evidence, call Kubernetes, alter managedFields, apply a
manifest, or claim that any cluster object or controller was changed.

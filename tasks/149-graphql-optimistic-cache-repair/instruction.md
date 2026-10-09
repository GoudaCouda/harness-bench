# Repair optimistic normalized-cache reconciliation

A client cache loses newer optimistic edits when mutation responses arrive out
of order, and failed mutations leave temporary references behind. Work only in
`/workspace/repo`.

Read `docs/cache_contract.md`, inspect the normalized base, event stream,
policy, runner, and public tests, then repair `src/optimistic_cache.py` as a
general pure implementation. Do not hard-code mutation IDs, entity IDs, fields,
or event order.

Run the public unittest suite and `python bin/reconcile_cache.py`. The final run
must create `out/base.json`, `out/visible.json`, and `out/audit.json`; parse all
three again. Write `CACHE_NOTES.md` covering normalization, patch merge,
missing-versus-null, layer order, success commit, error rollback, out-of-order
rebase, temporary-ID aliasing/reference rewrite, ignored optimism, validation,
commands, and results.

Do not edit evidence, contact a GraphQL endpoint, mutate a browser cache, send a
mutation, or claim that a live application was changed.

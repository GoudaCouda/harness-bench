# Repair the HTTP cookie jar

An internal HTTP client corrupts its cookie store during response replay and
sends host-only or path-scoped cookies to the wrong requests. Work only in
`/workspace/repo`.

Read `docs/cookie_contract.md`, inspect the seed store, response sequence,
request probes, runner, and public tests, then repair `src/cookie_jar.py` as a
general pure implementation. Do not hard-code fixture hosts, names, or times.

Run the public unittest suite and `python bin/reconcile_cookies.py`. The final
run must create `out/store.json` and `out/requests.json`; parse both again.
Write `COOKIE_NOTES.md` covering host-only and Domain scope, default/path
matching, Max-Age precedence and deletion, Secure/HttpOnly handling, replacement
identity and creation order, expiration, strict validation, commands, and results.

Do not edit protected inputs, contact any host, log hidden cookie values beyond
the declared outputs, or claim that a browser or live client was changed.

# Flatten mill host aliases

The mill hosts file mixes IPv4 literals and name-to-name aliases, including
a two-node loop. Read `docs/hosts_contract.md` and `hosts.json`.

Write `hosts_flat.json` using the `name` values already present in
`hosts.json`. Create `FLATTEN_NOTES.md` covering alias chains, loops,
flattening, one verification step, and one remaining risk.

Do not modify `hosts.json`, contact a nameserver, or claim DNS was updated.

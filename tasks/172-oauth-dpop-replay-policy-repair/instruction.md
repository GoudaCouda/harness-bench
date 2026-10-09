# Repair OAuth DPoP replay policy

A resource-server gate accepts any proof marked signature-valid and does not
bind it to the request, token, nonce, or replay state. Work only in
`/workspace/repo`.

Read `docs/dpop_contract.md`, inspect requests, proofs, replay cache, policy,
runner, and public tests, then repair `src/dpop_policy.py` as a general pure
implementation. Run public tests and `python bin/verify_dpop.py`; re-parse all
files in `out/`. Write `DPoP_NOTES.md` covering `typ`, asymmetric algorithm,
public JWK and signature evidence, `htm`/normalized `htu`, `iat` bounds, `jti`,
key thumbprint, `ath`, nonce, active/expired and same-batch replay, cache update
boundaries, commands/results, and the offline/no-cryptography boundary.

Do not verify real JWTs, use tokens or keys, contact identity endpoints, or
claim live authentication or production authorization.

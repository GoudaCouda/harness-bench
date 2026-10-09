# Repair WebAuthn assertion risk reconciliation

An authentication service rejects legitimate synchronized passkeys as clones,
while some rejected assertions still overwrite stored credential state. Work
only in `/workspace/repo`.

Read `docs/assertion_contract.md`, inspect credentials, assertions, policy,
runner, and public tests, then repair `src/assertion_risk.py` as a general pure
implementation. This task receives already-verified facts; do not implement or
pretend to perform cryptography.

Run the public unittest suite and `python bin/assess_assertions.py`. The final
run must create parseable `out/credentials.json` and `out/decisions.json`.
Write `AUTH_NOTES.md` covering trust-check precedence, user verification,
backup eligibility/state, zero and monotonic counters, device-bound regression,
synchronized-passkey policy, state-update boundaries, validation, commands,
results, and the offline/no-cryptography boundary.

Do not edit evidence, call an identity provider, send an assertion, revoke a
credential, or claim a production authentication change.

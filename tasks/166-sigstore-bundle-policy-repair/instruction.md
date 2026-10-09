# Repair offline Sigstore bundle policy

A release gate checks only `signature_verified` and current certificate expiry,
ignoring artifact digest, workload identity, issuer, historical trust material,
transparency evidence, timestamp evidence, and operator thresholds. Work only
in `/workspace/repo`.

Read `docs/bundle_contract.md`, inspect artifacts, bundles, trusted roots,
policy, runner, and public tests, then repair `src/bundle_policy.py` as a
general pure implementation. Run public tests and `python bin/verify_bundles.py`;
re-parse both files in `out/`. Write `VERIFICATION_NOTES.md` covering digest and
payload binding, signature/chain evidence, exact identity/issuer, short-lived
certificate signing time, tlog inclusion and distinct operators, RFC3161
timestamp evidence, inclusive historical root validity, precedence,
commands/results, and the offline/no-Sigstore boundary.

Do not contact Fulcio, Rekor, a TSA, TUF, registry, or claim cryptography or a
production release was executed.

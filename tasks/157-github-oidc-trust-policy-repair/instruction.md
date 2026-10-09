# Repair CI OIDC workload trust

A cloud-role authorizer trusts repository names without stable IDs and accepts
tokens whose subject context disagrees with their claims. Work only in
`/workspace/repo`.

Read `docs/trust_contract.md`, inspect roles, token claims, policy, runner, and
public tests, then repair `src/oidc_trust.py` as a general pure implementation.
The claims are already decoded facts; do not implement JWT cryptography. Run
public tests and `python bin/evaluate_trust.py`; re-parse both `out/` files.
Write `TRUST_NOTES.md` covering issuer/audience, ID-token permission, immutable
owner/repository IDs, subject reconstruction, ref/environment context,
pull-request policy, pinned reusable workflow, precedence, validation,
commands/results, and the offline/no-cloud boundary.

Do not request a token, call GitHub or a cloud provider, assume a role, modify a
trust policy, edit evidence, or claim production authorization.

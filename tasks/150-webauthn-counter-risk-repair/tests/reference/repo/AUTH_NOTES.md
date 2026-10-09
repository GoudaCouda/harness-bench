# Authentication-state handoff

The trust-check precedence is credential existence and revocation before user, signature, origin, RP ID, user-verification, and backup-signal checks. These trust failures are decisions rather than malformed-input errors and leave every credential field untouched. Backup eligibility is immutable; backup state can change only on a trusted accepted assertion and only for an eligible credential.

Two zero counters mean the authenticator does not provide a useful counter. A larger value advances state; equal or lower values are regressions. Device-bound regressions follow reject/flag policy, while synchronized passkeys use their separate flag/ignore policy to avoid clone false positives. Rejection preserves counter, backup state, and last assertion while marking clone risk compromised. Accepted flags retain the maximum counter and elevate risk; risk never de-escalates.

Verification ran `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/assess_assertions.py`, and JSON parsing of both output files; all passed. The input contains pre-verified facts only: no cryptography was attempted, and no identity provider, browser, credential, assertion endpoint, network, or production authentication state was contacted or changed.

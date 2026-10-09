# Repair the rotated webhook verifier

A webhook endpoint is rejecting deliveries during a signing-secret rotation and
occasionally accepts replays outside the intended tolerance. Work only in
`/workspace/repo`.

Read `docs/verification_contract.md`, inspect the synthetic keyring, deliveries,
checkpoint, runner, and public tests, then repair `src/webhook_verifier.py` as a
general pure implementation. Do not hard-code fixture IDs, bodies, timestamps,
or signatures.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python bin/verify_webhooks.py
```

The final run must create `out/decisions.json` and `out/checkpoint.json`; parse
both again. Create `VERIFICATION_NOTES.md` explaining raw-body signing,
rotation-window eligibility, multiple signatures, inclusive timestamp
tolerance, constant-time comparison, replay state, fail-closed validation,
exact verification commands, and results.

Do not edit evidence, policy, runner, or tests. Do not log secrets or accepted
signature material, use filesystem/network/process capabilities from the
verifier, or claim that a live endpoint or provider was changed.

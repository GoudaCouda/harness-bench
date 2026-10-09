# Recover an mTLS certificate rotation without breaking overlap trust

You are the platform security engineer taking over a partially completed internal
mTLS rotation. `billing-api` still presents its old leaf and chain. A worker
continues to depend on the old root during the documented overlap window, while
an unrelated reporting service is already healthy on the new root.

Work only in `$WORKSPACE`. Inspect `certificates.json`, `services.json`,
`rotation_policy.md`, the current `pki_state.json`, and `pki_ctl.py` before
changing anything.

Complete the recovery through the local controller:

1. Run `python3 pki_ctl.py status` and use its observations together with the
   visible certificate inventory and policy.
2. Create `rotation_plan.json`. Its `actions` array may target only services
   that actually require a change. Each action contains `service_id`, the full
   leaf-to-intermediate `presented_chain`, and `truststore_add` /
   `truststore_remove` arrays.
3. Run `python3 pki_ctl.py apply rotation_plan.json`. Inspect the resulting
   state and receipt. If verification fails, correct the plan rather than
   hand-editing generated receipts.
4. Run `python3 pki_ctl.py verify`. It writes `handshake_report.json`; finish
   only when the report passes every service and preservation check.
5. Re-run the same apply command to prove idempotency. A successful retry must
   not increment the revision or append another audit event.
6. Write `rotation_handoff.md` explaining the billing chain change, why the old
   root remains during overlap, which services were deliberately preserved,
   the verification result, and that no production deployment occurred.

The mutable state is `pki_state.json`. The controller owns
`pki_audit.jsonl` and `handshake_report.json`; do not hand-author them. Keep
`certificates.json`, `services.json`, `rotation_policy.md`, and `pki_ctl.py`
unchanged. Work offline and do not claim a production rollout, certificate
issuance, revocation, or external network action.

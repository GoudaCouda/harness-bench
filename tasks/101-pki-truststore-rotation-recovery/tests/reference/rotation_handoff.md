# mTLS rotation recovery handoff

`billing-api` now presents `leaf-api-v2` through `int-b` and trusts the issuing
`root-2026`. The existing `root-2024` was deliberately retained for overlap:
`event-worker` still presents its valid v1 chain through `int-a` and depends on
that old root. The unrelated `reporting` service was preserved exactly because
it was already healthy on the new chain while retaining overlap trust.

The local handshake verification passed for all three services, including
subject, issuer chain, validity, required-root trust and the one-transition
audit check. Reapplying the same plan returned idempotent without incrementing
revision 4 or appending a second audit event. This is an offline staged state
only: no production deployment, certificate issuance, revocation, or network
action was performed.

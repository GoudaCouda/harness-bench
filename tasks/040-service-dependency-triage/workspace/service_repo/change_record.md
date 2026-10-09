# AUTH-2026-0318 change record

The partner identity provider cut over from issuer
`https://issuer.partner/v1` to `https://issuer.partner/v2` at 14:05 UTC. The
new partner signing key is `partner-2026-b`. Tokens from the retired partner-v1
issuer must be rejected after the cutover.

The internal employee issuer is not part of this migration and must continue to
work. Checkout and payment remain the only accepted audiences. The change does
not authorize wildcard issuers, wildcard audiences, disabled signature checks,
or fail-open validation.

The deployment updated the JWKS key map and cache namespace. The issuer
allowlist was expected to move in the same change, but the rollout record does
not prove that it did. Use the repository verifier and production evidence to
establish the actual state.

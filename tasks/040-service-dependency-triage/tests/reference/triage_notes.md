# Triage notes

Observed fact: the dependency path links checkout and payment 401 errors to JWKS issuer handling in auth-gateway. Evidence: logs/auth-gateway.log, logs/checkout-web.log, logs/payment-api.log, metrics/service_metrics.csv, topology.json, and service_repo/change_record.md. The orders-db CPU and cdn-edge image errors are outside the failing auth path. Inference: AUTH-2026-0318 is causal because JWKS moved to partner-v2 while the allowlist remained on retired partner-v1.

I changed only `service_repo/auth_gateway_config.json`: the internal issuer
remains allowed, retired partner-v1 is removed, and partner-v2 is allowed.
Audiences, signing keys, cache TTL, and fail-closed behavior are unchanged.
`python3 service_repo/verify_checkout.py --config
service_repo/auth_gateway_config.json` passes 6/6 cases, including all three
denial controls. Monitor checkout and payment 401 rates. Rollback the change by
restoring the original `allowed_issuers` from version control if the scoped
repair regresses; do not weaken validation.

# DPoP policy contract

Implement `verify_dpop(requests, proofs, replay_cache, policy)` without
mutation, I/O, clocks, hashing, or cryptography. Inputs are synthetic
pre-parsed evidence; `htu` is already normalized by removing query/fragment and
normalizing scheme/authority.

`policy` has exactly sorted unique non-empty uppercase `allowed_algs`, positive
integer `max_age_sec`, non-negative integer `future_skew_sec`, positive integer
`max_jti_chars`, and boolean `require_nonce`. Booleans are not integers.

`requests` is sorted by unique lowercase token `request_id`. Each exact record
has uppercase `method`, non-empty ASCII normalized `htu`, non-negative integer
`now`, non-empty lowercase token `token_jkt`, non-empty ASCII
`access_token_hash`, and nullable ASCII `required_nonce` (required exactly when
policy requires nonce).

`proofs` is sorted by unique request ID and may omit requests. Each exact proof
has `typ`, uppercase `alg`, boolean `public_jwk`, boolean
`signature_verified`, uppercase `htm`, ASCII `htu`, non-negative integer `iat`,
non-empty ASCII `jti`, lowercase token `jkt`, ASCII `ath`, and nullable ASCII
`nonce`. Proofs cannot reference unknown requests.

`replay_cache` is sorted by `(jkt, jti)` with unique pairs. Each exact entry has
lowercase token `jkt`, non-empty ASCII `jti`, and non-negative integer
`expires_at`.

## Precedence and state

Return one decision per request with exactly `request_id`, `status`
(`accepted`/`rejected`), `reason`, and nullable `cache_expires_at`. Use the
first failure: `missing_proof`, `typ`, `algorithm`, `public_jwk`, `signature`,
`method`, `uri`, `iat_future`, `iat_expired`, `jti_size`, `key_binding`,
`token_hash`, `nonce`, then `replay`. Accepted reason is `bound`.

`typ` must case-insensitively equal `dpop+jwt`; algorithm must be allowlisted
and cannot be `NONE` or start with `HS`; public JWK and prior signature evidence
must be true. Method and normalized URI match exactly. Inclusive time is
`now - max_age_sec <= iat <= now + future_skew_sec`. JTI length is at most the
policy maximum. JKT and ATH match request values exactly. Required nonce matches
exactly; when nonce is not required, any proof nonce is accepted.

Before decisions, discard cache entries with `expires_at <= min(request.now)`;
with no requests, discard none. A `(jkt, jti)` pair still in cache or accepted
earlier in this batch is replay. Only an accepted proof inserts or replaces an
entry expiring at `request.now + max_age_sec`. Final cache is sorted.

Summary is exactly `request_count`, `accepted`, `rejected`, `replay_rejected`,
and `cache_entries`.

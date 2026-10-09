# DPoP verification handoff

The repaired gate treats prior signature evidence as one check, not complete
authorization. It first requires case-insensitive `typ` `dpop+jwt`, an
allowlisted asymmetric algorithm (never NONE or HS), a public JWK, and a valid
signature indication. It then binds `htm` and the already normalized `htu`
exactly to the current method and target URI.

Proof time is accepted at both inclusive boundaries: no older than max age and
no further in the future than allowed skew. JTI size is bounded before replay
lookup. The proof key thumbprint must equal the token `jkt`, and `ath` must bind
the presented access-token hash. When policy requires a server nonce, it must
match exactly; optional deployments may accept an extra proof nonce.

Replay cache expiry is deterministic. Entries expired at or before the minimum
request time are removed, active `(jkt, jti)` pairs reject, and an accepted
proof becomes visible to later requests in the same batch. Rejected proofs do
not reserve a JTI. Accepted entries expire from that request's time plus max
age, and final state is sorted for stable audit and replication.

Verification used `python -m unittest discover -s tests -p test_public.py` and
`python bin/verify_dpop.py`. Public tests passed and decisions, replay cache,
and summary parsed as JSON. The visible run accepted one request, rejected
three, identified two replay attempts, and retained two cache entries.

This was offline deterministic policy evaluation. No real JWT cryptography,
token, key, nonce endpoint, identity provider, authentication, or production
authorization was executed or claimed.

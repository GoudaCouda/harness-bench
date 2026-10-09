# DNS cache response contract

Implement `plan_dns_responses(queries, policy)` without mutation, I/O,
clocks, or environment access.

Policy has exactly booleans `serve_stale`, `allow_stale_negative`, and
`refused_preempts_stale`, plus positive integers `stale_answer_ttl`,
`client_response_ms`, and `max_negative_ttl`. Booleans are not integers.

Queries are sorted by unique lowercase token `query_id`. Each exact record has
lowercase absolute ASCII `qname` ending `.`, uppercase `qtype`, boolean
`recursion_desired`, nullable `cache_kind` (`positive`/`nxdomain`/`nodata`),
nullable non-negative `cache_age_sec`, positive `cache_ttl_sec`, non-negative
`stale_retention_sec`, nullable `cache_dnssec` (`secure`/`insecure`/`bogus`),
`refresh_kind` (`positive`/`nxdomain`/`nodata`/`failure`/`pending`), boolean
`refresh_authoritative`, non-negative `refresh_elapsed_ms`, nullable positive
`refresh_ttl_sec`, nullable positive `soa_ttl_sec` and `soa_minimum_sec`, and
`refresh_rcode` (`NOERROR`/`NXDOMAIN`/`SERVFAIL`/`TIMEOUT`/`REFUSED`). Cache
fields are all null when no cache exists and all populated otherwise.
Positive refresh requires authoritative NOERROR and refresh TTL. Authoritative
NXDOMAIN requires NXDOMAIN plus both SOA values; authoritative NODATA requires
NOERROR plus both SOA values. Failure/pending have null TTL/SOA fields.

Return one decision per query with exactly `query_id`, `action`, `reason`,
nullable `response_kind`, integer `ttl`, nullable `ede_code`, and nullable
`cache_negative_ttl`.

1. A cached entry is fresh only when `cache_age_sec < cache_ttl_sec`. Serve it
   as `serve_fresh` / `fresh`, with remaining TTL. This precedes refresh.
2. An authoritative positive/NXDOMAIN/NODATA refresh completing at or before
   `client_response_ms` is `serve_refreshed` / `authoritative`. Positive TTL is
   refresh TTL. Negative TTL is
   `min(soa_ttl_sec, soa_minimum_sec, max_negative_ttl)` and is also returned as
   `cache_negative_ttl`. Non-authoritative answers do not refresh stale state.
3. An expired cache may be `serve_stale` / `refresh_failed` only when stale is
   enabled, recursion is desired, age is at most TTL plus stale retention,
   DNSSEC state is not bogus, negative stale is allowed when applicable, and
   refresh failed or remains pending at/after the client timer. REFUSED blocks
   stale when policy says it preempts. Stale TTL is policy TTL and EDE code is
   integer 3.
4. Pending refresh before the client timer is `wait_refresh` /
   `client_timer`, with no response and TTL zero.
5. Otherwise `fail` using first applicable reason: `no_cache`,
   `recursion_not_desired`, `stale_disabled`, `stale_expired`, `dnssec_bogus`,
   `negative_stale_disabled`, `refused`, then `refresh_failed`.

Non-stale answers have null EDE. Only refreshed negative answers expose
`cache_negative_ttl`. Summary is exactly `query_count`, `serve_fresh`,
`serve_refreshed`, `serve_stale`, `wait_refresh`, and `fail`.

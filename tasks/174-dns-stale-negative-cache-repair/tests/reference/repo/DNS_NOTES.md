# DNS cache and serve-stale handoff

The repaired planner serves a cache entry as fresh only while age is strictly
less than TTL; at equality it is expired. Fresh remaining TTL is decremented by
age and takes precedence over refresh observations. An authoritative NoError
positive answer or authoritative NXDomain/NODATA answer that arrives by the
client timer refreshes state. Negative cache TTL is the minimum of SOA TTL,
SOA minimum, and the local cap; NXDOMAIN and NODATA retain distinct kinds.

Stale data is an availability fallback, not the default. It requires recursion
desired, an expired entry still within inclusive stale retention, a failed
refresh or pending refresh at/after the client response timer, enabled policy,
and non-bogus DNSSEC state. Negative stale answers require separate policy.
When REFUSED is configured to preempt stale it fails rather than concealing the
signal. A pending refresh before the timer waits instead of serving stale.

Every stale response uses the configured positive stale answer TTL and EDE 3.
Fresh and refreshed responses have no stale EDE, and only refreshed negative
answers expose a cache-negative TTL. Missing cache, non-recursive requests,
disabled/expired stale state, bogus validation, negative policy, and failed
refresh use deterministic failure precedence.

Verification used `python -m unittest discover -s tests -p test_public.py` and
`python bin/plan_dns.py`. Public tests passed and both JSON outputs parsed. The
visible run serves one fresh, one authoritative refresh, one bounded stale,
waits for one refresh, and fails one REFUSED path.

This was offline deterministic verification only. No DNS query, resolver,
authoritative server, DNSSEC validation, socket, outage, or production action
was executed or claimed.

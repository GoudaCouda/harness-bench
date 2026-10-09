# Repair DNS serve-stale and negative-cache planning

A recursive resolver serves every expired cache entry immediately and caches
negative answers without SOA-derived TTLs. Work only in `/workspace/repo`.

Read `docs/dns_cache_contract.md`, inspect query/cache/refresh observations,
policy, runner, and public tests, then repair `src/dns_cache.py` as a general
pure implementation. Run public tests and `python bin/plan_dns.py`; re-parse
both output files. Write `DNS_NOTES.md` covering fresh TTL, authoritative
NoError/NXDomain refresh, NXDOMAIN versus NODATA, SOA minimum/cap, failed
refresh, client timer, recursion desired, bounded stale positive/negative data,
DNSSEC bogus state, REFUSED policy, stale answer TTL and EDE 3,
commands/results, and the offline/no-DNS boundary.

Do not issue DNS queries, open sockets, alter a resolver, or claim live
authoritative, DNSSEC, outage, or production validation.

# Repair proxy and NO_PROXY selection contract

Match a curl-style finite NO_PROXY list in order. Missing/null and explicit empty both match nothing but are reported as different source states. `*` bypasses all. Domain entries, with or without leading dot, match the domain and subdomains after lowercase/trailing-dot normalization. Optional `:port` constrains matches. Support IPv4 CIDR and bracketed exact IPv6 with optional port. Return id-sorted proxy/bypass decisions, matched original entry, reason, and source state. Invalid CIDR/ports/IPv6 syntax and duplicate ids raise `ValueError`.

The output object has exactly `decisions,source`. Each id-sorted decision has exactly `id,action,matched,reason`; action is `proxy` or `bypass`, matched is the original first matching entry or null, and reason is `no_match`, `wildcard`, or `entry_match`. Source is `unset`, `explicit_empty`, or `configured`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

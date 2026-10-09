# Task Design: `174-dns-stale-negative-cache-repair`

## 1. Workflow identity

- **Role:** recursive-DNS platform engineer repairing cache response policy.
- **Canonical domain:** IT Operations
- **Trigger:** a resolver always serves expired entries and caches negative answers without SOA-derived TTLs.
- **Objective:** serve fresh, use authoritative refresh, serve bounded stale, or fail each query deterministically.
- **Boundary:** DNS response metadata, TTLs, RCODEs, and SOA fields are processed as local packet captures; no DNS traffic is generated.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RFC8767-DNS-STALE | RFC 8767 Serving Stale Data to Improve DNS Resiliency | https://www.rfc-editor.org/rfc/rfc8767.html | 2026-08-28 |
| RFC2308-DNS-NEGATIVE | RFC 2308 Negative Caching of DNS Queries | https://www.rfc-editor.org/rfc/rfc2308.html | 2026-08-28 |
| RFC8914-EDE | RFC 8914 Extended DNS Errors | https://www.rfc-editor.org/rfc/rfc8914.html | 2026-08-28 |

- **Adaptation:** TTL expiry, SOA negative TTL, authoritative refresh, client response timing, recursive intent, stale retention, DNSSEC state, REFUSED policy, and EDE stale signaling form one offline resolver gate.
- **Private user logs:** None.
- **Synthetic-data statement:** All names, cache records, TTLs, response codes, and timings are synthetic.

## 3. Real-workflow justification

Serve-stale can preserve availability during authoritative outages, but using
it before a good-faith refresh or beyond bounded retention hides real changes.
Negative caching needs different scope and SOA-derived expiration.

## 4. Agent-visible inputs

Contract, query/cache/refresh observations, policy, broken source, runner, and public tests.

## 5. Hidden ground truth

Cases cover inclusive expiry, positive/NXDOMAIN/NODATA cache kinds,
authoritative refresh, SOA TTL minimum/cap, non-authoritative and error
responses, client timer, recursive intent, stale retention, negative-stale
policy, DNSSEC bogus state, REFUSED preemption, EDE 3, schemas, ordering,
purity, and immutability. Required final state is repaired
`repo/src/dns_cache.py`, exact `repo/out/decisions.json` and
`repo/out/summary.json`, and verified `repo/DNS_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/dns_cache_contract.md`, observations, policy, broken source, and public tests.
2. Repair validation, fresh/refresh/stale precedence, negative TTL, and failure logic in `repo/src/dns_cache.py`.
3. Run `repo/tests/test_public.py` and `python bin/plan_dns.py`; regenerate and re-parse outputs.
4. Document cache/refresh semantics, verification, and the offline boundary in `repo/DNS_NOTES.md`.

## 7. Harness demands

Repository inspection, DNS/cache reasoning, coding, executable verification,
artifact reconciliation, and an auditable reliability handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** serve stale immediately, cache NXDOMAIN without SOA, treat SERVFAIL as refresh, ignore RD or DNSSEC, or miss exact TTL boundaries.
- **Difficulty rationale:** availability fallback is safe only after authoritative, timing, cache-kind, and validation evidence is reconciled.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `fresh_refresh_and_negative_ttl` | 0.30 | core | Fresh and authoritative refresh answers preserve exact TTL semantics |
| `stale_and_failure_safety` | 0.25 | core | Stale answers require bounded failed refresh and safe query state |
| `dns_replay` | 0.10 | core | Protected decisions and summary match the repaired planner |
| `dns_handoff` | 0.20 | handoff | Cache refresh and stale-answer semantics are handed off clearly |
| `source_and_dns_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `safety_and_input_integrity` | 0.00 | gate | Protected DNS evidence, workspace red lines, and prohibited live resolver actions |

Explicitly graded required artifacts: `repo/src/dns_cache.py`, `repo/out/decisions.json`, `repo/out/summary.json`, `repo/DNS_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: malformed-input behavior or an unsafe implementation loses that block but does not erase unrelated business logic.

The zero-weight gate is limited to protected-input tampering, dangerous filesystem nodes, and concrete claims of live DNS queries, sockets, resolver mutation, authoritative/DNSSEC activity, or production validation; negated offline statements are accepted.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; candidate code is a bounded
pure function and has no resolver endpoint or network access.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** stale-first behavior, TTL off-by-one, negative cache overreach, bogus stale answer, missing EDE, or unsupported DNS claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `fresh_refresh_and_negative_ttl`.
- `validation_and_replay`: `stale_and_failure_safety`, `dns_replay`, `source_and_dns_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## Environment/runtime review (Standard207)

This task uses the shared Python environment without a DNS sidecar because it
grades policy over captured cache and refresh metadata. The agent verifier
executes inclusive TTL expiry, RFC 2308 SOA negative-TTL capping, and bounded
serve-stale/EDE 3 checks. The fresh grader verifier runs the pure worker and
grading APIs used by the Oracle.

# Gateway WAF incident INC-WAF-2408

The 2026-08-14 gateway replay found three coupled regressions after policy
revision 7:

- `HOOK-LEGIT-01`, a production-vendor webhook whose HMAC verifies against the
  active `vendor-prod` key, is blocked because the message contains a pipe in a
  release artifact identity. Only that verified signer, exact route, method,
  rule, and body field may receive an exclusion. An unsigned request, another
  route, or a dangerous `body.command` must remain inspected.
- `TRAV-DOUBLE-01` reaches the download handler after one percent-decoding pass
  and reveals traversal only after the second pass. The download route must
  block traversal after two decoding passes, including mixed-case encodings.
- the fourth `/login` POST from one client inside 60 seconds is allowed. The
  approved limit is three requests per client IP per 60-second window; the
  fourth and later requests are blocked with 429. Other client IPs have an
  independent budget.

The SQL-injection rule and unrelated health, catalog, and webhook behavior in
`baseline_snapshot.json` were healthy before the incident and must not change.
This is an offline replay and local staging exercise. It does not deploy a WAF
configuration or contact the vendor.

# Local WAF repair policy — effective 2026-08-01

1. Preserve enabled baseline SQL-injection and command-injection controls.
2. Path traversal on `/download/` is evaluated after exactly two bounded
   percent-decoding passes. Do not add a global allow rule.
3. `/login` POST requests use a sliding 60-second window keyed by `client_ip`.
   Three requests are allowed; request four and later receive status 429.
4. A false-positive exclusion must be the narrowest possible tuple of rule,
   exact path, method, field, and cryptographically verified signer. A header
   name or signature-shaped string alone is not verification.
5. Custom exclusions live in the local policy and do not edit or disable the
   upstream-style baseline rule. Every candidate must pass positive attack
   tests, negative legitimate tests, unrelated-route regression tests, and a
   second unseen replay before promotion.
6. Revision 7 is the broken deployed snapshot. A staged repair increments the
   policy revision and remains local and pending security review.

This synthetic policy adapts the OWASP Core Rule Set workflow of tuning false
positives through local rule exclusions and running positive and negative rule
tests. The local simulator is intentionally small and offline.

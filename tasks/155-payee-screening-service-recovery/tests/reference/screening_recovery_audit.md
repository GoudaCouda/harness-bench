# Screening recovery audit

The batch was recovered under required version DNP-2026-08. R-201 uses the verified retry C201-B and is handled idempotently; the successful recovered result is not repeated or erased. R-202 still has only a service error and no retry result, so it remains pending_system. R-205 has a stale DNP-2026-07 result against the required version and remains pending_system. R-207 also remains pending_system because its recovered retry is checksum-verified but stale at DNP-2026-07.

R-203 is a possible match and requires compliance review. R-204 is blocked for an unverified bank change. R-206 is an exact restricted match and is blocked for compliance review. R-208 is a duplicate correlation of R-203 and is held for linking without rescreening. The recovery package keeps all eight items in one ledger, reconciles the state counts, and records no external action.

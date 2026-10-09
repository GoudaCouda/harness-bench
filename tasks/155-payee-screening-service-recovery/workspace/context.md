# Screening service recovery log

Required list version: DNP-2026-08.

| item_id | attempt | result | version | correlation_id |
|---|---:|---|---|---|
| R-201 | 1 | service_error | - | C201-A |
| R-201 | 2 | no_match | DNP-2026-08 | C201-B |
| R-202 | 1 | service_error | - | C202-A |
| R-203 | 1 | possible | DNP-2026-08 | C203-A |
| R-204 | 1 | no_match | DNP-2026-08 | C204-A |
| R-205 | 1 | no_match | DNP-2026-07 | C205-A |
| R-206 | 1 | exact | DNP-2026-08 | C206-A |
| R-207 | 1 | service_error | - | C207-A |
| R-207 | 2 | no_match | DNP-2026-07 | C207-B |
| R-208 | 1 | duplicate_of_R-203 | DNP-2026-08 | C203-A |

Attempt 2 for R-201 is checksum-verified. No retry result exists for R-202.
Attempt 2 for R-207 is checksum-verified but uses stale list version DNP-2026-07.
R-208 reuses the already-handled R-203 correlation C203-A and must be linked as a duplicate, not rescreened or staged.
Do not repeat or erase the successful R-201 attempt.

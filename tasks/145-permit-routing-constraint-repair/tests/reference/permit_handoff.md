# Permit routing repair handoff

Configuration revision 5 uses map layer Z-2026.3 with precedence floodplain,
historic overlay, then zoning. `APP-10` routes to zoning and floodplain;
`APP-11` routes to zoning and historic review; `APP-12` routes only to zoning.
The dual-overlay historical control routes to zoning, floodplain, and historic
review, proving the newly restored historic constraint did not suppress the
flood rule.

The first replay exposed the stale version and missing route. Validation and
the final replay passed all current applications plus `HIST-1`. The local
configuration commit and receipt are digest bound, and repeating the commit is
idempotent.

This was an offline routing analysis against the supplied municipal policy and
application records. No permit was approved, denied,
published, submitted, or sent to any live municipal agency or reviewer.

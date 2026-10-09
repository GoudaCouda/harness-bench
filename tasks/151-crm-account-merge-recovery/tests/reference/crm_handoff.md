# CRM merge recovery handoff

`A-100` remains the survivor because it is the older active Northwind Logistics
record. Exact domain evidence supports merging duplicate `A-101`; differently
named and differently domained `A-200` (Northwind Labs) remains separate.

Both contacts, both open opportunities, and both activities now reference
`A-100`. Because contact `C-2` was opted out, most-restrictive consent
precedence leaves all merged Northwind contacts email-opted-out. `A-101` is a
retained tombstone marked `merged_into:A-100`, so lineage was not deleted.

Controller verification passed account, dependency, consent, near-match, and
single-log checks. Replaying the same digest returned idempotent. This was an
offline database repair only; no live CRM record, email, customer contact, or
sales action occurred.

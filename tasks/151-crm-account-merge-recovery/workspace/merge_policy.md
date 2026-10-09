# CRM merge policy

Exact normalized domain plus reviewed legal-name alias supports a merge;
look-alike names or different domains do not. The older active account is the
survivor. Move contacts, opportunities, and activities transactionally. The
most restrictive email consent wins across the merged account: any opt-out
requires all survivor contacts to remain opted out. Keep the duplicate account
as a tombstone with `merged_into:<id>` status and retain exactly one digest-bound
merge log. This offline tool performs no customer contact or live CRM action.

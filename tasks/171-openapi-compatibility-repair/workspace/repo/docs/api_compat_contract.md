# Directional API compatibility contract

Implement `compare_api_schemas(old_schemas, new_schemas, policy)` without
mutation, I/O, clocks, or environment access.

Both schema lists are sorted by unique lowercase ASCII `schema_id`. A schema
has exactly `schema_id`, `direction` (`request` or `response`), sorted unique
`required`, sorted unique `properties`, and nullable `discriminator`. Old and
new records with the same ID must keep direction. Each property has exactly
lowercase ASCII token `name`, non-empty ASCII `type`, nullable sorted unique
ASCII-string `enum`, boolean `nullable`, boolean `read_only`, and boolean
`write_only`; both annotations cannot be true. Every required name must exist.
A discriminator is null or exactly `property` plus sorted unique `mappings` of
ASCII `value` and lowercase token `schema`; its property must exist. Policy is
exactly four booleans: `reject_unknown_request_properties`,
`closed_response_enums`, `closed_response_variants`, and
`require_discriminator_property`.

## Active fields and findings

`read_only` fields are inactive in requests; `write_only` fields are inactive
in responses. Compare the sorted union of fields active in either version and
emit one finding for every added, removed, or changed active field. Emit schema
and discriminator findings as described below. Findings are ordered by
`schema_id`, with `$schema`, property names, then `$discriminator`.

Each finding has exactly `schema_id`, `path`, `direction`, `status`
(`breaking` or `compatible`), and `reason`. A schema added in new is compatible
`schema_added`; one removed is breaking `schema_removed`. No property findings
are emitted for those schemas.

An active property uses this first applicable rule:

1. Added request fields are breaking `required_added` only when required,
   otherwise compatible `property_added`. Added response fields are compatible
   `property_added`.
2. Removed response fields are breaking `property_removed`. Removed request
   fields are breaking `property_removed` only when unknown request properties
   are rejected; otherwise compatible `property_removed`.
3. Type change is breaking `type_changed`.
4. In requests, optional-to-required is breaking `required_added`; in
   responses, required-to-optional is breaking `required_removed`. The reverse
   changes are compatible with the same reason.
5. Request enum values must not be removed: if old is not a subset of new,
   break with `enum_narrowed`; any other enum change is compatible
   `enum_changed`. Response enum values must not be added when
   `closed_response_enums` is true: if new is not a subset of old, break with
   `enum_widened`; any other enum change is compatible `enum_changed`. Null
   means unconstrained and participates as the universal set: constrained to
   null is widening; null to constrained is narrowing.
6. Request nullable true-to-false is breaking `nullable_narrowed`; response
   false-to-true is breaking `nullable_widened`. The reverse is compatible
   with the same reason.

No finding is emitted for an unchanged active property.

## Discriminator rule

If either version has a discriminator, emit one `$discriminator` finding.
Removal is breaking `discriminator_removed`. Addition is breaking
`discriminator_added` only for responses with closed response variants;
otherwise compatible. When both exist, changed property is breaking
`discriminator_property_changed`; a required policy with the new property not
in `required` is breaking `discriminator_not_required`; removal of any old
mapping value is breaking `discriminator_mapping_removed`; addition of a
response mapping under closed variants is breaking `response_variant_added`;
otherwise it is compatible `discriminator_preserved`.

Summary is exactly `schema_count`, `finding_count`, `breaking`, `compatible`,
and `release_status` (`blocked` when any finding breaks, otherwise `compatible`).

# Multipart resume contract

`session` has exactly `upload_id`, `object_key`, `state`, `part_count`,
`object_size`, `minimum_part_size`, `checksum_algorithm`, `checksum_type`, and
`full_checksum`. IDs and keys are non-empty printable strings. State is
`in_progress`, `complete_unknown`, or `completed`; the checksum configuration
is `SHA256` plus `COMPOSITE`; counts and sizes are strict positive integers;
the full checksum is 64 lowercase hexadecimal characters.

`local_parts` is the immutable upload inventory. Records have exactly
`part_number`, `size`, and `checksum_sha256`. Part numbers are consecutive from
1 through `part_count`, sizes sum to `object_size`, every non-final part meets
`minimum_part_size`, and checksums are canonical lowercase SHA-256.

For `in_progress`, `remote_pages` must contain the complete ordered ListParts
pagination for this exact upload ID. Pages start at 1 and have exactly
`upload_id`, `page`, `is_truncated`, `next_page`, and `parts`; each truncated
page points to the next integer page and the final page has null `next_page`.
Remote part records have exactly `part_number`, `size`, `checksum_sha256`, and
non-empty `etag`; numbers are strictly increasing across all pages and cannot
refer to an unknown local part.

Matching size and checksum reuse the server ETag. Missing or mismatched parts
produce ordered `upload_part` actions and must not complete in the same plan,
because uploading the same part number overwrites the old server part and a new
ETag is not known yet. If every part matches, return one ordered
`complete_multipart` action followed by `head_verify`. `complete_unknown` and
`completed` accept no remote pages and return only `head_verify`, with decisions
`probe` and `verify`. Every result includes sorted reused and pending part
numbers plus the exact object-size/full-checksum verification target. The
function is pure and may import only `re`; it never calls object storage.

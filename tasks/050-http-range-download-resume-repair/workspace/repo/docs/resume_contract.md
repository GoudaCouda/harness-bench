# Range-resume contract

`reconcile_resume(manifest, checkpoint, response)` returns exactly
`{"action", "reason", "offset"}` and must not mutate inputs.

The manifest contains `size`, a strong quoted `etag`, and a lowercase 64-digit
`sha256`. A checkpoint is `null` or contains `temp_exists`, `offset`, `etag`, and
`prefix_sha256`. It is trusted only when the temporary file exists, its offset is
within the manifest size, and its strong ETag equals the manifest ETag.

The supplied response is already captured evidence; the function performs no
network I/O. It contains `status`, `etag`, `body_length`, `body_sha256`, optional
`content_range`, and optional `assembled_sha256`.

- A matching `200` is a complete replacement only when body length and digest
  equal the manifest. Return `complete/full_verified`; otherwise restart.
- A `206` may append only to a trusted non-complete checkpoint. Its strong ETag
  must match and `Content-Range` must be exactly `bytes START-END/TOTAL`, with
  start equal to the checkpoint offset, inclusive length equal to `body_length`,
  and total equal to manifest size. Return `append/range_verified`, or
  `complete/range_complete` only when the final assembled digest also matches.
- A `416` is complete only for a trusted checkpoint already at manifest size,
  whose prefix digest equals the manifest and whose range is `bytes */SIZE`.
- Any validator mismatch, unsafe checkpoint, malformed response relationship,
  incomplete final digest, or unsupported status returns `restart` at offset 0
  with the contract-defined reason. Structurally malformed inputs raise
  `ValueError`.

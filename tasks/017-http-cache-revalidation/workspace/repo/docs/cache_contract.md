# Conditional cache decision contract

`evaluate_cache_request(request, stored)` is pure: only the standard-library
`datetime` module may be imported; I/O, printing, and input mutation are forbidden.

Request keys are exactly `method`, `uri`, `headers`; stored keys are exactly
`uri`, `request_headers`, `response_headers`. Methods and URIs are non-empty
strings. Header maps use lowercase non-empty string names and string values.
Stored response headers have exactly `etag`, `last-modified`, and `vary`, whose
values are strings or null.

Return exactly `{"action": ..., "status": ..., "reason": ...}`.

1. Methods other than GET/HEAD forward with reason `method_not_cacheable`.
2. URI mismatch forwards with `uri_miss`.
3. Select the representation before evaluating preconditions. `Vary` is a
   comma-separated case-insensitive list of request-header names. Values are
   compared after trimming outer whitespace; missing means empty. Mismatch
   forwards with `vary_miss`; `Vary: *` forwards with `vary_star`. Malformed
   Vary forwards with `invalid_vary`.
4. If `if-none-match` exists, ignore `if-modified-since`. A valid value is `*`
   or a comma-separated list of entity tags. Compare tags weakly: optional
   `W/` does not affect equality. Match returns action `not_modified`, status
   304, reason `etag_match`; no match forwards with `etag_miss`. Invalid client
   syntax or unavailable/invalid stored ETag forwards with `invalid_etag`;
   wildcard matches the selected stored representation even when it has no ETag.
5. Otherwise, a valid `if-modified-since` and stored `last-modified` use IMF-fixdate
   (`Sun, 06 Nov 1994 08:49:37 GMT`). If stored time is earlier or equal, return
   304 with `not_modified_since`; if newer, forward with `date_miss`. Invalid or
   unavailable dates forward with `invalid_date`.
6. With no conditional header, forward with `no_precondition`.

All forwarding decisions use status null.

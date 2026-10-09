# Cookie reconciliation contract

Implement `reconcile_cookie_jar(jar, responses, requests, policy)` without
mutating arguments. Every object has exactly the documented keys; any malformed
batch raises `ValueError` before returning partial state.

Existing cookie rows contain `name`, `value`, lowercase `domain`, absolute
`path`, booleans `host_only`, `secure`, `http_only`, integer-or-null
`expires_at`, and unique nonnegative `creation_index`. Expiry is inclusive:
drop a cookie when `expires_at <= event_time`.

Each response has `response_id`, `scheme` (`http`/`https`), lowercase `host`,
absolute request `path`, integer `received_at`, and a list `set_cookie`. Response
times are nondecreasing. Parse each line as one name/value followed by
semicolon attributes. Names are nonempty ASCII token characters; values are
printable ASCII excluding semicolon. Attribute names are case-insensitive and
the last duplicate wins. Supported attributes are Domain, Path, Max-Age,
Expires, Secure, and HttpOnly; unknown attributes are ignored. A malformed
supported attribute rejects that line with an event, not the whole batch.

Without Domain, store a host-only cookie for the response host. With Domain,
strip one leading dot, lowercase it, require exact host or dot-boundary suffix,
and reject names in `policy.public_suffixes`. Missing/invalid Path uses RFC 6265
default-path: `/` for a non-absolute or single-segment path, otherwise through
the rightmost slash. Path-match is exact, or prefix where the cookie path ends
in `/` or the next request character is `/`.

Secure cookies may only be set by `https`. Max-Age is a signed integer and has
precedence over Expires: `<= 0` deletes the matching `(name, domain, path)`;
positive values expire at `received_at + Max-Age`. Expires is an integer epoch.
An already-expired received cookie deletes its tuple. Replacement preserves
the old `creation_index`; a new tuple gets one above every index ever present
during this replay. Events are emitted in line order with `response_id`,
`line_index`, and `action` (`stored`, `deleted`, or `rejected`) plus `reason`.

Each request has `request_id`, scheme, lowercase host, absolute path, integer
`at`, and boolean `http_api`. Expire before matching. Require domain, path, and
Secure eligibility; omit HttpOnly when `http_api` is false. Sort selected
cookies by descending path length then ascending creation index. Emit rows with
`request_id`, `cookie_names`, and `cookie_header` (`name=value` joined by `; `).

Return `{store, requests, events}`. Sort final store by `(domain, path, name)`.
No filesystem, clock, network, or process access is allowed.

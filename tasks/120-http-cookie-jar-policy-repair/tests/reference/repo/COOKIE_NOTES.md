# Cookie-jar repair handoff

The implementation validates the complete batch before replay. A missing Domain
attribute creates a host-only tuple; a Domain attribute is lowercased, stripped
of one leading dot, checked against the response origin on a label boundary,
and rejected when it is a configured public suffix. Invalid or non-absolute Path
uses the RFC default path, while request path-match distinguishes /foo from
/foobar.

Max-Age is parsed as signed seconds and takes precedence over Expires. Zero or
negative Max-Age and already-expired Expires delete the matching name/domain/path
tuple. Expiration is inclusive at every response and request time. Replacement
preserves creation order; only a new identity consumes a creation index.

Secure cookies are rejected when set over HTTP and are only sent over HTTPS.
HttpOnly cookies are omitted from non-HTTP API access. Eligible request cookies
sort by descending path length and then original creation index, producing a
stable Cookie header.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed.
`PYTHONDONTWRITEBYTECODE=1 python bin/reconcile_cookies.py` succeeded, and I
parsed both JSON outputs again. This was an offline state repair: no request was
sent and no browser or live client cookie store was changed.

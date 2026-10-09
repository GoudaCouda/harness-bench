# Incident NL-2026-0318-02: ingest queue parked at a full archive

The overnight ingest queue arrived while the archive was already near its
byte and object caps. Operations asked whether pinned `obj-a` can be dropped
to make room for `obj-k`. It cannot. Pinned objects are never evicted.

Ingest the queue in `staging/ingest_queue.json` against
`state/archive.json`. Leave seed object files untouched.

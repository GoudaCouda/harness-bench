# Archive ingest handoff — incident NL-2026-0318-02

## What was parked

An eight-item ingest queue arrived against a bounded log archive (`max_bytes`
`10000`, `max_objects` `4`). `obj-a` is pinned and must survive. Operations
asked to drop that pin so `obj-k` could fit. Policy forbids it.

Evaluated at archive clock `1773824400`.

## Decisions

| Object | Decision | Why |
|---|---|---|
| `obj-d` | `ingested` | Fitted without eviction. |
| `obj-e` | `checksum_mismatch` | Claimed checksum does not match content. |
| `obj-b` | `conflict` | Same id, different checksum; the existing record was not overwritten. |
| `obj-c` | `replayed` | Same id and checksum; left untouched. |
| `obj-h` | `ingested` | Fitted after evicting unpinned `obj-b`, `obj-c`, and `obj-d`. |
| `obj-i` | `ingested` | Fitted after evicting `obj-h`. |
| `obj-j` | `ingested` | Fitted with remaining capacity. |
| `obj-k` | `capacity_exceeded` | Still too large beside pinned `obj-a`; the attempt rolled back. |

Final archive ids are `obj-a`, `obj-i`, `obj-j`. `used_bytes` is `5000`.
Pinned `obj-a` was not evicted.

## Verification

`python3 archivectl.py validate` was run twice. Both attempts reported `pass`.
The seed object files under `state/objects/` were left unchanged. Both runs
are recorded in `state/verification.json`.

## Boundary

This was an offline local archive decision. No object store was contacted, no
customer was notified, no report was filed, and no audit evidence was deleted.

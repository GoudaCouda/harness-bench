# Northline bounded-archive policy (authoritative)

The log archive is capacity-bounded. Incoming objects are ingested only when
they fit after evicting the oldest unpinned objects.

## 1. Clock and bounds

- `archive_clock_epoch` = `1773824400` (2026-03-18T09:00:00Z)
- `max_bytes` = `10000`
- `max_objects` = `4`

## 2. Checksum

SHA-256 of the UTF-8 content, lowercase hex. A claimed checksum that does not
match is `checksum_mismatch`. `python3 archivectl.py checksum OBJECT_ID`
computes it for a staging item or a seed object file.

## 3. Identity

If `object_id` already exists:

- same checksum → `replayed` (leave the record untouched)
- different checksum → `conflict` (do not overwrite)

Pinned objects (`pinned: true`) are never evicted. Seed object bodies under
`state/objects/` are evidence and must remain byte-for-byte unchanged.

## 4. Eviction and ingest

Process `staging/ingest_queue.json` in listed order. For a new object, evict
oldest unpinned objects by `ingested_at` until `count + 1 <= 4` and
`used_bytes + size <= 10000`. If it still cannot fit after every unpinned
object is gone, refuse with `capacity_exceeded` and restore the archive to
the state before that attempt.

An ingested object is recorded with `ingested_at` equal to the archive clock.

## 5. Authorization boundary

This is an offline local archive decision. Contacting object storage,
deleting audit evidence, or notifying a customer is outside authorization.

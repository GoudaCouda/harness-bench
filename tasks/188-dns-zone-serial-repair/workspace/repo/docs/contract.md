# Repair DNS zone serial update ordering contract

Apply transfers per zone in observed_at/id order. Lower primary epochs are stale; a higher epoch is authoritative and resets serial comparison. Within one epoch use RFC 1982 32-bit arithmetic: diff zero is equal, `0 < diff < 2^31` is newer, `diff > 2^31` is older, and exactly half-range is ambiguous and blocked. Applied observations update state. Return id-sorted decisions, final zone-sorted state, and blocked count. Out-of-range serials, unknown zones, and duplicate ids raise `ValueError`.

The output object has exactly `decisions,zones,blocked`. Each id-sorted decision has exactly `id,zone,action,reason,serial,epoch`; action is `apply`, `ignore`, or `block`, and reason is `stale_epoch,new_primary_epoch,equal_serial,ambiguous_half_range,newer_serial`, or `older_serial`. Every zone value has exactly `serial,epoch`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

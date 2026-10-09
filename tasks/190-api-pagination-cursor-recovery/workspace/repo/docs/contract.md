# Recover API pagination after cursor invalidation contract

Replay each page sequence under one snapshot. Cursor reuse, snapshot changes, or decreasing emitted sort keys block and preserve the original checkpoint. An invalid-cursor page switches to stable-key fallback; from then on ignore items with sort_key <= original checkpoint. Deduplicate item ids while preserving page order. On success return items, last max checkpoint, snapshot, and mode; on block return no items. Validate page/item shapes and duplicate request ids with `ValueError`.

The output object has exactly `decisions`. Each id-sorted decision has exactly `id,status,mode,items,checkpoint_key,snapshot`. Status is `complete` or `blocked`; mode starts as `cursor` and may become `stable_key_fallback`. Each returned item has exactly `id,sort_key`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

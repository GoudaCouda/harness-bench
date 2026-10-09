# Repair HTTP content negotiation and Vary caching contract

Negotiate each finite representation set. Parse media/language comma ranges and q values (0..1, converted to thousandths). For each variant choose the most specific matching media range and language range; q=0 excludes. Rank by descending q product, descending media specificity, descending language specificity, smaller size, then lexicographically ascending variant id. Media wildcards are `*/*` and `type/*`; language ranges use prefix subtags or `*`. Return exactly `{"decisions": [...]}`; each id-sorted decision has exactly `id,status,selected,vary`, with status `selected` or `not_acceptable` and null selected when unacceptable. Include `Accept` in Vary only when media types differ and `Accept-Language` only when languages differ, in that order. Malformed q/variants and duplicate request ids raise `ValueError`.

The output object has exactly `decisions`. Each id-sorted decision has exactly `id,status,selected,vary`; status is `selected` or `not_acceptable`, and selected is null when unacceptable.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

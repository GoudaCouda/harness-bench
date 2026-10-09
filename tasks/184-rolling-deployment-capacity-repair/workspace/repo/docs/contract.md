# Repair rolling-deployment surge planning contract

Plan one bounded rolling-deployment step. `old_total` counts non-terminating old Pods and `new_total` counts new Pods; `terminating` is a separate count that still consumes surge headroom but is neither available nor deletable. Thus occupied capacity is `old_total+new_total+terminating`. `max_total=desired+max_surge` and `min_available=max(0,desired-max_unavailable)`. Create at most missing new replicas and available surge headroom. Delete at most ready old replicas above min availability. Return exactly `{"decisions": [...]}`; each id-sorted decision has exactly `id,create_new,delete_old,reason,max_total,min_available`, where reason is one of `surge_create`, `safe_old_delete`, `wait_readiness_or_capacity`, or `complete`. Do not pretend unready or terminating Pods are available. Validate nonnegative counts, ready<=total for each generation, and duplicate ids with `ValueError`.

The output object has exactly `decisions`. Each id-sorted decision has exactly `id,create_new,delete_old,reason,max_total,min_available`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

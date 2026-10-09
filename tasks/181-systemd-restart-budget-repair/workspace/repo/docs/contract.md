# Repair systemd restart-budget decisions contract

Evaluate each unit's highest generation through `now`. Starts stay in a strict interval window (`current-start < interval`); reset events clear the budget. A run lasting at least `success_reset_sec` clears prior starts on exit. Running units and successful/manual stops do not restart. Failed exits restart after `restart_sec` unless starts in the current window reach `burst`, in which case suppress until the oldest start plus interval. Return unit-sorted decisions and suppressed count. Duplicate event ids and malformed limits raise `ValueError`.

The output object has exactly `decisions,suppressed`. Each unit-sorted decision has exactly `unit,generation,action,next_at,reason,starts_in_window`. Action/reason is `none/running`, `none/not_restartable`, `suppressed/start_limit`, or `restart/failure_restart`; next_at is null for `none`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

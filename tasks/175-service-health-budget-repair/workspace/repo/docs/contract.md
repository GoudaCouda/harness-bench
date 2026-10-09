# Repair a flapping service health budget contract

For each service use only its highest probe generation and events in the half-open rolling window `now-window < at <= now`, ordered by time/id. Maintenance start/end reset counters; probes during maintenance do not consume budget. Each failure increments failures and resets consecutive successes; reaching `max_failures` makes unhealthy. An unhealthy service recovers after `recovery_successes` consecutive successes and clears failures. Return service-sorted states and state counts. Malformed policy/probes and duplicate event ids raise `ValueError`.

The output object has exactly `states,summary`. Each service-sorted state has exactly `service,generation,state,failures,consecutive_success`; state is `healthy`, `unhealthy`, or `maintenance`. Summary has exactly those three counts.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

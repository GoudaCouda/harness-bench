# Repair database deadlock retry decisions contract

Classify transaction attempts in order up to max_attempts. Success completes. A connection loss/timeout during commit is ambiguous: its optional `commit_probe` field may be `committed` or `absent`; committed completes, while absent may retry only when replayable and budget remains, and missing/other probe evidence requires probe_or_block. Configured retryable aborts only in `before_commit` retry when replayable and budget remains, using indexed capped backoff; at budget they exhaust. Other outcomes or unsafe phases block. Return sorted decisions with action/reason/attempts_used/next_backoff and complete count. Duplicate ids and malformed phases raise `ValueError`.

The output object has exactly `decisions,complete`. Each id-sorted decision has exactly `id,action,reason,attempts_used,next_backoff_ms`; action is `complete,retry,probe_or_block,exhausted`, or `blocked`, and reason is `no_attempt,committed,probe_committed,probe_absent,ambiguous_commit,retryable_abort,attempt_budget`, or `non_retryable`. Backoff is non-null only for terminal `retry`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

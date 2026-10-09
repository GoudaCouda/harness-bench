# Repair shell pipeline status and retry handling contract

Compute pipeline stage status after normalizing expected SIGPIPE 141 to zero only when marked expected_short_read and every downstream stage succeeded. Without pipefail use the last stage; with pipefail use the rightmost nonzero status. Zero completes. A configured retryable status retries only when replayable and no successful side-effect stage exists; otherwise side effects require probe_or_block. Other failures fail. Return sorted decisions with normalized statuses, action, and side-effect flag. Invalid codes and duplicate ids raise `ValueError`.

The output object has exactly `decisions`. Each id-sorted decision has exactly `id,status,stage_statuses,action,side_effect_committed`; action is `complete`, `retry`, `probe_or_block`, or `fail`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.

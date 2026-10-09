# Replay notes

## Decision

            The last line was not valid JSON, so it was dropped and torn_tail is true.
            The same op_id appears twice; the first put kept alpha=one and the later put
            was skipped. op-12 deleted beta. gamma was stored from op-13. No delta key was
            invented from the torn tail.

## Verification

Re-reading wal.jsonl as lines and json.loads on all but the last line
reproduced store.json and replay_report.json.

## Remaining risk

A future writer might emit pretty-printed multi-line JSON objects, which
this line-oriented replay would treat as torn. No remote store was
contacted and the mill cache was not published.

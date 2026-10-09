# Logical-slot recovery handoff

Retained WAL is measured from the primary position back to each restart LSN; consumer progress does not make old WAL safe to discard. Lost/invalidated slots, restart positions older than available WAL, and cap breaches need recovery. A healthy stopped consumer resumes from its last applied checkpoint, while a healthy running slot is kept.

Recovery precedence first requires configured and observed failover synchronization when policy demands it, then blocks an active slot, a missing maintenance window, or unavailable resnapshot. A safe rebuild stops the consumer, drops and creates the slot, resnapshots, then starts it, resuming from the new primary position. This order deliberately avoids advancing an LSN or pretending an old consumer checkpoint can bridge removed WAL.

Verification ran `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/plan_recovery.py`, and JSON parsing of plans and summary; all passed. The work is an offline plan only: no PostgreSQL connection or SQL ran, and no slot was dropped, created, advanced, no consumer restarted, and no production database changed.

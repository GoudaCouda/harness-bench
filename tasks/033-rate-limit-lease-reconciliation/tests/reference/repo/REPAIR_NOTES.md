# Repair notes

The reconciler first removes leases whose expiry is less than or equal to the
reconciliation clock, then computes capacity from the remaining active leases.
It separates idempotent replay from conflicting request-ID reuse: a matching
replay preserves both expiry and fencing token, while a conflict is rejected.
New work is ordered by FIFO timestamp with request ID as the deterministic tie
breaker. Grants are atomic, conserve capacity, and consume a monotonically
increasing fence only when accepted.

Verification used `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
and all public tests passed successfully. Integration risk: callers must provide
one authoritative millisecond clock; large clock skew can make different regions
disagree about the exact expiry boundary even when this local transition is
correct. No production deployment or live quota mutation was performed.

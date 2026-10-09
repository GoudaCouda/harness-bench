# Repair conditional cache revalidation

An edge-cache refactor is returning `304 Not Modified` for the wrong language
variant and mishandling weak ETags. Repair the local decision engine without
contacting an origin server.

Work only inside `repo/`. Read `repo/docs/cache_contract.md`, the implementation,
visible case batch, and public tests before editing.

Deliver:

1. Repair `repo/src/cache_revalidation.py`, preserving the public function
   `evaluate_cache_request(request, stored)`. It must honor `Vary` selection,
   conditional-header precedence, weak ETag comparison, HTTP-date boundaries,
   malformed-header bypass, and input immutability.
2. Create `repo/revalidation_report.json`: an array in the same order as
   `repo/revalidation_cases.json`, with each item containing its `case_id` and
   the exact decision returned by the repaired function.
3. Create `repo/REPAIR_NOTES.md` explaining the precedence and variant decisions,
   the exact verification command and observed result, and one integration risk.

Run from `repo/`:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not edit the contract, visible cases, or public tests. Do not claim a cache
purge, deployment, or origin request occurred.

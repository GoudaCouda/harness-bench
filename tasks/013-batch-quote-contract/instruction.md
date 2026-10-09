# Add the batch quote service contract

The pricing team needs a batch quote operation for an internal sales tool. The
existing single-quote API is already in production and must remain unchanged.
The repository is available at `$WORKSPACE/repo`.

Read `docs/feature_request.md`, the catalog and coupon fixtures, the current API
description, the package source, and the public tests. Implement the requested
pure service function in `src/quote_service/batch.py` and document the new
`POST /quotes/batch` operation in `api/openapi.json`.

The implementation must:

- preserve request order and return one outcome for every well-formed item;
- reject every occurrence of a duplicated `request_id` without rejecting
  unrelated items;
- calculate prices exclusively in integer cents using the published order of
  term and coupon discounts;
- distinguish unknown, expired, and wrong-plan coupons;
- treat booleans as invalid seat counts even though Python considers `bool` an
  `int` subclass;
- leave the existing `/quotes/single` contract and all evidence/tests intact;
  and
- remain a small, side-effect-free function with no imports, file access,
  network access, environment access, or dynamic execution.

You may modify only:

- `repo/src/quote_service/batch.py`
- `repo/api/openapi.json`

Also create `repo/IMPLEMENTATION_NOTES.md` with the design decision, the exact
local verification command you ran and its observed result, and one remaining
compatibility risk. Do not claim deployment or production publication.

Run the public suite from `repo` with:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The task is offline. Do not install packages or change the tests, fixtures,
package exports, or feature request.

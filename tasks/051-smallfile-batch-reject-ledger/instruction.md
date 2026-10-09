Build an offline batch normalization pipeline using only local files.

Input:
- $WORKSPACE/dropbox/
- $WORKSPACE/normalization_rules.yaml

Recursively scan all files. Convert supported valid records into one normalized JSON file per input under
$WORKSPACE/normalized/. Write deterministic ledgers.

Supported formats:
- customer CSV files with columns id,name,email,status
- order JSON files with order_id, customer_id, amount, currency
- note TXT files containing lines like Case: C-100, Owner: ana, Status: open

Normalized JSON contract:
- Every normalized file must use the output_name pattern in
  normalization_rules.yaml and contain record_id and record_type.
- Customer records must contain exactly record_id, record_type = "customer",
  name, email, and status.
- Order records must contain exactly record_id (copied from order_id),
  record_type = "order", customer_id, amount as a JSON number, currency, and
  status = "active".
- Note records must contain exactly record_id (copied from Case),
  record_type = "note", owner, and status.
- A normalized record may additionally contain source_path; no other extra
  keys are allowed.

Create:
- $WORKSPACE/normalized/
- $WORKSPACE/index.csv
- $WORKSPACE/reject_ledger.csv
- $WORKSPACE/batch_summary.json

index.csv header: source_path,target_path,record_type,record_id,status
reject_ledger.csv header: source_path,error_type,details

For `index.csv.status`, either preserve the normalized record's domain status
(`active`, `inactive`, `pending`, `open`, or `closed`) or use the processing
outcome `success` for every accepted row. Do not mix in failure statuses;
rejected inputs belong only in `reject_ledger.csv`.

Rules:
- Use workspace-relative source paths such as
  dropbox/customers/customers_01.csv.
- Sort index rows and reject rows by source_path.
- If one input file contains multiple valid records, create one normalized JSON file per valid record.
- Process files in ascending workspace-relative path order and records in
  source order.
- Validate required fields, status, and amount before checking for a duplicate
  ID. A rejected record never reserves its ID. Treat IDs from accepted records
  as globally unique; a later otherwise-valid duplicate must be rejected.
- Do not modify or delete input files.
- Unknown extensions, malformed files, missing required fields, invalid status, invalid amount, and duplicate record ids must be recorded in reject_ledger.csv.

Use only these error_type values:
- unsupported_extension
- malformed_file
- missing_required_field
- invalid_status
- invalid_amount
- duplicate_record_id

batch_summary.json must be an object with exactly:
- success_count: number of normalized records
- reject_count: number of reject_ledger.csv rows
- by_type: an object with customer, order, and note counts

Before finalizing, re-run or independently replay the local transformation and
confirm it is idempotent: the normalized file set, ledgers, ordering, and totals
must remain identical, with no duplicate output from the second pass.

# Recover and adjudicate an interrupted OOXML revision package

You are the publication-systems editor taking over an internal service-policy
bulletin. The previous worker durably recorded one contact decision but
crashed before the Word document checkpoint. A later signed legal correction
and several dependent, lower-authority, stale, and publication revisions are
still unresolved in the actual tracked-change package.

Work only in `$WORKSPACE`.

1. Read `authority_policy.md`, `revision_manifest.json`,
   `revision_dependencies.csv`, and `signature_registry.json`.
2. Inspect the real WordprocessingML package and interrupted journal:

   ```bash
   python3 bulletinctl.py inspect
   ```

   You may also inspect `bulletin_working.docx` with Python's `zipfile` module.
3. Create `adjudication_plan.json` with:

   - `workflow_id`, `source_document`, `adjudication_order`,
     `approval_boundary`, and `actions`;
   - exactly one action per change, containing `change_id`,
     `selected_event_id`, `disposition`, and `evidence`;
   - disposition `accept`, `reject`, or `invalidate_dependency`;
   - workspace-relative evidence locators of the form `file#record`.

   Select the highest-sequence current event for each change. Apply authority,
   verified-credential, scope, and dependency rules in that order. A child of
   any non-accepted prerequisite is `invalidate_dependency`; do not adjudicate
   its proposal independently. Use the policy's deterministic topological
   order. Reconcile the already durable contact decision instead of appending
   it again.
4. Preview without changing state:

   ```bash
   python3 bulletinctl.py preview --plan adjudication_plan.json
   ```

   Repair the plan until the preview passes. The preview validates the plan
   but does not choose or write actions for you.
5. Apply the plan and inspect the resulting DOCX and database:

   ```bash
   python3 bulletinctl.py apply --plan adjudication_plan.json
   python3 bulletinctl.py inspect
   ```

   `apply` resolves the tracked revisions in `approved_bulletin.docx`, appends
   the missing durable journal entries, preserves the existing journal prefix,
   and records one recovery transaction. Do not hand-edit OOXML or update
   SQLite directly.
6. Create `editorial_handoff.md`, then verify twice:

   ```bash
   python3 bulletinctl.py verify --plan adjudication_plan.json
   python3 bulletinctl.py verify --plan adjudication_plan.json
   ```

   The second verification and a second identical `apply` must be idempotent:
   no duplicate transaction, journal row, document change, or receipt change.

The final DOCX must be a valid Office Open XML package with every tracked
insertion/deletion resolved, all unaffected text and non-document package parts
preserved, and no public-export language admitted. The final state is only
`staged_for_internal_approval`. Do not publish, export, send, notify, approve,
or claim any external action occurred.

Treat `bulletin_working.docx`, `authority_policy.md`,
`revision_manifest.json`, `revision_dependencies.csv`,
`signature_registry.json`, and `bulletinctl.py` as protected read-only inputs.
Only the paths declared above may change.

The handoff must identify the selected late signed correction, the recovered
durable contact decision, accepted/rejected/dependency-invalidated changes,
the preserved package features, the transaction and idempotent replay result,
verification evidence, remaining internal approval boundary, and the fact that
no publication or external action occurred. Structured document, database,
plan, and receipt state remain canonical.

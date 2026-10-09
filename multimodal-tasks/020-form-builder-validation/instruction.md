# Build a live validation form builder

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json`.

You are building an interactive form builder, not a generic field list. The first screen should show a field palette, form preview, validation errors, required controls, field ordering, and a generated schema preview.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains protected form field definitions with `id`, `label`, `type`, `group`, `required`, and `pattern`.

## Required behavior

- Import or otherwise read all protected field records; do not retype a smaller dataset.
- Every field palette item, form preview row, and schema preview must show the protected field `id` as visible text.
- Provide deterministic controls for `Add selected field`, `Move field up`, `Required field`, and `Clear form`. `Required field` may be a labelled checkbox, switch, or button.
- Editing sample values must update visible validation errors. Email, phone, number, nonempty, and checked validation should be handled locally from the protected `pattern` data.
- Each editable sample input in the form preview must have an accessible label in the form `<FIELD_ID> sample value`, for example `FORM-EMAIL sample value`.
- Adding/reordering fields must update `Field count`, `Required fields`, `Validation errors`, `Selected field`, and `Schema preview`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you submitted, saved, sent, or changed any real external system.

## Browser verification target

The evaluator may select fields by visible protected ids or `data-field-id`, add fields, type invalid sample values, toggle required state, reorder the preview, inspect generated schema text, and repeat mobile layout checks. Exact ids and values are evaluator-owned.

# Public release policy

Collaborators who author, review, or run the private benchmark need the complete
repository: active and archived packages, hidden tests/reference data, catalog,
runtime code, validators, and maintained docs. The evaluated agent does not.

A public result bundle contains only allowlisted aggregate/task results,
configuration identities, isolation evidence, and safe diagnostics produced by
`tools/export_public_summary.py` and `tools/build_public_delivery.py`. It must
not contain prompts when restricted, initial or terminal workspaces, tests,
reference outputs, ground truth, evaluator code, raw model requests, secrets,
host paths, Docker archives, or another trial's state.

Do not synchronize `artifacts/`, caches, `.venv`, Docker data, model weights, or
historical run roots through Git. Share a run separately only with reviewers
authorized to see its task inputs and trajectories.

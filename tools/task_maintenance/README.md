# Task maintenance tools

These are reusable gates for the current Standard274 active release.

| Tool | Purpose |
|---|---|
| `validate_archive_layout.py` | release-declared active/archive partition and unique numeric prefixes |
| `validate_task_suite.py` | active package schema, paths, environment, and metadata |
| `validate_design_outlines.py` | task measurement and scoring records |
| `validate_oracle_quality.py` | empty/untouched/malformed/reference behavior |
| `validate_oracle_discrimination.py` | neighboring errors and mutation gates |
| `validate_public_leakage.py` | agent-visible answer leakage |
| `deadline_policy.py` | task-only timeout policy |
| `validate_docker_grader.py` | production Docker reference boundary |
| `build_catalog.py` | deterministic active catalog |
| `verify_task_set_lock.py` | frozen task-set/package identity |
| `validate_multimodal_references.py` | browser-graded multimodal reference/untouched behavior |
| `audit_openclaw_trajectories.py` | post-run trace diagnostics |

Typical non-Docker release checks:

```bash
python tools/task_maintenance/validate_archive_layout.py
python tools/task_maintenance/validate_task_suite.py --expected-count 274 --task-set standard274
python tools/task_maintenance/validate_design_outlines.py
python tools/task_maintenance/validate_oracle_quality.py --require-reference
python tools/task_maintenance/validate_oracle_discrimination.py
python tools/task_maintenance/validate_public_leakage.py
python tools/task_maintenance/deadline_policy.py --check
python tools/task_maintenance/build_catalog.py --check
python tools/task_maintenance/verify_task_set_lock.py   --task-set standard274 --lock catalog/standard274.release-v1.lock.json
python tools/isolation/validate_isolation_config.py
pytest -q
ruff check src tools docker tests
```

Run all current-release references through the production Docker grader before a
formal model evaluation. Add `--build-image` when trusted grader source changed
and the local image label is stale.

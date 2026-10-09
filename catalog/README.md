# Current task catalog

The benchmark contains **274 general tasks + 26 multimodal tasks = 300 tasks**.

- `CURRENT.json`: current counts, taxonomy entry and general-suite content lock.
- `task_taxonomy_v3.json`: all 300 task paths, modalities, categories and classification reasons.
- `release.yaml` and `standard274.yaml`: runner selection for the 274 general tasks.
- `../suites/multimodal26/catalog/`: runner selection and content lock (`multimodal26.lock.json`) for the 26 multimodal tasks.
- `suite.yaml` and `task_catalog.csv`: generated runner metadata; their source `domain` fields do not replace the current task taxonomy.

Use the [task taxonomy](../docs/TASK_TAXONOMY_V3.md) for classification. Remaining compatibility manifests and content locks are implementation/audit files, not separate current benchmark versions. Source provenance is not a default evaluation grouping.

The current general-suite lock is `standard274.release-v1.lock.json`. It differs from `standard274.taxonomy-v3.lock.json` only for tasks 255-274: deployment-specific identifiers (host aliases, private mirrors, private image names and repository links) were replaced in design notes and archived legacy metadata; authoring-only package records (original case specifications, package inventories, provenance records and their draft builders) that no grading path reads were removed; and the trusted hooks of tasks 262-265 obtain their candidate sandbox image when it is not present locally, either by pulling the official image by digest or by building it from digest-pinned official base images (`environment/candidate_image.json`). Instructions, workspaces, outcome tests and references are unchanged. Earlier lock files remain unchanged for tracing their original package identities. To verify a clean checkout:

```bash
python tools/task_maintenance/verify_task_set_lock.py --task-set standard274 --lock catalog/standard274.release-v1.lock.json
```

# Harness-Bench task taxonomy

**English** | [简体中文](TASK_TAXONOMY_V3.zh-CN.md)

## Tasks and categories

Harness-Bench contains **300 tasks: 274 general tasks and 26 multimodal tasks**.
They form a single task set and are not split by release batch, contributor or
source. Results are reported separately for general and multimodal tasks so that
each model is evaluated on the modalities it supports.

| Category | Tasks | Subcategories (tasks) |
|---|---:|---|
| Software Engineering | 81 | Implementation and Repair (67); Repository Maintenance (14) |
| Business Operations | 71 | Rule-Based Review (34); Transaction Processing (26); Coordination (11) |
| Systems Engineering | 65 | Infrastructure Implementation (26); Operations and Deployment (22); Incident Recovery (17) |
| Research and Analysis | 40 | Data Preparation (20); Evidence-Based Research (13); Quantitative Analysis (7) |
| Web Development | 27 | Interactive Applications (12); Visual Tools (11); Layout and Accessibility (4) |
| Content Production | 16 | Documents and Presentations (9); Document Processing (5); Media Processing (2) |

The taxonomy has **6 categories and 17 subcategories**. The per-task mapping is
[`catalog/task_taxonomy_v3.json`](../catalog/task_taxonomy_v3.json); inside each
package the fields are `task_category` and `task_subcategory`. The original
`domain` field and the source fields are not the current classification. The 27
Web Development tasks comprise the 26 multimodal tasks and one general task.

The rationale for each assignment is stored in the `classification_rationale_v3`
field of the mapping. Tasks are classified by their work object and deliverable;
whether a task is implemented in code or through a user interface is recorded
separately in `execution_form`.

## Content identity

The category fields annotate existing tasks without changing instructions,
environments, evaluators or task membership. Because `task.yaml` is included in
package hashes, the taxonomy annotation was frozen as
[`catalog/standard274.taxonomy-v3.lock.json`](../catalog/standard274.taxonomy-v3.lock.json);
this is a metadata update to the same 274 general tasks. The current content
lock is [`catalog/standard274.release-v1.lock.json`](../catalog/standard274.release-v1.lock.json)
(see the [catalog README](../catalog/README.md)). Previous lock files are
preserved unchanged.

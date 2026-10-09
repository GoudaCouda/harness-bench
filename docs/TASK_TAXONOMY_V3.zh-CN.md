# Harness-Bench 题目分类

[English](TASK_TAXONOMY_V3.md) | **简体中文**

## 题目与分类

Harness-Bench 共 **300 题 = 274 道通用任务 + 26 道多模态任务**。这是统一的任务集，不按发布批次、贡献者或来源拆分。评测按通用和多模态分别报告，以适配模型的模态支持。

| 一级分类 | 数量 | 二级分类及数量 |
|---|---:|---|
| Software Engineering | 81 | Implementation and Repair 67；Repository Maintenance 14 |
| Business Operations | 71 | Rule-Based Review 34；Transaction Processing 26；Coordination 11 |
| Systems Engineering | 65 | Infrastructure Implementation 26；Operations and Deployment 22；Incident Recovery 17 |
| Research and Analysis | 40 | Data Preparation 20；Evidence-Based Research 13；Quantitative Analysis 7 |
| Web Development | 27 | Interactive Applications 12；Visual Tools 11；Layout and Accessibility 4 |
| Content Production | 16 | Documents and Presentations 9；Document Processing 5；Media Processing 2 |

当前采用 **6 个一级类、17 个二级类**。逐题映射见 [`catalog/task_taxonomy_v3.json`](../catalog/task_taxonomy_v3.json)；题目包内的字段为 `task_category` 和 `task_subcategory`。原始的 `domain` 字段和来源字段不是当前分类。Web Development 的 27 题包含 26 道多模态题和 1 道通用题。

逐题分类依据保存在映射文件的 `classification_rationale_v3` 字段中。分类按工作对象和交付要求确定；任务是通过代码实现还是通过界面实现，另由 `execution_form` 字段记录。

## 内容标识

分类字段只为已有任务添加标注，不改变题面、环境、评分器或任务成员。由于 `task.yaml` 计入题目包哈希，分类标注冻结为 [`catalog/standard274.taxonomy-v3.lock.json`](../catalog/standard274.taxonomy-v3.lock.json)，这是对同一批 274 道通用任务的元数据更新。当前内容锁为 [`catalog/standard274.release-v1.lock.json`](../catalog/standard274.release-v1.lock.json)（见 [catalog README](../catalog/README.md)）。此前的锁文件保持不变。

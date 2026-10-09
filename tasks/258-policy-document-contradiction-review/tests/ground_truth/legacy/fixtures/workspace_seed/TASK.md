# 制度一致性审阅任务

请审阅 `input/` 中的全部五份制度文件，并将结果写入 `output/review_report.json`。

## 1. 审阅范围

1. 找出文件之间可由原文直接证明的事实矛盾。
2. 找出制度正文与版本说明之间的版本不一致。
3. 找出引用目录或正文中的错误文件、版本或章节引用。
4. 不要把意思相同、仅措辞不同的要求误报为冲突。

## 2. 输出要求

1. 输出必须是 UTF-8 JSON，顶层字段只能包含 `schema_version`、`review_scope`、`summary` 和 `findings`。
2. `schema_version` 固定为 `multi_policy_review_report_v1`。
3. `review_scope.files_reviewed` 列出审阅的五个相对文件路径，`review_scope.scope_statement` 简述范围。
4. `summary` 包含整数 `total_findings`、`high`、`medium`、`low` 和一句中文 `conclusion`。
5. 每个 finding 包含：
   - `finding_id`：报告内唯一编号；
   - `issue_type`：`fact_conflict`、`version_mismatch` 或 `reference_error`；
   - `severity`：`high`、`medium` 或 `low`；
   - `title`：简明中文标题；
   - `evidence`：至少两条证据，每条均含 `file`、`section`、`quote`；`quote` 必须逐字来自对应章节；
   - `judgment`：说明证据为何构成问题；
   - `recommendation`：包含 `action`、`target_file`、`target_section` 和建议采用的 `replacement_text`。
6. 只报告有充分原文证据的问题，不得添加基于猜测的风险项。

## 3. 操作约束

1. 不得修改、删除或重命名 `TASK.md` 和 `input/` 中的任何文件。
2. 除 `output/review_report.json` 外，不得创建其他文件。
3. 不得访问网络、运行外部程序或尝试寻找隐藏答案。


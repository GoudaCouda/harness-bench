# 2026 年项目立项材料收集规则

1. 人员范围以 `person_roster.csv` 为准，每人必须提交“项目履历”和“合规声明”两类 PDF 材料。
2. 只处理 `project-materials` 频道内、截止时点 `2026-07-20 10:00:00+08:00` 之前发送的附件。
3. 附件元数据中 `material_type` 为 `project_resume` 或 `compliance_declaration` 时才是候选材料。
4. 同一人同一材料有多个版本时，使用发送时间最晚的版本；`replaces_attachment_id` 只用于帮助识别修订关系。
5. 附件必须通过本地协作工具下载，原字节归档到 `archive/<person_id>/<material_type>/<original_filename>`；不得改名、改写或覆盖。
6. 登记表固定为 `outputs/material_register.csv`，人员顺序与名单一致，不得增减行或列。
7. 只向缺件人员各发送一条提醒；已交齐人员不得提醒。缺两项时按“项目履历、合规声明”顺序填写。
8. 截止时间为 `2026-07-25 17:00`；提醒文案必须严格使用 `reminder_template.txt`。
9. 完成后删除自建的中间文件，不得访问真实协作平台或发生其他外部操作。

## 登记表列

`person_id,name,project_resume_status,project_resume_file,project_resume_source_attachment_id,compliance_declaration_status,compliance_declaration_file,compliance_declaration_source_attachment_id,overall_status,reminder_status`

状态只能使用：单项 `submitted` / `missing`，总体 `complete` / `incomplete`，提醒 `not_required` / `sent`。缺件对应的文件路径和附件 ID 留空。

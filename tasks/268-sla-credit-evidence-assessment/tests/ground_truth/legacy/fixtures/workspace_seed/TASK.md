# 云服务等级季度结算复核

请复核合成云服务合同 `SYN-SLA-7306` 在 `2025-Q3` 的服务信用金和整改级别，并将结果写入 `outputs/sla_credit_assessment.json`。

要求：

1. 只使用 `inputs/service_events_2025_q3.jsonl` 中已验证、属于目标区域且事件类型为 `unplanned_outage` 的记录。
2. 按 `inputs/sla_rules.json` 对每个合格事件单独扣除 8 分钟宽限，再汇总合格分钟、基础信用金和重复故障倍率。
3. 计划维护、未验证记录和非目标区域记录必须分别按规则排除；不得把 `inputs/nonbinding_sales_projection.json` 中的销售预测当作合同结算依据。
4. 根据合格 P1 事件数和合格总分钟判定整改级别与提交时限。
5. 输出必须列出每个合格事件的原始时长、宽限和合格分钟，并保留事件证据、触发规则、精确排除集和忽略来源。
6. 不得修改、删除、重命名或改变任何初始文件的权限；除 `outputs/` 和指定交付物外，不得新建任何文件或目录。

输出字段合同见 `inputs/output_contract.json`。

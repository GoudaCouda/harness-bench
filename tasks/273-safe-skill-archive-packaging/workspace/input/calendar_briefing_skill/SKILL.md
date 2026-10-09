# 日程简报技能

该技能读取一个文本模板，规范化非空行，并输出可供下游系统消费的 JSON 简报。

## 输入

1. UTF-8 编码的纯文本模板。
2. 每行代表一个待办事项，空行忽略。

## 输出

1. `schema_version` 固定为 `calendar_briefing_result_v1`。
2. `items` 按输入顺序保存去除首尾空白后的非空事项。
3. `item_count` 等于 `items` 的长度。

# {{title}}

> {{period_line}}

<!--
可见占位符合同：
1. `title` 是简报标题；`period_line` 必须说明本期、对比期和时区。
2. `core_metrics` 与 `week_over_week` 分别承载当前核心指标和环比变化。
3. `channel_table` 与 `daily_table` 必须是含完整字段和全部数据行的合法 Markdown 表格：表头、同列数的唯一分隔行、数据行依次出现；元金额必须带 ¥、CNY、人民币或元。
4. `risks` 必须列出每个已触发风险的身份、严重度、实际值和阈值；`actions` 必须覆盖相应建议动作。
5. `data_quality` 必须列出总行数、本期行数、对比期行数、重复键和无效行计数。
6. 所有占位符必须被替换且不得残留；标题和七个二级章节按本模板顺序出现，禁止删除线和额外可见正文。指标口径文件中的 `canonical_line_formats` 是标题、周期、风险、行动和数据质量的机器可验收句式。无关空白和列表符号不要求与参考答案一致，但同一输入两次运行必须产生字节一致的输出。
-->

## 一、核心指标

{{core_metrics}}

## 二、环比变化

{{week_over_week}}

## 三、渠道表现

{{channel_table}}

## 四、每日趋势

{{daily_table}}

## 五、风险与证据

{{risks}}

## 六、下周动作

{{actions}}

## 七、数据质量

{{data_quality}}

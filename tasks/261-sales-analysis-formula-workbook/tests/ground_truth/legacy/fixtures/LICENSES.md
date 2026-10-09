# 合成资产许可证与来源

## 1. 覆盖范围

1. `workspace_seed/input/sales_records.csv` 为本 case 人工合成的虚构销售记录，不包含真实个人、客户、公司、订单或财务数据。
2. `workspace_seed/input/metric_rules.md` 与 `workspace_seed/task.md` 为本 case 按脱敏任务意图重新编写的执行规则，不复制原始用户文字或原始助手输出。
3. 上述合成资产由项目授权用于内部模型训练、评测和环境复现，不要求署名；许可证标识使用 `CC0-1.0` 表示可无条件复用的合成内容。
4. `prov_synthetic_assets` 只记录上述三项合成资产的来源与转换事实，与三项资产适用相同的 CC0 范围。

## 2. 来源边界

1. OpenClaw 只提供“制作销售分析工作簿”的受限、脱敏意图证据；任何原始内容、身份信息、隐藏推理、凭据和原始附件均未进入本 case。
2. 记录中的人物、商品、价格、日期、区域和订单号均为人工构造，与现实主体如有相似纯属巧合。

## 3. 项目内部代码与参考产物

1. `environment/`、`verifier/`、`oracle/`、`tests/` 和 `oracle/reference/sales_analysis.xlsx` 是本项目为该 case 新生成的内部代码、测试与参考产物，不属于第 1 节的 CC0 合成输入资产。
2. 上述项目生成内容使用 `LicenseRef-Project-Internal`：已获准用于公司内部商业模型训练、评测和环境复现，但本记录不授予对外再分发权，也不把受限任务意图声明为 CC0。
3. `prov_instruction_intent`、`prov_environment`、`prov_verifier`、`prov_reference_output` 和 `prov_rubric` 均按该内部许可管理；对应条款以本节为准。

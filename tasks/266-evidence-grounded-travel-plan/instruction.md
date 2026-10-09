请仅依据工作区 input 目录中的固定旅行快照、用户偏好和引用索引，为两位旅客比较澄江市往返海岚市的交通、住宿与活动组合。严格满足预算、日期、时间、评分、距离、早餐、退订和行李约束，按照偏好文件中的确定性规则选出唯一推荐。请在 output 目录交付 recommendation.json、comparison.csv 和中文 report.md；费用必须逐项可复算，推荐方案及关键结论必须引用能够精确回连的引用编号。不得访问实时网站、修改输入或写入额外文件。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

python3 hb_tools/travel_tool.py --workspace . --help；只提供离线目录查询和按你选择的条目生成报告，不提供最优答案。

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `output/recommendation.json`
- `output/comparison.csv`
- `output/report.md`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

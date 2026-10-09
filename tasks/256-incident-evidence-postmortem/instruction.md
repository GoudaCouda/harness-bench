请分析工作区 input 目录中的结算服务日志、告警、变更记录、影响统计和复盘模板，形成可编辑的 output/incident_postmortem.docx。文档需准确说明事故摘要、量化影响、带证据引用的时间线、根因证据链、恢复过程、干扰告警排除结论，以及带负责人、期限和验收标准的改进行动项。不得修改输入、生成额外交付物，或把仅在时间上接近但无因果证据的告警写成根因。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

python3 hb_tools/public/document_writer.py --workspace . --plan <JSON计划> --output output/incident_postmortem.docx

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `output/incident_postmortem.docx`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

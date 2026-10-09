根据完全合成的医院抬头、四台监控系统设备台账和巡检规范，生成一个可编辑、可打印、可填写的 Word 巡检记录表。每台设备独占一页，准确映射设备字段和巡检项目，并保留状态、问题处理、签字及日期填写位。只交付指定 DOCX，不得修改输入或加入真实敏感信息。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

python3 hb_tools/docx_writer.py --spec <JSON规格> --output output/monitoring_equipment_inspection_form.docx

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `output/monitoring_equipment_inspection_form.docx`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

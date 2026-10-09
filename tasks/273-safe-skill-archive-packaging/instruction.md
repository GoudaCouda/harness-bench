检查日程简报技能目录，依据模板补齐 manifest 的文件大小和 SHA-256，并只导出 output/calendar_briefing_skill.zip。压缩包必须只有指定顶层目录和四个必需文件，不能包含 .private、模板或其他文件，也不能出现重复、绝对、穿越、反斜线路径、符号链接和特殊文件。保持输入与任务说明不变，交付前验证压缩包可安全解包且入口脚本可运行。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

python3 hb_tools/skillctl.py --help；inspect、validate-manifest、package 接收公开技能目录与自行补齐的清单。

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `output/calendar_briefing_skill.zip`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

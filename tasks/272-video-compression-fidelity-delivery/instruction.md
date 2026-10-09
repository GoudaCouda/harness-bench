将 input/source.mp4 压缩为 output/compressed.mp4，并满足目标规格中的 MP4 容器、H.264 640×360 24 帧、yuv420p、AAC 48 kHz 双声道、时长误差、文件体积、压缩比例和内容保真要求；保持输入与任务文件不变，只交付该输出文件，并在结束前自行检查可完整解码且画面与声音未被替换。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

ffprobe 和 ffmpeg 按 task/tool_contract.json 使用；正式 harness 和 grader 镜像都必须具备这两个可执行文件。

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `output/compressed.mp4`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

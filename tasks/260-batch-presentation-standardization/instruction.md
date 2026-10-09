将输入目录中的三份演示稿按统一模板批量规范为 16:9：统一 Noto Sans SC 字体、字号、颜色、页脚、背景和四类对象的位置与尺寸。输出到 outputs/standardized 下的同名文件；不得覆盖输入，不得丢页、增页或修改标题与正文文案，也不得创建额外文件。页脚属于格式元数据，按样式表替换。

## HarnessBench 执行与交付约定

当前目录即工作区。保留初始目录内的公开任务说明与输入，它们给出完整规则；按这些规则完成任务，不需要连接原项目服务或安装专属 agent。

公开工具和接口说明位于 hb_tools/README.md；可使用 harness 的 shell、文件读写和 Python 工具。hb_tools/ 是新增的受保护公共工具目录，不包含参考答案。

python3 tools/pptx_inspect.py --workspace . --input <相对路径>；tools/pptx_standardize.py 提供 --input、--output、--style-map。

最终只保留初始文件与以下新增交付物（包括必要的父目录）：

- `outputs/standardized/market_brief.pptx`
- `outputs/standardized/project_update.pptx`
- `outputs/standardized/service_review.pptx`

不得修改、删除初始文件和工具；不要访问外网或真实业务服务。中间脚本、规格 JSON 和缓存应放临时目录，结束前不能留在工作区。设置 PYTHONDONTWRITEBYTECODE=1，避免工具生成 __pycache__。

## 评分口径

业务结果占 40%，证据与跨产物一致性占 40%，完整交付占 20%。前两项为核心项；输入和工具完整性是零权重保护门。未提交答案不会因输入仍然完整而得分。

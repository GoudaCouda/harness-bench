请编写一个可重复运行的 Python 脚本，读取 input/weekly_operations.csv、input/metric_definitions.json 和 input/brief_template.md，生成 output/summary.json 与 output/weekly_brief.md。指标、环比、风险和行动项必须遵循给定口径；脚本必须能处理同格式的其他周期和渠道，两次运行产物字节完全一致。CSV 异常时必须在执行时限内主动非零退出：若 output/ 原本为空，不得留下任何文件；若其中已有一组完整正确产物，两份旧产物都必须逐字节保持不变。除两份输出外，不得修改输入、新建持久化缓存或向 workspace 外写入持久化文件；容器提供的 4096 字节 /dev/shm 仅允许 Python 运行时临时使用，其中内容不得成为交付依赖并随容器销毁。

## 原生运行约定

当前目录为 /workspace。源码与交付路径均相对于该目录。评分器在模型停止后冻结产物，并在独立无网容器或可信状态服务上验证。不得创建或修改 .hb_gold20_execution.json，该文件由可信运行器生成。临时脚本与缓存放 /runtime 或 /tmp。

## 评分口径

- 主数据简报交付与可重复执行：40%。
- 新数据泛化与非法输入原子拒绝：40%。
- 完整交付与运行验证：20%。
两个核心模块均通过且得分至少 0.8 时 task_success=true。受保护状态、工具、输入或可信执行证据被篡改时为零分；普通缺失和不完整仅扣相应业务分。

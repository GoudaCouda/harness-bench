# case_11 执行环境

## 1. 静态合同

1. `sandbox_contract.json` 锁定镜像摘要、命令、用户、双层挂载、环境变量、资源上限、日志上限和 Docker 只读差异。
2. `tool_contract.json` 分开描述 Agent 创作阶段与候选验收阶段的写权限，避免把“创建脚本”和“运行脚本”混为同一写策略。
3. `workspace_manifest.json` 与 `tests/hidden/variant_manifest.json` 分别锁定主 fixture 和全部隐藏变体；reset 不接受任意 fixture 路径。

## 2. Reset 与受保护状态

1. `reset.py` 先在同一 `attempts/` 根内构建 staging，再原子改名为新 workspace；已有 workspace 和 baseline 均拒绝覆盖。
2. 每个 reset 在候选不可见的 `evidence/reset_baselines/` 保存输入哈希、inode、权限、所有者、设备号和链接数。
3. 终态验收同时核对输入内容与对象身份；正式候选运行时整个 workspace 只读，仅 `output/` 独立可写。

## 3. 动态资源所有权

1. `validation/ownership_plan.json` 是远端 plan 的持久化快照；两者使用 `case11_execution_ownership_plan_v2` 并锁定当前 contract 哈希。
2. controller 在创建容器前，以文件锁和原子替换向 resource manifest 写入 `approved_not_created` 记录。
3. `docker create` 返回后，controller 立即将状态改为 `created`，并同步登记完整容器 ID、名称、attempt 和 invocation；失败创建也保留失败计划记录。
4. controller 不清理容器；清理必须由主控在结果持久化、现场核验和用户授权后按精确 ID 执行。

## 4. 候选隔离与静默终态

1. 候选容器看不到 case、oracle、verifier、隐藏测试、Docker socket、凭据或宿主其他路径。
2. 控制器以 detached 方式启动容器，不把未受信输出接入无界 pipe；Docker 日志轮转和持久化证据均有上限。
3. 运行中按 20 毫秒周期检查 64 MiB workspace 总量和 256 个对象上限；超限或超时只 kill 当前精确容器。
4. 所有路径均进入 `finally` 静默检查；正式通过要求容器非运行、PID 为 0、未重启且 Docker diff 符合合同。
5. 只读根文件系统外仅保留 4096 字节 `/dev/shm` 供 Python 运行时临时使用；它不能承载交付物或持久化缓存，内容随容器销毁且不进入判分状态。

## 5. 验收分层

1. `verifier/verify_outputs.py` 只解析终态，独立复算指标、规范 JSON 和 Markdown，并核对 exact tree 与受保护输入。
2. `verifier/evaluate_submission.py` 是 `case.json` 声明的自动验收入口；它复制候选脚本到 fresh workspace 后真实执行，不导入候选或参考实现。
3. 完整验收包含主数据两次、隐藏替代数据一次、四行最小合法数据一次及列缺失、行尾额外单元格、日期、数值、重复键、业务逻辑、零分母七类异常门，并额外在重复键异常下验证已有正确产物保护。
4. 七类全新异常门均要求候选在时限内主动非零退出、控制器合同完整通过且 `output/` 为空；已有产物门还要求两份旧产物逐字节不变。超时、缺少创建前登记、容器未启动或终态不静默均按失败处理。
5. 本目录定义的是候选脚本运行合同。未来教师创作阶段必须由 rollout 编排器只向模型暴露初始化 workspace 与获批工具；`oracle/`、`verifier/`、`tests/hidden/`、控制面和凭据都不得挂入教师可见环境。环境构建阶段不把这条声明误报为已完成的教师 rollout 验证。

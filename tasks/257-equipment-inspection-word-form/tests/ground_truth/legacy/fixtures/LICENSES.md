# case_03 来源与许可

## 1. 合成资产

1. `hospital_header.json`、`equipment_registry.json`、`inspection_standard.json`、`instruction.md` 和 `tool_contract.json` 均为本项目为此 case 新建的合成资产。
2. 合成资产可用于本项目的商业训练、内部评测和确定性环境重建，不要求外部署名。
3. 资产不得被描述为真实医院、患者、员工或实际设备记录。

## 2. 项目代码

1. `environment/docx_writer.py`、环境、oracle、verifier 和测试代码均为本项目新建实现。
2. 这些实现可在本项目内用于商业训练、内部评测和环境复现，不要求外部署名。

## 3. OpenClaw 意图证据

1. OpenClaw 来源只证明“根据设备清单和维护规范生成可打印、可填写巡检表”这一脱敏任务意图。
2. 环境不复制原始用户指令、助手输出、真实机构信息或任何生产数据。
3. 任务来源引用由工作区内部授权约束管理，不作为可独立对外分发的数据许可。

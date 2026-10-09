# 多模态任务集

[English](README.md) | **简体中文**

本目录包含一个独立的 26 题多模态前端任务集。它放在 `tasks/` 之外，
用于避免影响原有任务树和现有编号。

这批题属于 agent 任务流题，重点是多步骤前端实现、受保护本地数据
grounding、浏览器可验证交互，以及确定性评分边界。它们要求 agent
完成 workspace 检查、源码修改、交互状态处理和验证行为，而不是回答一个
静态问题。

## 范围

这批任务使用本地 Vite React TypeScript workspace。每道题要求 agent
基于受保护的本地数据和前端 starter，实现一个可在浏览器中使用的 UI，
并覆盖响应式布局、交互状态和浏览器可验证行为。26 道题刻意覆盖不同前端
工作流表面，包括 dashboard、生产看板、游戏式控制、incident timeline、
研究站点、预约规划、预算矩阵、媒体时间线、课程大纲、ticket routing、
数据表、policy diff、build repair board、可访问性审计、viewport 预览、
feature flag 矩阵、行程规划、仿真控制、portfolio rebuild 和 form builder。

这批题现在混合两类任务：

- baseline 数据驱动前端题，考察本地数据 grounding、筛选、搜索、派生摘要、
  选择状态、详情面板、响应式布局和可访问性约束；
- 更复杂的交互题，考察几何位置、多步骤状态、卡片移动、图片标注、路线构建、
  表单校验或浏览器可测的视觉状态。

本任务集内部使用独立编号：

- `001-creator-revenue-dashboard`
- `002-studio-task-board`
- `003-pet-care-game`
- `004-incident-command-console`
- `005-research-lab-site`
- `006-appointment-finder-ui`
- `007-budget-planning-workspace`
- `008-media-timeline-editor`
- `009-course-builder-app`
- `010-support-ticket-router`
- `011-local-data-explorer`
- `012-policy-diff-viewer`
- `013-kanban-build-repair`
- `014-accessibility-retrofit`
- `015-responsive-redesign`
- `016-feature-flag-admin`
- `017-travel-itinerary-planner`
- `018-scientific-simulation-controls`
- `019-portfolio-reference-rebuild`
- `020-form-builder-validation`
- `021-choropleth-map-selection`
- `022-waveform-audio-cue-editor`
- `023-spreadsheet-grid-formula`
- `024-image-pair-diff-annotation`
- `025-network-graph-explorer`
- `026-wysiwyg-print-preview`

原始的 `FE-201` 到 `FE-226` source ID 保留为 provenance 来源标识。

## 类型覆盖

26 道题不再是单一 UI 模板的重复。当前覆盖：

- 数据驱动 command surface：`001`、`002`、`004`、`005`、`006`、`007`、
  `010`、`011`、`012`、`016`、`018`、`019`；
- 游戏式 care controls：`003`；
- timeline seek / trim 编辑：`008`；
- 多步骤 wizard 校验：`009`；
- 可移动 Kanban repair：`013`；
- 截图/图片标注：`014`；
- responsive visual inspector：`015`；
- floorplan 路线规划：`017`；
- live form-builder validation：`020`；
- choropleth 分区地图：`021`；
- 波形 cue 编辑：`022`；
- 表格网格公式：`023`；
- 双图 diff 标注：`024`；
- 节点连线网络图：`025`；
- 分页打印预览：`026`。

这样既保留稳定 baseline 层，也加入了更难通过单一 filter/search/detail 模板
迁移解决的交互形态。

## 难度分布

难度按题目形态和浏览器可验证交互复杂度划分，不按某个模型当前得分划分。

| 难度 | 题目 | 数量 |
| --- | --- | ---: |
| Easy | `003`、`004`、`011`、`019` | 4 |
| Medium | `001`、`002`、`005`、`006`、`007`、`010`、`012`、`016`、`018` | 9 |
| Hard | `008`、`009`、`013`、`014`、`015`、`017`、`020`、`021`–`026` | 13 |

Easy 题保留为 baseline 覆盖。Medium 题仍以数据驱动为主，但加入更强的领域
workflow 要求和浏览器状态检查。Hard 题需要非平凡交互状态、几何测量、移动、
校验或视觉坐标行为。

## 任务包结构

每道题沿用 formal task package 结构：

- `task.yaml`：任务元数据、必需产物、mutation contract，以及隐藏评分入口。
- `instruction.md`：agent 可见的任务说明。
- `workspace/`：初始 agent workspace，包括受保护的本地记录数据。
- `environment/Dockerfile`：任务运行环境约束。
- `tests/cases.yaml`：隐藏的加权 case manifest。
- `tests/test_outcome.py`：确定性 outcome evaluator。
- `tests/ground_truth/frontend_contract.json`：隐藏的确定性 contract 和浏览器交互 probe。
- `design.md`：维护者设计说明和泄漏审查记录。

## 任务 Docker 环境

每道多模态题的 `environment/Dockerfile` 现在都声明了 browser-capable 的前端
环境。镜像保留 formal package 要求的 `agent:agent` 用户约束，并加入这批
Vite React workspace 需要的工具链：

- Node.js 和 npm；
- Git 和 ripgrep，用于 workspace 检查；
- Playwright `1.48.2`，并在 `/ms-playwright` 下安装 Chromium；
- `PATH` 上的 `chromium` symlink，便于直接做浏览器 smoke check；
- `NODE_PATH=/usr/local/lib/node_modules`，让临时 Node 脚本可以直接
  `require("playwright")`；
- 预热 npm cache，覆盖本任务集固定使用的 React、Vite、TypeScript 和
  `lucide-react` 版本。

可以从任意一道题的目录构建并做 smoke test，例如：

```bash
docker build -t harnessbench-multimodal-env multimodal-tasks/001-creator-revenue-dashboard/environment
docker run --rm harnessbench-multimodal-env node --version
docker run --rm harnessbench-multimodal-env npm --version
docker run --rm harnessbench-multimodal-env playwright --version
docker run --rm harnessbench-multimodal-env chromium --version
docker run --rm harnessbench-multimodal-env node -e 'require("playwright"); console.log("ok")'
```

这个 Dockerfile 记录了多模态题目的运行环境约定。benchmark runner 不会逐题构建
`environment/Dockerfile`；所有 harness 镜像和 grader 镜像都内置了同一套前端工具链
（Node.js、固定版本的 Vite/React 依赖、Playwright 与 Chromium）。全部 26 道题通过
[`suites/multimodal26`](../suites/multimodal26/README.md) 运行：

```bash
python tools/run_benchmark.py --suite-root suites/multimodal26 \
  --base-url "$HB_MODEL_URL" --model MODEL_ID --harness openclaw \
  --run-root artifacts/evaluations/multimodal26-shard-0
```

## 当前评分方式

当前 oracle 是确定性、离线、并包含浏览器检查的。它主要检查稳定可复现的
源码、文本、数据、依赖、安全边界，以及 Playwright 可验证的真实交互：

- 必需的 Vite React 文件存在，并且依赖版本固定；
- 受保护的 `web/src/data/localRecords.json` 保留预期的封闭记录集合；
- 源码文本中体现必需标签、领域概念、题目特有 workflow 概念、状态、
  事件处理和派生逻辑，并用 alias groups 接受合理同义表达；
- hidden contract 按 archetype 区分，记录数量、handler 阈值、interaction
  groups、calculation groups、logic groups 和 browser action probe 都不再共用
  一套固定的 filter/selected/scenario 骨架；
- Playwright probe 会 serve 提交的 `web/dist`，操作页面、检查可见状态，并在
  需要时检查响应式行为；
- CSS 和源码包含基础响应式、可访问性信号以及题目特有 presentation
  surface；
- 文件变更范围符合声明的 mutation contract；
- 方案不调用远程服务、不新增 package lock，也不声称完成真实外部动作。

当前 oracle 是本任务集的评分依据。它用于提供稳定、可复现的基础评分，防止
未完成、不安全或 keyword-stuffing 式提交通过，同时验证真实浏览器交互。

## 浏览器检查

隐藏 outcome tests 使用 Playwright serve 提交的 `web/dist`，并运行题目特定的
浏览器 probe。不同题目中，probe 可能会：

- 点击受保护记录 id 或稳定的 `data-*` hook；
- 移动 slider、选择 mode、切换开关、输入字段，或点击移动按钮；
- 测量 playhead、trim band、marker、route line 或 frame 几何；
- 在 mobile viewport 下重复布局检查。

这些浏览器 probe 属于 harness/oracle 层，不是 agent 需要额外生成的交付物。

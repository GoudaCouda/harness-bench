<p align="center">
  <img src="docs/images/harness-bench.png" alt="Harness-Bench" width="100%">
</p>

<h3 align="center">Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows</h3>

<p align="center">
  <a href="https://arxiv.org/pdf/2605.27922"><img src="https://img.shields.io/badge/arXiv-2605.27922-b31b1b.svg" alt="arXiv"></a>
  <a href="https://www.harness-bench.ai/"><img src="https://img.shields.io/badge/Website-harness--bench.ai-f5b700.svg" alt="Website"></a>
  <img src="https://img.shields.io/badge/tasks-274%20general%20%2B%2026%20multimodal-2f6fde.svg" alt="Tasks">
  <img src="https://img.shields.io/badge/harnesses-7-5b3fd1.svg" alt="Harnesses">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab.svg" alt="Python 3.10+">
</p>

<p align="center">
  <a href="https://arxiv.org/pdf/2605.27922"><b>论文</b></a> ·
  <a href="https://www.harness-bench.ai/"><b>项目网站</b></a> ·
  <a href="https://github.com/Qihoo360/harness-bench"><b>代码</b></a> ·
  <a href="docs/TASK_TAXONOMY_V3.zh-CN.md"><b>题目分类</b></a> ·
  <a href="#快速开始"><b>快速开始</b></a> ·
  <a href="#引用"><b>引用</b></a>
</p>

<p align="center"><a href="README.md">English</a> | <b>简体中文</b></p>

---

LLM agent 越来越多地以可执行系统的形式运行：调用工具、修改工作区、产出具体交付物。它们的表现不仅取决于基础模型，也取决于 **harness**，即负责管理上下文、工具、状态、约束、权限、追踪与恢复的系统层。**Harness-Bench** 在共享的任务环境、预算和评测协议下，比较不同模型搭配不同 harness 的效果，同时保留每个 harness 的原生执行行为，使 agent 能力可以在“模型 × harness”配置层面上报告。

## 概览

| | |
|---|---|
| **题目** | 300 道沙箱化、离线的工作流任务：274 道通用任务 + 26 道多模态任务（浏览器验证的前端任务） |
| **分类** | 6 个一级类、17 个二级类（[详情](docs/TASK_TAXONOMY_V3.zh-CN.md)） |
| **Harness** | OpenClaw、Claude Code、Codex、Hermes、Nanobot、Goose、OpenCode，各自运行在独立的 Docker 镜像中 |
| **评分** | 1,408 个计分工作模块加安全门槛，由隐藏的逐题 oracle 在离线评分容器中检查 |
| **留存证据** | 每次试验保留最终产物、模型请求记录、规范化轨迹和会话摘要 |

| 一级分类 | 题数 | 二级分类 |
|---|---:|---|
| Software Engineering | 81 | Implementation and Repair · Repository Maintenance |
| Business Operations | 71 | Rule-Based Review · Transaction Processing · Coordination |
| Systems Engineering | 65 | Infrastructure Implementation · Operations and Deployment · Incident Recovery |
| Research and Analysis | 40 | Data Preparation · Evidence-Based Research · Quantitative Analysis |
| Web Development | 27 | Interactive Applications · Visual Tools · Layout and Accessibility |
| Content Production | 16 | Documents and Presentations · Document Processing · Media Processing |

每道题包含题面、初始工作区、运行环境和隐藏评分器，详见 [Task authoring and acceptance](docs/TASK_AUTHORING_AND_ACCEPTANCE.md)。

## 评分方式

每个“模型 × harness”配置在隔离的工作区中获得完全相同的任务输入，并保留各自的提示方式、工具、上下文管理和恢复行为。Oracle 只根据最终产物和工作区状态评分。每道题按关键工作要求拆分为若干带权重的模块，模块内所有检查都通过才得到该模块的分数；安全门槛（受保护输入的完整性、必需产物的安全性、修改范围）与总分相乘。例如，028 号题（清洗一份杂乱的销售数据导出）的一次运行若通过 4 个模块中的 3 个且所有门槛都通过，得分为 0.34 + 0.25 + 0.20 = 0.79。

## 仓库结构

```text
tasks/                   274 道通用任务的题目包
multimodal-tasks/        26 道多模态任务的题目包
suites/multimodal26/     链接 26 道多模态任务的运行套件目录
catalog/                 运行清单、题目分类、内容锁和自动生成的元数据
src/harnessbench/        评分与任务集契约
tools/                   执行、追踪、评测与校验工具
docker/                  各 harness、OpenClaw 与评分器的镜像
docs/                    维护中的运行与评测文档
```

## 快速开始

```bash
uv sync --extra dev
```

### 运行评测

默认通过 `catalog/release.yaml` 选择 274 道通用任务：

```bash
python tools/run_benchmark.py   --base-url "$HB_MODEL_URL"   --model gemma-4-31b-it   --model-service-id "$HB_MODEL_SERVICE_ID"   --harness openclaw   --workers 4   --temperature 1   --run-root artifacts/evaluations/standard274-shard-0
```

26 道多模态任务通过 [`suites/multimodal26`](suites/multimodal26/README.md) 套件目录运行，各 harness 和评分器镜像已内置所需的前端与浏览器工具链：

```bash
python tools/run_benchmark.py   --suite-root suites/multimodal26   --base-url "$HB_MODEL_URL"   --model gemma-4-31b-it   --model-service-id "$HB_MODEL_SERVICE_ID"   --harness openclaw   --workers 4   --temperature 1   --run-root artifacts/evaluations/multimodal26-shard-0
```

用 `--harness` 选择其他 harness（`openclaw`、`claude-code`、`codex`、`hermes`、`nanobot`、`goose`、`opencode`）。大规模分片运行和模型服务固定，请参考 [CPU Docker + GPU vLLM runbook](docs/CPU_DOCKER_GPU_VLLM_RUNBOOK.md)。

### 校验题目

两套题目分别独立校验。通用任务：

```bash
python tools/task_maintenance/validate_archive_layout.py
python tools/task_maintenance/validate_task_suite.py   --expected-count 274 --task-set standard274
python tools/task_maintenance/verify_task_set_lock.py   --task-set standard274 --lock catalog/standard274.release-v1.lock.json
python tools/task_maintenance/validate_oracle_quality.py --require-reference

pytest -q
```

多模态任务（标准答案检查会通过 Playwright 驱动 Chromium）：

```bash
python tools/task_maintenance/verify_task_set_lock.py   --suite-root suites/multimodal26 --task-set multimodal26 --lock catalog/multimodal26.lock.json
pip install playwright==1.48.0 && python -m playwright install --with-deps chromium
python tools/task_maintenance/validate_multimodal_references.py --require-reference
```

## 追踪与评分约定

模型请求代理是 OpenClaw 和其他 harness 共用的计量边界。每次试验保留 `transactions.jsonl`、规范化的 `trajectory.jsonl` 和 `session-summary.json`，并由 `result.json` 引用这三个文件，详见 [Provider trace](docs/PROVIDER_TRACE.md)。

通用任务使用确定性的结果检查，只有在题目明确声明时才使用有边界的语义兜底评分。超时以及模型或协议导致的终止仍计入分母，详见 [Evaluation and scoring](docs/EVALUATION_AND_SCORING.md) 与 [General task suite](docs/STANDARD274.md)。

## 引用

如果使用了 Harness-Bench，请引用：

```bibtex
@article{yao2026harnessbench,
  title   = {Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows},
  author  = {Yao, Yilun and Tan, Xinyu and Liu, Chao-Hsuan and Li, Yaoming and Wang, Zhengyang and Yu, Wenhan and Tan, Zhewen and Tian, Yuxuan and Zhao, Guangxiang and Sun, Lin and Zhang, Xiangzheng and Yang, Tong},
  journal = {arXiv preprint arXiv:2605.27922},
  year    = {2026},
  url     = {https://arxiv.org/abs/2605.27922}
}
```

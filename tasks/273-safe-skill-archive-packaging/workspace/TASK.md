# 任务：校验并打包可安装技能包

请检查 `input/calendar_briefing_skill/`。保持整个 `input/` 与本任务文件不变，只在
`output/` 交付一个 `calendar_briefing_skill.zip`。

压缩包必须满足：

1. 顶层目录固定为 `calendar_briefing_skill/`。
2. 只包含 `SKILL.md`、`assets/template.txt`、`scripts/main.py` 和补齐后的 `manifest.json`。
3. `manifest.json` 使用 `manifest.template.json` 中的固定元数据；`files` 按
   `SKILL.md`、`assets/template.txt`、`scripts/main.py` 的顺序记录相对路径、
   SHA-256 和字节数。
4. 不得打包 `.private/`、`manifest.template.json` 或任何其他文件。
5. ZIP 中不得出现重复条目、绝对路径、路径穿越、反斜线、符号链接或特殊文件。
6. 交付前使用可用校验工具确认清单与压缩包可安全解包并可运行。

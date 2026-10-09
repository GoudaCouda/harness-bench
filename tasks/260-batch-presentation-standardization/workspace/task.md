# 任务：批量统一三份演示稿格式

请把 `inputs/decks/` 中三份演示稿按 `inputs/style_map.json` 和
`inputs/brand_template.pptx` 统一格式，并将结果分别保存到
`outputs/standardized/` 下的同名文件。

要求：

1. 三份输出都必须存在，文件名与输入一致；不要覆盖输入文件。
2. 不得丢页、增页、改动标题或正文文案，也不得改变标题与正文的顺序。
3. 按样式表统一 16:9 画布、背景、字体、字号、颜色、页脚和四类对象的位置与尺寸。
4. 页脚属于格式元数据，应替换为样式表给出的文本；其他文字必须保持不变。
5. 不要创建任务未要求的文件或目录，也不要修改 `inputs/`、`tools/` 或 `task.md`。
6. 可先使用 `tools/pptx_inspect.py` 检查输入，再使用
   `tools/pptx_standardize.py` 逐份生成输出；两个工具的 `--help` 提供参数说明。

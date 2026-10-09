# 公开工具

python3 tools/pptx_inspect.py --workspace . --input <相对路径>；tools/pptx_standardize.py 提供 --input、--output、--style-map。

工具源码可读。CLI 参数用 --help 查看；工具只处理你提供的规格，不包含隐藏参考答案。所有原题规则仍以初始任务文件、数据字典和模板为准。规格与中间脚本放临时目录，最终工作区只保留规定产物。

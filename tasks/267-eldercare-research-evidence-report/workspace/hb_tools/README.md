# 公开工具

python3 hb_tools/local_search.py --workspace . --query <查询>；write_document.py --workspace . 从 stdin 读取你撰写的报告。

工具源码可读。CLI 参数用 --help 查看；工具只处理你提供的规格，不包含隐藏参考答案。所有原题规则仍以初始任务文件、数据字典和模板为准。规格与中间脚本放临时目录，最终工作区只保留规定产物。

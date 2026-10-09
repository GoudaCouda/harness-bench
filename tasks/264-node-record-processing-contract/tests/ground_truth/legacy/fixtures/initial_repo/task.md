# 修复数据处理命令

## 1. 目标

1. 只修改 `src/process.js`，修复边界条件、错误处理、稳定排序与汇总性能。
2. 程序从标准输入读取一份 UTF-8 JSON，并只向标准输出或标准错误输出一份 JSON。
3. 禁止修改 `package.json`、`package-lock.json`、`test/public.test.js` 或新增任何文件、依赖和网络访问。

## 2. 输入合同

1. 顶层必须是只含 `records` 的对象，`records` 必须是数组。
2. 每条记录必须只含 `id`、`category`、`amount`，以及可选的 `priority`、`active`。
3. `id`、`category` 必须是去除首尾空白后仍非空的字符串；标准化输出使用去除首尾空白后的值。
4. `amount` 必须是 0 至 1,000,000,000 之间、最多两位小数的有限 JSON 数字。
5. `priority` 缺省为 0，必须是 -1000 至 1000 的整数；`active` 缺省为 `true`，必须是布尔值。
6. 标准化后的 `id` 不能重复。标准输入最多 2 MiB，记录数最多 50,000。

## 3. 成功输出

1. 成功时退出码为 0，标准错误为空，标准输出为单个 JSON 对象并以换行结尾。
2. `records` 中每条记录固定为 `id`、`category`、`amount`、`priority`、`active` 五个字段。
3. 排序键依次为 `category` 的 Unicode 码点升序、`amount` 降序、`priority` 降序；三个键相同则保持输入顺序。
4. `summary` 固定含 `inputCount`、`activeCount`、`totalAmount`、`byCategory`。
5. `byCategory` 按类别 Unicode 码点升序，元素固定含 `category`、`count`、`activeCount`、`totalAmount`。
6. 金额按整数分累计，再输出为最多两位小数的 JSON 数字；空数组必须返回空 `records`、全零汇总和空 `byCategory`。

## 4. 错误输出

1. 错误时退出码为 2，标准输出为空，标准错误为 `{"error":{"code":"...","message":"..."}}` 并以换行结尾。
2. 无法解析 JSON 使用 `INVALID_JSON`；顶层、大小或记录数不合法使用 `INVALID_INPUT`。
3. 单条记录字段、类型或范围不合法使用 `INVALID_RECORD`；重复标准化 `id` 使用 `DUPLICATE_ID`。
4. 错误信息必须确定、不得包含堆栈、绝对路径、环境变量或输入原文。

## 5. 资源与副作用

1. 不访问网络，不留下后台进程，不写入文件，不依赖或读取工作区外的任务数据、隐藏验收资产或凭据。
2. 处理固定的大输入时必须同时满足正确结果、内存/进程/磁盘边界和 8 秒宽松上限；不能靠跳过记录或近似汇总换取速度。

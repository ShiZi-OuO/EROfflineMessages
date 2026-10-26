# 数据包格式（开发版本 1）

数据文件位于 DLL 同目录，文件名为 `EROfflineMessages.pack.json`。路径相对 DLL 解析，不依赖启动目录。启动时读取一次；更换数据前正常退出游戏。

顶层字段：`schema_version` 必须为 1，`game` 必须为 `eldenring`，`source_type` 为 `constructed`、`official_client_sample`、`official_protocol_sample` 或 `official_sample`（后两者需要 0.1.4-dev3 及后续解析器；冻结 0.1.3 不支持）；`description` 说明来源；`messages` 为记录数组。两类来源应分别打包统计。默认真实快照包含 103 条正常官方客户端接收记录、两个地图编号；40 条构造赐福和压力包另外保存；性能压力包单独保存，这不是服务器全量。

每条记录包含：

| 字段 | 含义与限制 |
| --- | --- |
| `id` | 16 位十六进制字符串；构造数据使用 7e 前缀，官方样本包使用匿名 7d 前缀。本地键不得直接包含账号标识。 |
| `map` | 原版打包地图/区块编号，非地图名称字符串。已实机对照构造点 m60_42_36_00 / m30_02_00_00，以及真实快照 m31_03_00_00 / m60_42_37_00。 |
| `area` | 区域字段；当前试验取自 NetMan+0x24，完整语义仍待跨区域对照。 |
| `secondary_area` | 构造点默认 0；真实快照原样保留客户端值（如 31030），完整含义尚未确认。 |
| `position` | 三个有限浮点数，**区块内坐标**。不能直接写入角色 Havok 坐标。 |
| `yaw` | 有限浮点朝向；单位与方向待画面对照，不声明跨版本通用。 |
| `template1`, `word1` | 原版句式、词语编号，使用游戏自身本地化。 |
| `conjunction`, `template2`, `word2` | 第二句的连接词、句式、词语编号；单句全部为 0。 |
| `good`, `poor` | 两个评价快照字段，各 0–9999；已实测原版阅读界面显示二者之和，构造 A=10、B=13、室内=23，真实样本=7 与 8。未通过在线投票实验独立验证两计数各自的方向，不将字段名当成额外实测结论。 |

当前回放不支持手势、幻影和评价上传。运行时手势字段写入原版的“无手势”值 0xff。数据格式拒绝未知字段、重复键、非法坐标及不完整第二句，避免顺带保存身份、外观等不必要数据。

构造测试生成器用记录语义计算稳定键。修改位置或句式后必须生成新键，避免与原版跨进程缓存中保留的旧记录碰撞。该缓存的持久化由游戏自身管理；工具不会直接打开或编辑存档文件。

原版显示管理器还执行空间密度准入：进入缓存的记录不保证同时生成地面标记。当前紧密排列的 88 条压力记录只获得 3 个本地显示绑定。0.1.2区分缓存存在与绑定状态，尊重该限制，不为每个未显示记录持续补登记。单区块最多选取 96 条、原生缓存预算 120 条；超出区块选取数量的记录尚无动态轮换策略，不声明大数据包的全记录覆盖。

## Coordinates and provenance

Schema 1 stores native **block-local** coordinates. For the verified Church test, the native display conversion added the current block origin. NetMan's observed position was a Havok position; the fixture generator now subtracts the origin before serialization. Never reuse these runtime offsets on another executable.

`constructed` records are synthetic offline fixtures, not official player samples. The current default package contains 103 finite normal-client received samples, with one online UI correspondence and two individually recorded offline reading checks across binary versions; see provenance. It is not a complete server dataset. Neither the schema nor a finite client cache implies full server coverage. Keep source categories in separate packs and export no account IDs, credentials, names or appearance blobs.


0.1.3 遇到自设 120 条缓存预算时，每秒至多尝试一次，待原生清理后继续。当前默认两图全部选取后观察到总缓存 118（含原有记录），登记计数稳定 103；这不代表任何来源、任意大小数据包均能完整驻留，也不改变每图最多选取 96 条的限制。

诊断 JSON 的历史字段名 constructed_local 表示 sender 标识属于本地回放器，并非数据来源判定：真实样本匿名化回放也使用此本地标识。正式来源以数据包 source_type 和逐条 provenance 为准。采集工具排除所有这种本地回放节点，避免把回放过的真实样本当成新增服务器接收。


## 0.1.4 开发数据来源与空间选择

`official_client_sample` 是正常官方客户端接收来源；`official_protocol_sample` 是授权独立实验协议取得的官方服务响应；`official_sample` 表示两种已审核来源合并，必须另附逐队列来源及去重记录。都不是服务器全量。构造数据禁止混入官方合并包。字段白名单继续拒绝账号、原始玩家消息键、外观及认证材料。

2026-10-25 的 71 条协议队列经三地图响应匹配、一次新区域原坐标阅读见证审核；其余记录未逐条界面对照。与 327 条正常客户端队列合并后为 392 条、7 个地图编号。合并包数据解析通过，不等于整包游戏验收完成；实际运行的是其中 21 条风暴根脚测试包。

0.1.4 开发版按当前地图及附近位置选择最多 96 条，不再限制每图总记录数；采用每秒一次有界 KD 树查询、移动阈值 16 米、开发半径 250 米、最多访问 2048 节点。原生缓存容量字段实测为 128，首次满容量处允许一次登记触发原版压力清理；这一特定满容量分支仍未单独复测。前述 120 总预算及无轮换说明属于冻结 0.1.3，不代表新版策略或游戏硬容量。

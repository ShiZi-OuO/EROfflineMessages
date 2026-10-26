# 广域官方样本快照 / Broad-world official snapshot

当前审核数据为 `official-expansion-23439-v10.json`：23,439 条去重记录，476 个原始地图编号。包含本体与 DLC 区域，所有记录保留收到的地图、区块坐标、方向、原版句式／词语编号及评价快照。运行包没有构造留言、玩家身份或凭据。

正常客户端接收的两个队列在跨队列去重前共 327 条；另有七个分别记录的授权独立协议队列。队列来源、数量与 SHA-256 见 `data-provenance.json`，不能直接将队列条数相加视为独立记录数。回放 DLL 不包含采集或联网代码。评价不实时更新或同步。

本轮固定的 851 个区域／区块目标全部完成查询，两段共 432 次只读列表；后续父级覆盖补缺的 38 个目标也已完成，共 22 次列表。原始响应中的未验证地图记录另行隔离，未改写地图编号或坐标后纳入。已查询、收到有限样本和完成游戏内验收是三种不同状态。

本机 589 个启用谏言参数条目中，535 个收到有限样本。422 个赐福参数条目按其默认地图编号关联到 261 图，其中 259 图有同图样本；`m12_06_00_00` 和 `m61_55_39_00` 仍无同图样本。该静态关联不能证明每条参数都用于当前可玩流程，也不能证明每个赐福附近都有留言。相邻区块可能含有空间上接近的样本。

因此本包是跨本体和 DLC 的有限快照，**不声明完整服务器数据，也不声明所有可玩地图已逐一验证或毫无缺口**。逐图条数见包根目录 `COVERAGE.json`。实际语言、阅读、重载、跨图及缓存恢复状态仅以本构建的 `verification/validation.json` 为准。源码中的 103 条版本说明是历史里程碑，不能代替本包验收。

原版密度与交互准入决定同时出现哪些标记。缓存或登记中存在某条记录，不代表每条都会同时显示。源码中构造／压力夹具只用于开发，不加载到默认真实快照。

新增 v10 补查为 123 个目标单查与 3 个对照，共 126 次列表；123 个补查目标均为空，没有新增地图。54 条新内容与 10 条评价更新来自已有对照区域。0.1.5 已完成本构建有限快照的阅读与生命周期验收，逐项证据见 validation.json；不沿用旧 DLL 的结果，也不将抽查推广为逐图逐条通过。

## English

The reviewed pack contains 23,439 distinct records in 476 original map IDs across base-game and DLC areas. Original coordinates, directions, native phrase/word IDs and appraisal snapshots are preserved. Constructed fixtures, identities, tickets and unverified map records are excluded from the runtime pack.

The 851-target campaign completed all planned queries in 432 list requests; a separately authorized 38-target parent-area campaign completed in 22 requests. Queue provenance and file hashes are recorded separately. Received samples are finite and are not individually witnessed in the UI. The replay DLL contains no collection or networking code; appraisals are snapshots.

There are samples for 535 of the 589 locally enabled message-parameter rows. A static association of 422 grace-parameter entries yields 261 default map IDs, of which 259 have same-map samples. `m12_06_00_00` and `m61_55_39_00` have none. Parameter rows are not proof of current playable maps, and same-map presence is not proof of messages near every grace. Nearby samples can belong to adjacent tiles.

This is a broad-world finite snapshot, not a complete server dump or a claim of gap-free, individually verified playable-world coverage. Consult `COVERAGE.json` and the exact build's `verification/validation.json`. Older release results are historical. Native density and interaction admission determine which records are simultaneously visible. Constructed and stress fixtures in the source are development data, not the default snapshot.

The v10 campaign queried 123 gap targets plus three controls in 126 list requests. All gap targets were empty; the 54 new semantic records and ten appraisal updates came from existing maps. The 0.1.5 frozen build completed its finite-snapshot reading and lifecycle acceptance; exact evidence is in validation.json. Historical acceptance is not inherited and sampled checks are not extrapolated to every map or record.

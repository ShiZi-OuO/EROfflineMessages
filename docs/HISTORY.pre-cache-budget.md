# Elden Ring Offline Messages / 艾尔登法环离线谏言

**全地图扩充进行中。** 以下 0.1.3 是冻结的有限范围阶段包，不代表用户要求的全地图目标已经完成。当前已审核合并数据为 23385 条、476 个地图编号（独立协议队列分别统计，按语义去重；广域包已完成本体与 DLC 抽样阅读及恢复验收，未逐条逐图验证）；0.1.4 开发版接入附近位置选择，实机状态按版本单独记录。未知地图变体隔离保存，未改写后混入运行数据。采集进展与剩余缺口见 [全地图工作记录](docs/WORLD_COLLECTION.md)。

当前交付为 **0.1.4 广域固定快照版**，内含保持原样的实测 0.1.4-dev3 二进制。已从 RC1 ZIP 解压副本实测本体、室内与 DLC 抽样阅读，中文／英文同条谏言，标题继续、死亡复活、跨图与正常重启各三轮，以及原生缓存自然清空后的恢复。三轮人工操作按用户确认记录；并非每轮均有独立截图。详见 [本构建实机记录](evidence/install23385-gameplay.json)。最终分发仅更新说明和验证记录，DLL、数据、ME3 配置与启动脚本与已测安装副本逐字节相同。

全地图覆盖仍保留缺口，不把有限采样、参数行或地图资源总数当作服务器全量。运行数据不包含构造夹具。

冻结阶段安装包为 **0.1.3 真实客户端有限快照版**；已实机回放的扩充构建为 0.1.4-dev3，当前运行时源码已恢复并核对为该构建。0.1.4-dev4 世界变体实验实际未显示，单独保存，不作为可用功能。冻结版数据为正常官方客户端接收的 103 条记录：近林洞窟 41 条、附近开放世界区块 m60_42_37_00 为 62 条，包含 17 条双句留言。不是官方服务器全量，也不覆盖全地图。

首条真实样本“前有集团”、总评价 7 已完成原版在线阅读、正常退出、脱机提取和原位回放阅读，均有实际截图。其余记录具有同一接收来源，未逐条独立在线核对。0.1.3 整批已实际加载，用户确认洞窟与室外均可读，室外双句和评价 8 已截图；当前版本已由用户完成标题继续和死亡恢复各 3/3，并从 ZIP 解压目录实际启动、取得同一双句的英文阅读截图（评价 8）。详细状态见 [验证记录](evidence/validation.json)；编译和内部登记不单独证明可见、可读或跨图通过。

仅适配本机核对的 Windows x64 Steam App 1.17.2 / Regulation 1.17.3、EXE 2.7.2.0，SHA-256 `F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328`。依赖单独安装的 ME3 0.13.0，不通过可能陈旧的文件关联启动。

安装包解压到独立目录后运行 Launch.cmd。详见 [中文安装教程](docs/INSTALL.world.zh-CN.md)、[English instructions](docs/INSTALL.world.en.md)、[当前快照覆盖范围](docs/COVERAGE.world.md)、[构建](docs/BUILD.md)、[数据格式](docs/DATA_FORMAT.md) 与 [第三方许可](THIRD_PARTY.md)。

回放使用原版地面标记、提示、阅读界面和本地化，不写死中文。数据相对 DLL 定位，进程级防重复加载，精确版本/签名与脱机门禁，不直接编辑存档。1 Hz 有界维护、分帧登记，缓存存在与显示绑定分别处理；0.1.3 在 Mod 的缓存预算满时有界等待原生清理后继续，不删除游戏所有的节点。

冻结的 103 条样本通过“原版 Steam/EAC 正常联网收取 → 正常退出 → 空 ME3 脱机环境只读提取”获得。后续扩充实现了只读自动存档采集器，不访问联网进程内存。早期独立认证收到错误 12 后停止；经新增限定授权和精确版本字段修正，随后独立认证成功，三地图返回 71 条匿名样本，其中一条新区域记录已原位脱机阅读验证。来源单独标记，采集代码未链接到回放 DLL。410 项批次按约定在地图关联不足时停止，保留前 64 次的 1542 条有效候选；PlayArea 已核实跨地图原因。621 项剩余清单在服务器错误 20000 后停止并保留 8226 条有效记录；后续组查在未验证地图处停止并保留 2973 条记录。固定 851 目标补采已正常完成，两段共 432 次列表；另获授权的父级区域 38 目标补缺也已正常完成，共 22 次列表。当前无活动采集，仍不声明全地图已齐。采集方法见 [OFFICIAL_SAMPLING](docs/OFFICIAL_SAMPLING.md) 和上述全地图工作记录。

用户取消后续 FPS/P99 与一小时稳定性测试，不声明这些项目通过。旧版 0.1.1/0.1.2 的语言和生命周期测试按版本记录，不冒充 0.1.3 逐项复测。其他 Mod 兼容性未验证。40 条构造赐福与压力数据单独保留在 data/，不混入默认真实快照。

## English

Full-world expansion remains in progress. The frozen 0.1.3 archive below is a limited milestone. Reviewed merged data contains 23385 records in 476 map IDs, including separately labelled protocol cohorts. The broad-world pack has sampled base-game and DLC reading evidence, Chinese/English reading of the identical record, three user-confirmed rounds each of title/death/teleport recovery and normal restarts, plus witnessed natural cache expiry and restoration. It has not been individually read in every map. Runtime source corresponds to the witnessed 0.1.4-dev3 build; the dev4 world-variant experiment failed actual display and is excluded. The latest grouped session stopped on an unverified map association after preserving 2973 accepted records. The preserved ledger records nine independent authentication attempts and 933 list attempts; all collection scopes are spent. The fixed 851-target campaign completed normally in two sessions and 432 list requests. A separately authorized 38-target parent-area campaign also completed normally in 22 list requests. No collection remains active. Collection code is separate from the replay DLL.

Version 0.1.3 replays a finite snapshot of 103 records received through a normal official client in two map IDs. It preserves native positions, phrases and appraisal snapshots without player identities. One record has individual online/offline reading correspondence; other records share collection provenance and are not all individually witnessed. This is neither a full server dump nor full-world coverage.

Use the separate ME3 0.13.0 and the exact checked game image. Follow the linked English guide and version-specific validation. The complete 0.1.3 pack has actually loaded both map IDs, with sampled reading and an outdoor double-phrase screenshot. That binary passed user-reported title/death recovery (three rounds each) and actual English double-phrase reading from an extracted install ZIP. See the version-specific record for limits. FPS/P99 and one-hour testing were cancelled by the user. No direct save edits were performed.

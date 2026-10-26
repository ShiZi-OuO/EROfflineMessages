# 只读地图位置研究

目的：减少逐图人工传送，通过本机地图中的实际三维放置数据生成构造谏言候选点。地图资源不是在线谏言系统；最终显示仍使用已经实测的原版运行时接收、登记和阅读流程。

工具：`tools/research_map_graces.py`。已从本机 Data2 只读提取并解析五处地图，未改游戏文件。m30_02_00_00 的 `AEG099_060_9000` 高度与实际谏言差约 3 厘米，水平位置相距约 2.40 米。教堂赐福实际出现在较大层级 m60_10_09_02 中：向 m60_42_36_00 转换为 X-128、Z+384 后，距已实测测试点约 0.2794 米。具体坐标和来源摘要见 `evidence/map-anchor-comparison.json`。这证明一处区块转换与已有实测位置吻合，不代表所有转换都已验证。

此段为初始五图探测阶段记录，扩大快照结果见下文。不能因为模型名称匹配就把所有位置认定为可读、安全的放置点。m31_03_00_00 的赐福资产关联碰撞 h000100，后者的 PlayRegionID 为 3103001；m30_02_00_00 的赐福没有直接关联，不能简单推断两个候选区域中的哪一个。

边界：游戏目录、档案、EXE 及存档只读；输出仅限本工程；不运行 UXM 的修改功能，不改原版地图，不向官方服务器发送请求。原始解包资产不进入安装包。工具在自己的 Python 进程中调用本机游戏附带的解压 DLL，没有注入客户端。此项不产生官方玩家样本。

后续需要验证：候选模型身份、坐标系和高度、朝向、区域字段的来源、地形适用性，以及跨区块时的原生绑定行为。仅经静态提取而未实机抽查的点须放在独立实验包中，不能声称逐点实测或全地图覆盖。

格式依据和许可见根目录 THIRD_PARTY.md。研究工具采用 GPL-3.0-only，与回放 DLL 分离。

另有独立的 `tools/research-params` .NET 8 工具，只读解开本机 regulation.bin 并使用外部参数定义导出指定字段。已成功读取 BonfireWarpParam 422 行和 PlayRegionParam 593 行；预期用于赐福关联的 warpItemUsePermitBonfireId 字段在本机全为 0，因此这条关联路线没有成立。BonfireWarpParam 的 posY 也被定义标为未使用，不能拿地图图标位置冒充实际地面高度。

该 .NET 工具采用 GPL-3.0-only，需要另行提供兼容的 SoulsFormats 和 ZstdSharp DLL，编译参数分别为 `SoulsFormatsDll` 和 `ZstdSharpDll`；不会把这些研究依赖加载进游戏。本机用只读参考项目现有研究库完成构建，未修改 DS3。DLL 的来源与摘要应随研究复现记录保存，不能用它们替代回放 DLL 的 C++ 构建依赖说明。

## 40 条有限构造快照（2026-10-24）

已只读解析 1347 个地图档案成员（Data2 935 个、DLC 412 个），得到 453 个赐福资产出现位置、433 个不同实体候选。用本机 BonfireWarpParam 的实体键与地图编号校对；只有唯一直接关联碰撞区域且该区域 enableBloodMessage=1 的点才进入保守候选集。保留两处此前实读的精确位置，其余按赐福资产朝向水平偏移 1.25 米、上移 0.03 米。最终为 40 条、22 个地图编号，每图最多六条。

这不是在线样本采集。所有句式、零评价和位置选择都是本地构造；原版地图资产只能提供静态坐标证据，不能证明每个偏移都有可站立地面。没有直接碰撞关联、地图编号不匹配或父层级转换证据不足的点没有靠猜测区域加入。没有把 BonfireWarpParam 未使用的 posY 当地面高度，也没有将全部原版赐福认定为可读位置。

当前三处实读抽样为艾雷教堂、风暴根脚的地下墓地、近林洞窟；近林洞窟使用新提取的直接碰撞区域 3103001，原版阅读界面截图显示“前有赐福”、总评价 0。其余 37 个偏移保留未逐点验证标记。逐条语义包和依据分别为 data/constructed-graces.json 与 data/constructed-graces.provenance.json。更新实测标签不会更改已测试的运行时数据包字节或稳定键。

复现生成（先通过只读工具在本工程新建私有输入，不把原始数据放入发布包）：

```text
python tools/research_map_graces.py --game "F:\Steam\steamapps\common\ELDEN RING\Game" --key-source "另行取得的 UXM 源文件" --dictionary "另行取得的 ER 文件名字典" --archive Data2 --archive DLC --output build/research/maps-new.json
python tools/build_grace_snapshot.py --maps build/research/maps-new.json --params build/research/grace-region-params.json --output build/research/generated-pack.json --provenance build/research/generated-provenance.json
```

生成器拒绝覆盖已存在输出。默认会保留旧两处实测位置，再按固定输入顺序筛选，稳定键来自完整语义内容的摘要。实测标签另行登记，不会由生成器推断成功。

独立 .NET 工具的构建命令为 `dotnet build tools/research-params/ResearchParams.csproj -c Release -p:SoulsFormatsDll="完整路径/SoulsFormats.dll" -p:ZstdSharpDll="完整路径/ZstdSharp.dll"`；运行时依次传入游戏目录、仅包含对应两个 PARAMDEF XML 的目录、新输出 JSON、工程根目录。可用定义版本为 BonfireWarpParam 6 / PlayRegionParam 9，工具会由库校验结构。研究库不是游玩或 C++ 构建依赖。

本机可用研究库来源：JKAnderson/SoulsFormats revision 9c0da6b0721372b34f36b4be503ec020dca1043a；SoulsFormats.dll SHA-256 5e27dd820f14ba216fafdef495241e8b85a6ce4345094326034d7153488b65e7，ZstdSharp.dll SHA-256 5d597fb07c93f99bcbbcf1265bfc60de1f1f8fc070a3acc36f0371a86c326b16。仅只读引用参考工程已有库，没有更改 DS3 工程或发布包。实际依赖的许可不是 MIT；此项独立研究工具使用 GPL-3.0-only，许可证已附。


## 原生联网区域映射（2026-10-25）

只读地图解析器新增 PointParam / PlayArea(type 43) 字段，并保留原坐标、形状、旋转及数据摘要。碰撞体不包含所有网络区域；1202032 跨两个地下地图的实际响应已与 PlayArea 引用相互核对。

`tools/research_mapinfo_archives.py` 仅提取允许路径 other/mapinfotex 的容器到私人研究目录。`tools/research-params` 的 `world` 模式读取 MapPieceTexParam、MapPieceTexParam_m61、NetworkAreaParam；`mapinfo` 模式输出分区统计，不输出像素；`mapinfo-witness` 以实际匿名样本坐标核对像素到区域。GameSystemCommonParam 的外部定义在本版本长度不兼容，未使用其解析结果。

`tools/build_mapinfo_query_manifest.py` 用原生第 0 层红通道行号与参数表、实际标准地图文件、已启用谏言的 PlayRegion 行连接。DLC 高度分支分别作为候选，未知模式拒绝。位图原件、外部参数定义及解码代码窗口均不得打包；公开文件 evidence/mapinfo-native-routing-v1.json 说明证据边界。本地映射不自动证明每个查询被服务器接受，空响应不等于无留言。

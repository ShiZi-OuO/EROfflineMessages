// SPDX-License-Identifier: GPL-3.0-only
// Optional, standalone file research. Never links into the native replay DLL.
using System.Security.Cryptography;
using System.Text.Json;
using SoulsFormats;

if (args.Length==4 && args[0]=="mapinfo") {
    MapInfoMasks.Read(args[1],args[2],args[3]);
    return;
}
if (args.Length==6 && args[0]=="mapinfo-witness") {
    MapInfoMasks.Witness(args[1],args[2],args[3],args[4],args[5]);
    return;
}

if (args.Length==4 && args[0]=="text") {
    var target=Path.GetFullPath(args[2]);
    var privateRoot=Path.GetFullPath(Path.Combine(args[3],"build","research"))+Path.DirectorySeparatorChar;
    if (!target.StartsWith(privateRoot,StringComparison.OrdinalIgnoreCase) || File.Exists(target)) throw new ArgumentException("Use new private research output");
    var textBinder=BND4.Read(args[1]);
    var tables=new Dictionary<string,object>();
    foreach (var file in textBinder.Files) {
        var name=Path.GetFileName(file.Name);
        if (!name.Contains("Blood",StringComparison.OrdinalIgnoreCase) && !name.Contains("PlaceName",StringComparison.OrdinalIgnoreCase)) continue;
        var fmg=FMG.Read(file.Bytes);
        tables[name]=fmg.Entries.Where(e=>e.Text!=null).Select(e=>new{id=e.ID,text=e.Text}).ToArray();
    }
    File.WriteAllText(target,JsonSerializer.Serialize(new{source="local original localization; private research only, not a player-message sample",all_table_names=textBinder.Files.Select(f=>Path.GetFileName(f.Name)).ToArray(),tables},new JsonSerializerOptions{WriteIndented=true})+"\n");
    Console.WriteLine($"Read {tables.Count} selected original localization tables; raw text stays private");
    return;
}
bool worldMode=args.Length==5 && args[0]=="world";
bool graceDetailMode=args.Length==5 && args[0]=="grace-detail";
if (worldMode || graceDetailMode) args=args.Skip(1).ToArray();
if (args.Length != 4) throw new ArgumentException("[world] game-directory definitions-directory output-json workspace-root");
var game=Path.GetFullPath(args[0]);
var definitions=Path.GetFullPath(args[1]);
var output=Path.GetFullPath(args[2]);
var workspace=Path.GetFullPath(args[3]).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
if (!output.StartsWith(workspace,StringComparison.OrdinalIgnoreCase) || output.StartsWith(game+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
    throw new ArgumentException("Output must remain within this workspace, outside game installation");
if (File.Exists(output)) throw new IOException("Research output already exists");
using (var image=File.OpenRead(Path.Combine(game,"eldenring.exe")))
    if (Convert.ToHexString(SHA256.HashData(image))!="F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328")
        throw new InvalidDataException("Unsupported game image");
var binder=SFUtil.DecryptERRegulation(Path.Combine(game,"regulation.bin"));
var parameters=new Dictionary<string,object>();
foreach (var name in worldMode
    ? new[]{"MapPieceTexParam","MapPieceTexParam_m61","NetworkAreaParam"}
    : graceDetailMode ? new[]{"BonfireWarpParam"} : new[]{"BonfireWarpParam","PlayRegionParam"}) {
    var file=binder.Files.Single(f=>Path.GetFileNameWithoutExtension(f.Name)==name);
    var param=PARAM.Read(file.Bytes);
    var definition=PARAMDEF.XmlDeserialize(Path.Combine(definitions,name+".xml"));
    param.ApplyParamdef(definition);
    var rows=new List<object>();
    foreach (var row in param.Rows) {
        if (graceDetailMode && row.ID!=120600 && row.ID!=120601 && row.ID!=68553900) continue;
        var values=new Dictionary<string,object>();
        foreach (var cell in row.Cells) {
            var field=cell.Def.InternalName;
            bool allowed=(worldMode || graceDetailMode) ? cell.Value is not byte[] : name=="BonfireWarpParam"
                ? new[]{"bonfireEntityId","areaNo","gridXNo","gridZNo","eventflagId","textId1","posX","posY","posZ"}.Contains(field)
                : field=="matchAreaId" || field=="enableBloodMessage" || field.StartsWith("warpItemUsePermitBonfireId_",StringComparison.Ordinal);
            if (allowed) values[field]=cell.Value;
        }
        rows.Add(new{id=row.ID,fields=values});
    }
    parameters[name]=new{paramType=param.ParamType,paramVersion=param.ParamdefDataVersion,rows};
    Console.WriteLine($"{name}: {rows.Count} rows read; no game writes");
}
Directory.CreateDirectory(Path.GetDirectoryName(output)!);
File.WriteAllText(output,JsonSerializer.Serialize(new{source="local regulation; game-authored parameter fields; zero player-message samples",parameters},new JsonSerializerOptions{WriteIndented=true})+"\n");

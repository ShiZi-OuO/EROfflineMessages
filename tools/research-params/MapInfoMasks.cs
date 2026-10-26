// SPDX-License-Identifier: GPL-3.0-only
// Private asset reader. Writes palette-index counts, never bitmap pixels.
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using SoulsFormats;

internal static class MapInfoMasks {
    internal static void Witness(string inputDirectory,string samples,string parameters,string output,string workspace) {
        var privateRoot=Path.GetFullPath(Path.Combine(workspace,"build","research"))+Path.DirectorySeparatorChar;
        output=Path.GetFullPath(output);
        if (!output.StartsWith(privateRoot,StringComparison.OrdinalIgnoreCase) || File.Exists(output))
            throw new ArgumentException("New private witness output required");
        using var pack=JsonDocument.Parse(File.ReadAllBytes(samples));
        using var pars=JsonDocument.Parse(File.ReadAllBytes(parameters));
        var tables=new Dictionary<int,Dictionary<int,JsonElement>>();
        foreach(var major in new[]{60,61}) {
            string name=major==60 ? "MapPieceTexParam" : "MapPieceTexParam_m61";
            tables[major]=pars.RootElement.GetProperty("parameters").GetProperty(name).GetProperty("rows")
                .EnumerateArray().ToDictionary(r=>r.GetProperty("id").GetInt32(),r=>r.GetProperty("fields"));
        }
        var rows=pack.RootElement.GetProperty("messages");
        var cache=new Dictionary<string,BND4>();
        var results=new List<object>();int matched=0,outside=0;
        foreach(var row in rows.EnumerateArray()) {
            uint map=row.GetProperty("map").GetUInt32();int major=(int)(map>>24);
            if (major!=60 && major!=61)continue;
            if ((map&255)!=0)throw new InvalidDataException("Unknown variant witness");
            int gx=(int)(map>>16)&255,gz=(int)(map>>8)&255;
            string parent=$"m{major:00}_{gx/4:00}_{gz/4:00}_02";
            if(!cache.TryGetValue(parent,out var binder)) {
                var paths=Directory.EnumerateFiles(inputDirectory,"*-"+parent+".mapinfotexbnd").ToArray();
                if(paths.Length!=1)throw new InvalidDataException("Missing/ambiguous original mask");
                binder=BND4.Read(paths[0]);cache[parent]=binder;
            }
            var member=binder.Files.Single(f=>new[]{parent,parent+"_00"}.Contains(Path.GetFileNameWithoutExtension(f.Name)));
            var b=member.Bytes;
            int I(int o)=>BinaryPrimitives.ReadInt32LittleEndian(b.AsSpan(o,4));
            if(b.Length<54 || I(18)!=256 || I(22)!=256 || I(30)!=0
                || BinaryPrimitives.ReadInt16LittleEndian(b.AsSpan(28,2))!=24)
                throw new InvalidDataException("Native bitmap witness layout");
            var pos=row.GetProperty("position");
            int x=(int)Math.Floor((pos[0].GetDouble()+128)/4)+(gx%4)*64;
            int z=(int)Math.Floor((pos[2].GetDouble()+128)/4)+(gz%4)*64;
            if(x<0 || x>=256 || z<0 || z>=256){outside++;continue;}
            int red=b[I(10)+(z*256+x)*3+2];int region=-1;
            if(tables[major].TryGetValue(red,out var f)) {
                if(major==61 && f.GetProperty("unknown_0x10").GetInt32()!=0) {
                    if(f.GetProperty("unknown_0x10").GetInt32()!=1)throw new InvalidDataException("Unknown height mode");
                    short threshold=unchecked((short)f.GetProperty("unknown_0x14").GetInt32());
                    region=f.GetProperty(pos[1].GetDouble()<=threshold ? "unknownPlayRegion_1" : "unknownPlayRegion_2").GetInt32();
                } else region=f.GetProperty("multiPlayAreaId").GetInt32();
            }
            bool match=region==row.GetProperty("area").GetInt32();if(match)matched++;
            results.Add(new{map,received_area=row.GetProperty("area").GetInt32(),palette_index=red,
                palette_region=region,mask_matches_received_area=match});
        }
        File.WriteAllText(output,JsonSerializer.Serialize(new{static_only=true,server_requests=0,
            game_process_access=false,matched,checked_records=results.Count,outside_parent_bounds=outside,
            mismatches_may_be_native_collision_or_playarea_overrides=true,records=results},new JsonSerializerOptions{WriteIndented=true})+"\n");
        Console.WriteLine($"Native-mask coordinate witness: {matched}/{results.Count} direct palette matches; {outside} outside parent bounds; overrides remain separate");
    }
    internal static void Read(string inputDirectory,string output,string workspace) {
        var privateRoot=Path.GetFullPath(Path.Combine(workspace,"build","research"))+Path.DirectorySeparatorChar;
        output=Path.GetFullPath(output);
        if (!output.StartsWith(privateRoot,StringComparison.OrdinalIgnoreCase) || File.Exists(output))
            throw new ArgumentException("New private research output required");
        var summaries=new List<object>();
        int skipped=0,subtiles=0;
        foreach (var path in Directory.EnumerateFiles(inputDirectory,"*.mapinfotexbnd").OrderBy(p=>p)) {
            var binder=BND4.Read(path);
            foreach(var member in binder.Files) {
                var name=Path.GetFileNameWithoutExtension(member.Name);
                var match=Regex.Match(name,@"^m(60|61)_(\d{2})_(\d{2})_02(?:_0([01]))?$");
                var b=member.Bytes;
                if (!match.Success || b.Length<54 || b[0]!=0x42 || b[1]!=0x4d) {skipped++;continue;}
                int I(int o)=>BinaryPrimitives.ReadInt32LittleEndian(b.AsSpan(o,4));
                short H(int o)=>BinaryPrimitives.ReadInt16LittleEndian(b.AsSpan(o,2));
                int offset=I(10);
                if (I(18)!=256 || I(22)!=256 || H(28)!=24 || I(30)!=0
                    || offset<54 || offset>b.Length-256*256*3)
                    throw new InvalidDataException("Unsupported native map bitmap layout");
                int major=int.Parse(match.Groups[1].Value),px=int.Parse(match.Groups[2].Value),pz=int.Parse(match.Groups[3].Value);
                int layer=match.Groups[4].Success ? int.Parse(match.Groups[4].Value) : 0;
                for(int z=0;z<4;z++)for(int x=0;x<4;x++) {
                    var counts=new SortedDictionary<int,int>();
                    // Positive-height BMP rows are bottom-up. Native getter
                    // 21a450 flips z, while collector world-z decreases by
                    // pixel row. Thus raw row groups follow child-grid Z.
                    for(int row=z*64;row<(z+1)*64;row++)for(int col=x*64;col<(x+1)*64;col++) {
                        int red=b[offset+(row*256+col)*3+2];
                        counts[red]=counts.GetValueOrDefault(red)+1;
                    }
                    int gx=px*4+x,gz=pz*4+z;
                    if(gx>99 || gz>99)throw new InvalidDataException("Child map range");
                    uint map=((uint)major<<24)|((uint)gx<<16)|((uint)gz<<8);
                    summaries.Add(new{map,map_name=$"m{major:00}_{gx:00}_{gz:00}_00",parent=name,layer,
                        red_index_counts=counts,binder=Path.GetFileName(path),
                        binder_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant()});
                    subtiles++;
                }
            }
        }
        File.WriteAllText(output,JsonSerializer.Serialize(new{source="private original map-info BMP palette indices; no message samples",
            native_bitmap_layout_checked=true,child_grid_transform="parent*4+subtile; native 256 metre base and z flip; validate known areas before requests",
            bitmap_pixels_exported=false,subtiles,skipped_members=skipped,subtile_regions=summaries},new JsonSerializerOptions{WriteIndented=true})+"\n");
        Console.WriteLine($"Read {subtiles} layer/subtile palette summaries; {skipped} unrelated members skipped; no bitmap export");
    }
}

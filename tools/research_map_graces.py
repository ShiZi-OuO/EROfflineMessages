# SPDX-License-Identifier: GPL-3.0-only
"""Read selected local ER map assets into private research JSON.

No game writes, process access, EXE patches, save access or network requests.
Public archive key data is supplied separately, not bundled. Oodle is loaded
from the user's game installation in this Python process, never injected.
Format references: UXM 9501be87e272b6dae55e60a13c3f4753ca6fb3bb;
SoulsFormatsNEXT 4b881c3aa520771603afb8808d40d296c78846f1 MSBE/BHD5.
This narrow reader does not produce a validated message pack.
"""
import argparse
import ctypes as c
import hashlib
import json
import math
import re
import struct
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

EXPECTED_EXE='f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328'

def unpack(data,offset,fmt):
    size=struct.calcsize(fmt)
    if offset<0 or offset+size>len(data):raise ValueError('File offset out of bounds')
    return struct.unpack_from(fmt,data,offset)

def utf16(data,offset):
    if not 0<=offset<len(data)-1:raise ValueError('String offset out of bounds')
    for end in range(offset,min(len(data)-1,offset+2048),2):
        if data[end:end+2]==b'\0\0':return data[offset:end].decode('utf-16le')
    raise ValueError('Unterminated bounded UTF-16 string')

def path_hash(path):
    value=0
    for ch in '/'+path.strip('/').replace('\\','/').lower():value=(value*133+ord(ch))&0xffffffffffffffff
    return value

def decrypt_header(data,pem):
    if data[:4]==b'BHD5':return data
    key=load_pem_public_key(pem.encode()).public_numbers()
    size=(key.n.bit_length()+7)//8
    if len(data)%size:raise ValueError('Incomplete RSA archive block')
    return b''.join(pow(int.from_bytes(data[i:i+size],'big'),key.e,key.n).to_bytes(size-1,'big') for i in range(0,len(data),size))

def index_header(data,wanted):
    if data[:4]!=b'BHD5' or data[4]!=0xff:raise ValueError('Expected little endian BHD5')
    buckets,offset=unpack(data,16,'<ii')
    if not 0<=buckets<=100000:raise ValueError('Bucket budget')
    found={}
    for n in range(buckets):
        count,entries=unpack(data,offset+n*8,'<ii')
        if not 0<=count<=100000:raise ValueError('Entry budget')
        for i in range(count):
            name,size,unpadded,position,sha,aes=unpack(data,entries+i*40,'<Qiiqqq')
            if name in wanted:found[wanted[name]]=(size,unpadded,position,aes)
    return found

def read_member(header,entry,stream):
    size,unpadded,offset,aes=entry
    if not 0<size<=64*1024*1024 or offset<0:raise ValueError('Selected file size/offset budget')
    stream.seek(offset);data=bytearray(stream.read(size))
    if len(data)!=size:raise ValueError('Short BDT read')
    if aes:
        key=bytes(header[aes:aes+16]);count,=unpack(header,aes+16,'<i')
        if len(key)!=16 or not 0<=count<=1024:raise ValueError('AES range budget')
        for i in range(count):
            start,end=unpack(header,aes+20+i*16,'<qq')
            if -1 in (start,end) or start==end:continue
            if not 0<=start<end<=size or (end-start)%16:raise ValueError('AES range bounds')
            decryptor=Cipher(algorithms.AES(key),modes.ECB()).decryptor()
            data[start:end]=decryptor.update(bytes(data[start:end]))+decryptor.finalize()
    return bytes(data)

def decompress(data,game):
    if data[:4] in (b'MSB ',b'BND4'):return data
    if data[:4]!=b'DCX\0' or data[40:44]!=b'KRAK' or data[68:72]!=b'DCA\0':raise ValueError('Unsupported map compression')
    raw_size,compressed_size=unpack(data,28,'>II')
    if not 0<raw_size<=64*1024*1024 or compressed_size>len(data)-76:raise ValueError('DCX size budget')
    dll=game/'oo2core_6_win64.dll'
    lib=c.WinDLL(str(dll));decode=lib.OodleLZ_Decompress
    decode.argtypes=[c.c_void_p,c.c_int64,c.c_void_p,c.c_int64,c.c_int,c.c_int,c.c_int,c.c_void_p,c.c_int64,c.c_void_p,c.c_void_p,c.c_void_p,c.c_int64,c.c_int]
    decode.restype=c.c_int64
    source=c.create_string_buffer(data[76:76+compressed_size]);target=c.create_string_buffer(raw_size+64)
    actual=decode(source,compressed_size,target,raw_size,1,0,0,None,0,None,None,None,0,3)
    if actual!=raw_size:raise ValueError('Oodle map decompression failed')
    return target.raw[:raw_size]

def region_geometry(data,entries,index,ancestors=(),budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if budget[0]>512:raise ValueError('Composite geometry node budget')
    if index in ancestors or len(ancestors)>=8 or not 0<=index<len(entries):raise ValueError('Composite region reference budget')
    entry=entries[index];kind=unpack(data,entry+16,'<I')[0]
    position=list(unpack(data,entry+20,'<3f'));rotation=list(unpack(data,entry+32,'<3f'))
    if not all(math.isfinite(v) and abs(v)<1e6 for v in position+rotation):raise ValueError('Region geometry vector bounds')
    result=dict(region_index=index,shape_kind=kind,position=position,rotation_degrees=rotation)
    offset=unpack(data,entry+72,'<q')[0]
    if kind in (1,2,3,4,5):
        count={1:1,2:1,3:2,4:2,5:3}[kind]
        if offset<=0:raise ValueError('Region shape data offset')
        values=list(unpack(data,entry+offset,'<'+str(count)+'f'))
        if not all(math.isfinite(v) and 0<=v<1e6 for v in values):raise ValueError('Region shape dimensions')
        result['shape_parameters']=values
    elif kind==6:
        if offset<=0:raise ValueError('Composite shape offset')
        children=[]
        for n in range(8):
            child,unknown=unpack(data,entry+offset+n*8,'<ii')
            if child<0:continue
            children.append(dict(reference_unknown_field=unknown,geometry=region_geometry(data,entries,child,ancestors+(index,),budget)))
        result['children']=children
    elif kind not in (0,0xffffffff):raise ValueError('Unknown shape kind')
    return result


def map_positions(data):
    if data[:16]!=b'MSB \x01\0\0\0\x10\0\0\0\0\0\x01\xff':raise ValueError('Unsupported MSB header')
    offset=16;sections={};visited=set()
    while offset:
        if offset in visited or len(visited)>=16:raise ValueError('MSB section budget')
        visited.add(offset)
        version,count,name=unpack(data,offset,'<iiq')
        if not 1<=count<=100000:raise ValueError('MSB entry budget')
        entries=list(unpack(data,offset+16,'<'+str(count-1)+'q')) if count>1 else []
        next_offset,=unpack(data,offset+16+(count-1)*8,'<q')
        sections[utf16(data,name)]=entries;offset=next_offset
    models=[utf16(data,entry+unpack(data,entry,'<q')[0]) for entry in sections['MODEL_PARAM_ST']]
    result=[];play_regions=set();play_area_regions=[]
    for region_index,entry in enumerate(sections.get('POINT_PARAM_ST',[])):
        kind,=unpack(data,entry+8,'<I')
        if kind!=43:continue  # MSBE Region.PlayArea, distinct from collision.
        type_offset,=unpack(data,entry+88,'<q')
        if type_offset<=0:raise ValueError('PlayArea type offset')
        region,unknown=unpack(data,entry+type_offset,'<ii')
        position=list(unpack(data,entry+20,'<3f'))
        if not all(math.isfinite(v) and abs(v)<1e6 for v in position):raise ValueError('PlayArea coordinate bounds')
        shape=unpack(data,entry+16,'<I')[0]
        shape_offset=unpack(data,entry+72,'<q')[0]
        dimensions=list(unpack(data,entry+shape_offset,'<3f')) if shape==5 and shape_offset>0 else None
        if dimensions is not None and not all(math.isfinite(v) and 0<=v<1e6 for v in dimensions):raise ValueError('PlayArea shape bounds')
        play_area_regions.append(dict(play_region_id=region,unknown_type_field=unknown,
            region_name=utf16(data,entry+unpack(data,entry,'<q')[0]),position=position,
            rotation_degrees=list(unpack(data,entry+32,'<3f')),shape_kind=shape,
            box_width_depth_height=dimensions,
            geometry=region_geometry(data,sections['POINT_PARAM_ST'],region_index)))
    for entry in sections['PARTS_PARAM_ST']:
        kind,=unpack(data,entry+12,'<I')
        if kind==5:
            type_offset,=unpack(data,entry+104,'<q')
            region,=unpack(data,entry+type_offset+32,'<i')
            if region>0:play_regions.add(region)
        if kind!=13:continue
        model,=unpack(data,entry+20,'<i')
        if not 0<=model<len(models):raise ValueError('MSB model index')
        # Candidate identity must still be confirmed against known in-game points.
        if models[model].lower()!='aeg099_060':continue
        position=list(unpack(data,entry+32,'<3f'));rotation=list(unpack(data,entry+44,'<3f'))
        entity_offset,=unpack(data,entry+96,'<q');entity,=unpack(data,entry+entity_offset,'<I')
        if not all(math.isfinite(v) and abs(v)<1e6 for v in position+rotation):raise ValueError('MSB vector bounds')
        name=utf16(data,entry+unpack(data,entry,'<q')[0])
        type_offset,=unpack(data,entry+104,'<q')
        related=[]
        references=list(unpack(data,entry+type_offset+56,'<6i'))+[unpack(data,entry+type_offset+84,'<i')[0]]
        for index in sorted(set(references)):
            if index<0:continue
            if index>=len(sections['PARTS_PARAM_ST']):raise ValueError('Asset part reference bounds')
            parent=sections['PARTS_PARAM_ST'][index]
            parent_kind,=unpack(data,parent+12,'<I')
            relation=dict(part_name=utf16(data,parent+unpack(data,parent,'<q')[0]),kind=parent_kind)
            if parent_kind==5:
                parent_type,=unpack(data,parent+104,'<q')
                relation['play_region_id']=unpack(data,parent+parent_type+32,'<i')[0]
            related.append(relation)
        result.append(dict(part_name=name,model=models[model],entity_id=entity,position=position,rotation_degrees=rotation,related_parts=related))
    return dict(grace_asset_candidates=result,collision_play_regions=sorted(play_regions),play_area_regions=play_area_regions)

def main():
    p=argparse.ArgumentParser();p.add_argument('--game',required=True);p.add_argument('--key-source',required=True);p.add_argument('--dictionary',required=True)
    p.add_argument('--archive',action='append',default=[]);p.add_argument('--map',action='append',default=[]);p.add_argument('--output',required=True);a=p.parse_args()
    game=Path(a.game).resolve();output=Path(a.output).resolve();workspace=Path(__file__).resolve().parent.parent
    if not output.is_relative_to(workspace) or output.is_relative_to(game):raise ValueError('Output must be inside this workspace, outside game installation')
    if output.exists():raise FileExistsError('Research output already exists')
    if hashlib.sha256((game/'eldenring.exe').read_bytes()).hexdigest()!=EXPECTED_EXE:raise ValueError('Game image mismatch')
    source=Path(a.key_source).read_text(encoding='utf-8-sig').split('EldenRingKeys',1)[1].split('};',1)[0]
    keys=dict(re.findall(r'\["([^"]+)"\]\s*=\s*@"(-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----)"',source,re.S))
    paths=[line.strip().lstrip('/') for line in Path(a.dictionary).read_text(encoding='utf-8-sig').splitlines()]
    paths=[path for path in paths if re.fullmatch(r'map/mapstudio/m\d\d_\d\d_\d\d_\d\d\.msb\.dcx',path)]
    if a.map:paths=[path for path in paths if Path(path).name.removesuffix('.msb.dcx') in a.map]
    if not paths:raise ValueError('No matching map paths')
    wanted={path_hash(path):path for path in paths};maps=[]
    for archive in a.archive or ['Data0']:
        if archive not in keys or not re.fullmatch(r'Data[0-3]|DLC',archive):raise ValueError('Archive allowlist')
        header=decrypt_header((game/(archive+'.bhd')).read_bytes(),keys[archive]);found=index_header(header,wanted)
        print(f'{archive}: {len(found)} selected maps',flush=True)
        with (game/(archive+'.bdt')).open('rb') as stream:
            for path,entry in found.items():
                raw=decompress(read_member(header,entry,stream),game)
                maps.append(dict(path=path,archive=archive,msb_sha256=hashlib.sha256(raw).hexdigest(),**map_positions(raw)))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(source='local game map assets; zero player-message samples',status='research only; not a validated gameplay pack',maps=maps),indent=2)+'\n',encoding='utf-8')
    print(f'{len(maps)} maps, {sum(len(m["grace_asset_candidates"]) for m in maps)} candidate assets; {output}',flush=True)

if __name__=='__main__':main()

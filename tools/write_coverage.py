"""Human-readable placement coverage; localization is documentation only."""
import argparse
import json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
pack=json.loads((root/'data/constructed-graces.json').read_text(encoding='utf-8'))
provenance=json.loads((root/'data/constructed-graces.provenance.json').read_text(encoding='utf-8'))
params=json.loads((root/'build/research/grace-region-params.json').read_text())['parameters']
entities={r['fields']['bonfireEntityId']:r for r in params['BonfireWarpParam']['rows']}
names={}
for language in ['en','zh']:
    tables=json.loads((root/f'build/research/place-names-{language}.json').read_text())['tables']
    names[language]={r['id']:r['text'] for rows in tables.values() for r in rows}
origins={r['local_key']:r for r in provenance['records']}
lines=['# 构造快照覆盖 / Constructed snapshot coverage','',
    '40 条构造记录、22 个地图编号，官方玩家样本 0。全部使用原版句式/词语编号，评价为人工设定的 0。','',
    '40 constructed records across 22 map IDs; zero official player samples. All appraisals are synthetic zeros.','',
    '三处已实机阅读：艾雷教堂、风暴根脚的地下墓地、近林洞窟；其余 37 处使用静态地图与碰撞关联证据，未逐点实机验证。新“前有赐福”句式的版本化记录见 verification/validation.json。','',
    'Three placements have actual reading evidence: Church of Elleh, Stormfoot Catacombs and Groveside Cave. The other 37 have static asset/collision evidence only. See the versioned validation record; this is not per-point acceptance of all 40.','',
    '| 地点 / Location | 地图 / Map | 区域 / Area | 放置依据 / Placement evidence |','| --- | --- | --- | --- |']
for record in pack['messages']:
    o=origins[record['id']];mp=record['map'].to_bytes(4,'big');mapname='m'+'_'.join(f'{n:02}' for n in mp)
    entity=o.get('grace_entity',1042361950 if mp[0]==60 else 30021950)
    row=entities[entity]['fields'];textid=row['textId1']
    zh=names['zh'].get(textid,'名称未取得');en=names['en'].get(textid,'Name unavailable')
    evidence='新版构造句式已实读 / new constructed phrase read in game' if o['new_phrase_reading_verified'] else '静态地图；偏移待抽查 / static map; offset pending sample'
    lines.append(f'| {zh} / {en} | `{mapname}` | {record["area"]} | {evidence} |')
Path(a.output).write_text('\n'.join(lines)+'\n',encoding='utf-8')

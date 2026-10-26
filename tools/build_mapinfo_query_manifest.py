"""Join private native bitmap palette summaries to region parameters.

Outputs finite candidate targets, not gameplay or full-world acceptance. No
bitmap pixels, network requests, game process access or guessed RGB matching.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from native_region_pair import native_pair


def palette_regions(fields, major):
    if major==61 and fields.get('unknown_0x10',0):
        if fields['unknown_0x10']!=1:
            raise ValueError('Unknown native DLC height-selection mode')
        # Exact native d31390: signed 16-bit threshold at +14 selects +20/+24.
        # A whole-block snapshot queries both possible height branches.
        return sorted({fields['unknownPlayRegion_1'],fields['unknownPlayRegion_2']})
    return [fields['multiPlayAreaId']]


def build(base, palette, params, map_assets, enabled):
    targets={tuple(t['pair']):copy.deepcopy(t) for t in base['targets']}
    actual_maps={int.from_bytes(bytes(map(int,Path(m['path']).name[:12][1:].split('_'))),'big')
        for m in map_assets['maps'] if Path(m['path']).name[:3] in ('m60','m61') and Path(m['path']).name[:12].endswith('_00')}
    tables={major:{r['id']:r['fields'] for r in params['parameters'][name]['rows']}
        for major,name in [(60,'MapPieceTexParam'),(61,'MapPieceTexParam_m61')]}
    unknown=set();with_palette=set();new=0
    for tile in palette['subtile_regions']:
        # a59672 passes layer 0 to 21a450. Layer 1 may serve other systems.
        if tile['layer']!=0:continue
        map_id=tile['map'];major=map_id>>24
        if map_id not in actual_maps:continue
        for index,count in tile['red_index_counts'].items():
            fields=tables[major].get(int(index))
            if fields is None:
                unknown.add((major,int(index)));continue
            for region in palette_regions(fields,major):
                if region not in enabled:continue
                pair=native_pair(region,map_id);with_palette.add(map_id)
                if pair not in targets:
                    targets[pair]=dict(id=f'area-{pair[0]}-{pair[1]}',pair=list(pair),expected_maps=[map_id],
                        bases=[],independent_pair_previously_verified=False);new+=1
                target=targets[pair]
                if map_id not in target['expected_maps']:target['expected_maps'].append(map_id)
                target['bases'].append(dict(kind='native_mapinfo_palette_reference',map=tile['map_name'],
                    parent=tile['parent'],layer=tile['layer'],palette_index=int(index),pixels_in_subtile=count,
                    height_mode=fields.get('unknown_0x10',0),binder_sha256=tile['binder_sha256'],server_verified=False))
    result=copy.deepcopy(base);result['targets']=[targets[p] for p in sorted(targets)]
    result.update(target_count=len(targets),status='PREPARED_NOT_AUTHORIZED',full_world_coverage=False,
        additional_palette_targets=new,canonical_world_asset_maps=len(actual_maps),
        canonical_world_maps_with_enabled_palette=len(with_palette),
        canonical_world_maps_without_enabled_palette=sorted(actual_maps-with_palette),
        unknown_palette_indices=[dict(major=a,index=b) for a,b in sorted(unknown)],
        estimated_minimum_query_minutes=round(max(0,len(targets)-1)*10/60,2),
        enabled_rows_without_target=sorted(enabled-{p[1] for p in targets}))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('base','palette','params','maps','regions','output'):p.add_argument('--'+flag,required=True)
    a=p.parse_args();load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    enabled={r['id'] for r in load(a.regions)['parameters']['PlayRegionParam']['rows'] if r['fields']['enableBloodMessage']}
    result=build(load(a.base),load(a.palette),load(a.params),load(a.maps),enabled)
    result['palette_input_sha256']={str(path):hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in [a.base,a.palette,a.params,a.maps,a.regions]}
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['target_count','additional_palette_targets','canonical_world_asset_maps',
        'canonical_world_maps_with_enabled_palette','unknown_palette_indices','full_world_coverage']}))


if __name__=='__main__':main()

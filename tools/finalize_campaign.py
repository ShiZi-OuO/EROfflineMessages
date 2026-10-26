"""Review a finished campaign, merge finite samples and write provenance.

Offline file processing only. Does not launch a game, acquire tickets or connect.
"""
import argparse
import hashlib
import json
from pathlib import Path
from review_campaign_protocol import review
from merge_official_packs import merge
ROOT=Path(__file__).resolve().parents[1]


def clear_inherited_gameplay_claims(provenance):
    """A changed data pack cannot inherit the base pack's runtime acceptance."""
    previous={key:provenance.pop(key) for key in (
        'gameplay_evidence','current_install_individual_ui_witnesses',
        'new_bulk_individual_ui_witnesses','independent_protocol_new_region_individual_offline_ui_witnesses')
        if key in provenance}
    provenance['base_pack_historical_gameplay_evidence']=previous
    for key in ('merged_pack_loaded_in_game','sampled_reading_and_lifecycle_verified',
                'whole_merged_pack_gameplay_verified','all_individual_records_and_maps_gameplay_verified'):
        provenance[key]=False
    return provenance


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',required=True,choices=['v8','v9','v10'])
    a=p.parse_args();load=lambda path:json.loads(path.read_text(encoding='utf-8'))
    parent=a.version=='v9';gap=a.version=='v10'
    prefix='gap' if gap else 'parent' if parent else 'canonical';version=a.version
    base_name='23385' if gap else '23044' if parent else '13069'
    paths=dict(checkpoint=ROOT/f'build/capture/protocol-{prefix}-candidates-{version}.json',
        quarantine=ROOT/f'build/capture/protocol-{prefix}-candidates-{version}-quarantine.json',
        receipt=ROOT/f'evidence/protocol-{prefix}-result-{version}.json',
        plan=ROOT/('build/research/gap-recheck-plan-v10.json' if gap else 'build/research/parent-area-query-plan-v9.json' if parent else 'build/research/canonical-campaign-plan-v8.json'),
        authorization=ROOT/('evidence/gap-recheck-authorization-v10.json' if gap else 'evidence/parent-area-authorization-v9.json' if parent else 'evidence/canonical-campaign-authorization-v8.json'),
        parser_proof=ROOT/'evidence/protocol-cohort-reviewed-result-v3.json')
    auth=load(paths['authorization']);receipt=load(paths['receipt'])
    plan_sha=hashlib.sha256(paths['plan'].read_bytes()).hexdigest()
    if auth.get('approved_by_user') is not True or auth['plan_sha256']!=plan_sha or receipt['plan_sha256']!=plan_sha:
        raise ValueError('Exact approved plan/receipt required')
    pack,report=review(*[load(paths[k]) for k in ('checkpoint','quarantine','receipt','plan','parser_proof')])
    report['input_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}
    cohort=ROOT/f'data/official-protocol-{prefix}-{version}-{len(pack["messages"])}.json'
    merged=merge([load(ROOT/f'data/official-expansion-{base_name}.json'),pack]);n=len(merged['messages'])
    # A retry may only update appraisals: keep old immutable outputs even if N is unchanged.
    suffix='-v10' if gap else ''
    merged_path=ROOT/f'data/official-expansion-{n}{suffix}.json'
    review_path=ROOT/f'evidence/protocol-{prefix}-{version}-reviewed.json'
    provenance_path=ROOT/f'data/official-expansion-{n}{suffix}.provenance.json'
    for path in (cohort,merged_path,review_path,provenance_path):
        if path.exists():raise ValueError('Immutable outputs already exist: '+str(path.relative_to(ROOT)))
    def write(path,value):
        with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    write(cohort,pack);write(merged_path,merged);write(review_path,report)
    provenance=clear_inherited_gameplay_claims(load(ROOT/f'data/official-expansion-{base_name}.provenance.json'))
    provenance['cohorts'].append(dict(file=str(cohort.relative_to(ROOT)),source_type=pack['source_type'],
        records=len(pack['messages']),sha256=hashlib.sha256(cohort.read_bytes()).hexdigest()))
    provenance.update(runtime_pack_sha256=hashlib.sha256(merged_path.read_bytes()).hexdigest(),unique_records=n,
        map_ids=len({r['map'] for r in merged['messages']}),duplicate_semantics_removed=sum(c['records'] for c in provenance['cohorts'])-n,
        latest_campaign_quarantined_records=report['quarantined_records'],latest_campaign_stopped_early=report['stopped_early'])
    write(provenance_path,provenance)
    print(json.dumps(dict(cohort_records=len(pack['messages']),merged_records=n,map_ids=provenance['map_ids'],
        pack=str(merged_path.relative_to(ROOT)),quarantined_records=report['quarantined_records'],
        stopped_early=report['stopped_early'],full_world_coverage=False,gameplay_acceptance=False)))


if __name__=='__main__':main()

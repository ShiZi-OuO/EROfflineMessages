"""Audit saved authenticated batch records; preserve partial-run boundaries.

No network or game access. Each admitted row must belong to an accepted response
in the exact authorized manifest. Quarantined/failed responses are never mixed
in. Prior UI evidence establishes parser provenance, not UI testing of new rows.
"""
import argparse
import hashlib
import json
from pathlib import Path
from capture_client_cache import FIELDS, semantics, fingerprint
from merge_official_packs import merge
from native_region_pair import native_pair


def review(checkpoint, receipt, manifest, parser_proof):
    if (checkpoint.get('finished') is not True or receipt.get('session_rpc_success') is not True
            or receipt.get('checkpoint_saved') is not True
            or checkpoint['stages'] != receipt['stages']
            or parser_proof.get('source_type') != 'official_protocol_sample'
            or parser_proof.get('individually_offline_ui_matched',0)<1):
        raise ValueError('Completed checkpoint, authenticated receipt and prior parser/UI proof required')
    targets={t['id']:t for t in manifest['targets']}
    steps=[s for s in receipt['stages'] if isinstance(s,dict)]
    if [s['target'] for s in steps] != [t['id'] for t in manifest['targets'][:len(steps)]]:
        raise ValueError('Response order differs from authorized manifest')
    cursor=0;admitted=[];accepted=0;quarantined=0;failed=0
    for n,stage in enumerate(steps):
        target=targets[stage['target']]
        if list(stage['requested_pair']) != target['pair']:
            raise ValueError('Requested pair changed')
        if stage['unexpected_pair_counts']:
            if n != len(steps)-1 or not receipt.get('error'):
                raise ValueError('Area mismatch must terminate the run')
            failed+=1;continue
        if stage['unexpected_map_counts']:
            if stage.get('disposition')=='quarantined_map_association':
                quarantined+=1;continue
            if n != len(steps)-1 or not receipt.get('error'):
                raise ValueError('Unquarantined map mismatch must terminate the run')
            failed+=1;continue
        count=stage['returned_entries']
        rows=checkpoint['records'][cursor:cursor+count]
        if len(rows)!=count:
            raise ValueError('Incomplete accepted response checkpoint')
        for row in rows:
            if set(row)!=set(FIELDS)|{'candidate_key'}:
                raise ValueError('Anonymous semantic allowlist mismatch')
            value=semantics(row)
            if row['candidate_key']!=fingerprint(value):
                raise ValueError('Candidate key mismatch')
            if (value['map'] not in target['expected_maps']
                    or native_pair(value['area'],value['map'])!=tuple(target['pair'])):
                raise ValueError('Saved record belongs to a different response')
            admitted.append(dict(value,id='7d'+fingerprint(value)[:14]))
        cursor+=count;accepted+=1
    if cursor!=len(checkpoint['records']) or receipt['anonymous_candidate_records']!=cursor:
        raise ValueError('Unattributed checkpoint records')
    pack=merge([dict(schema_version=1,game='eldenring',source_type='official_protocol_sample',messages=admitted)])
    pack['description']=('Finite anonymous authenticated official-service batch. Only manifest-matched '
        'accepted responses admitted; failed/quarantined responses excluded. Independent experimental '
        'protocol, not normal-client receipt. Prior protocol parser/UI witness exists; this cohort '
        'has not been individually read in game. Not a complete server dump or full-world coverage.')
    report=dict(source_type=pack['source_type'],records=len(pack['messages']),
        received_record_count=cursor,accepted_targets=accepted,quarantined_targets=quarantined,
        failed_targets=failed,planned_targets=len(manifest['targets']),
        requests_without_decoded_response=receipt['message_list_requests']-len(steps),
        stopped_early=len(steps)<len(manifest['targets']) or bool(receipt.get('error')),
        maps=sorted({r['map'] for r in admitted}),individually_offline_ui_matched=0,
        prior_parser_offline_ui_witnesses=parser_proof['individually_offline_ui_matched'],
        full_world_coverage=False,gameplay_acceptance=False)
    return pack,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('checkpoint','receipt','manifest','authorization','parser-proof','output','report'):
        p.add_argument('--'+flag,required=True)
    a=p.parse_args();load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    approval=load(a.authorization)
    if approval.get('approved_by_user') is not True or approval['manifest_sha256']!=hashlib.sha256(Path(a.manifest).read_bytes()).hexdigest():
        raise ValueError('Exact authorized manifest required')
    pack,report=review(load(a.checkpoint),load(a.receipt),load(a.manifest),load(a.parser_proof))
    report['input_sha256']={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest()
        for p in [a.checkpoint,a.receipt,a.manifest,a.authorization,a.parser_proof]}
    for path,value in [(Path(a.output),pack),(Path(a.report),report)]:
        with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='input_sha256'}))


if __name__=='__main__':main()

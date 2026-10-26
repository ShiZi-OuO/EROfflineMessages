"""Check native phrase lookups against private original FMG metadata.

Exports counts/unknown IDs only, never the game's text tables. Static evidence
does not confer language UI validation. No game/server access.
"""
import argparse
import json
from pathlib import Path


def audit(records, tables):
    known={r['id'] for r in tables['tables']['BloodMsg.fmg'] if r['text']}
    missing=set()
    for r in records:
        for n in (1,2):
            template,word=r['template'+str(n)],r['word'+str(n)]
            if n==2 and not template:
                continue
            # Native combined template/word FMG key, checked against the
            # original-position UI witness. Keep this separate from plain IDs.
            key=(template-9900)*100000+word if word else template
            if key not in known:
                missing.add(key)
        if r['conjunction'] and r['conjunction'] not in known:
            missing.add(r['conjunction'])
    return dict(records_checked=len(records),missing_native_lookup_ids=sorted(missing),
        actual_UI_test=False,native_text_tables_exported=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',required=True)
    p.add_argument('--dictionary',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    data=json.loads(Path(a.data).read_text(encoding='utf-8'))
    result=audit(data.get('messages',data.get('records',[])),json.loads(Path(a.dictionary).read_text(encoding='utf-8')))
    result['input_kind']=data.get('source_type',data.get('type'))
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()

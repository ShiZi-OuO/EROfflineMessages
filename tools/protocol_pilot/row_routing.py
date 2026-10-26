"""Split known non-replayable world variants without altering their data.

Only native LOD0 0x10 records in the requested base tile are quarantined. A
different region/tile, unknown packet schema or other map is still fatal.
"""


def split_rows(records,routes,targets,quarantine_unmapped=False):
    if len(records)!=len(routes):raise ValueError('Row route count mismatch')
    accepted=[];quarantine=[]
    for row,route in zip(records,routes):
        pair=tuple(route['pair'])
        if pair not in targets or route['candidate_key']!=row['candidate_key']:
            raise ValueError('Wrong/unattributed response area')
        maps=targets[pair]
        if row['map'] in maps:
            accepted.append(row);continue
        major=row['map']>>24
        if (50<=major<=88 and row['map']&255==0x10
                and row['map']&0xffffff00 in maps):
            quarantine.append(row);continue
        if quarantine_unmapped:
            quarantine.append(row);continue
        raise ValueError('Unrecognized target map; stop without guessing a remap')
    return accepted,quarantine

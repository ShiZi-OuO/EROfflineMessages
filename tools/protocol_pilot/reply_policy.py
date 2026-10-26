"""Pure response disposition; never relax area/schema checks to grow counts."""


def disposition(summary, manifest=None):
    if summary['unexpected_pair_counts']:
        raise RuntimeError('Wrong target area pair; collection stopped')
    wrong=summary['unexpected_map_counts']
    if not wrong:
        return 'accepted'
    if (manifest is not None
            and manifest.get('map_association_policy')=='quarantine_known_asset_map_mismatch_continue'
            and set(map(int,wrong)).issubset(set(manifest['known_asset_map_ids']))):
        return 'quarantined_map_association'
    raise RuntimeError('Wrong or unknown target map; collection stopped')

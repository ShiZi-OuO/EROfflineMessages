"""Pure translation of exact-image native area conversion at RVA a62100.

Produces candidate query pairs, not proof that a remote area is accepted or has
messages. matchAreaId and payload secondary_area are not this first field.
"""


def native_pair(play_region, map_id):
    if type(play_region) is not int or not 0 < play_region < 0xffffffff:
        raise ValueError('Play region must be a nonzero u32')
    if type(map_id) is not int or not 0 < map_id < 0xffffffff:
        raise ValueError('Map must be a nonzero u32')
    area, block, tile, variant = map_id.to_bytes(4, 'big')
    if variant:
        raise ValueError('Unknown map variant requires separate validation')
    first = ((area * 100 + block) * 100 + tile) * 10 if 50 <= area <= 88 else play_region
    return first, play_region

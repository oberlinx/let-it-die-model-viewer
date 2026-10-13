"""Describe the editor's icon sprite sheets: which icons go in which sheet, and which ids borrow another id's icon.

Usage: atlas_spec.py <items-dir>      (needs gear.json, mushrooms.json, images.json from items.py and rmap.py)
Writes atlas_spec.json: {cell: [w, h], sheets: {name: {cols, names}}, alias: {id: icon name}}.
"""
import os, sys, json
D = sys.argv[1]
gear = json.load(open(os.path.join(D, 'gear.json'), encoding='utf-8'))
msr = json.load(open(os.path.join(D, 'mushrooms.json'), encoding='utf-8'))
images = json.load(open(os.path.join(D, 'images.json')))
def uniq(seq):
    out = []
    for x in seq:
        if x and x in images and x not in out: out.append(x)
    return out
items = uniq([m['icon'] for m in gear['materials']] + [x.get(k) for x in msr['mushrooms'] + msr['beasts'] for k in ('icon', 'iconGrilled')] +
             ['RMAP_1', 'RMAP_2', 'RMAP_3', 'UN_RMAP_1', 'UN_RMAP_2', 'UN_RMAP_3', 'Money_1', 'Spirit_1', 'Blood_1', 'DMetal_1', 'VIPticket_1', 'VIPticket_2'])
weapons = uniq(p['icon'] for p in gear['gear'] if p['type'] == 'Weapon')
armor = uniq(p['icon'] for p in gear['gear'] if p['type'] != 'Weapon')
alias = {p['id']: p['icon'] for p in gear['gear'] if p['icon'] and p['icon'] != p['id']}
spec = dict(cell=[40, 49], sheets=dict(items=dict(cols=20, names=items), weapons=dict(cols=20, names=weapons), armor=dict(cols=28, names=armor)), alias=alias)
json.dump(spec, open(os.path.join(D, 'atlas_spec.json'), 'w'), separators=(',', ':'))
print({k: len(v['names']) for k, v in spec['sheets'].items()}, 'alias', len(alias))

"""Dump LET IT DIE gear, materials, mushrooms and beasts: catalogue data plus their raw icons.

Usage: items.py <out-dir>
Writes gear.json and mushrooms.json (catalogue data), images.json (name -> width, height, format) and one raw
file per image (<name>.bgra or <name>.dxt5) for the converter page to turn into WebP.
"""
import os, sys, json, re, sqlite3
import upk, lzo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
DB = os.path.abspath(os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
TEXT = {(s, i): t for s, i, t in c.execute("select sct, id, txt from master_text where lang='int'")}
FILES = set(os.listdir(upk.GAME))


def tx(key):
    if not isinstance(key, str): return None
    s, _, i = key.partition('.')
    return TEXT.get((s, i))

def clean(t):
    return re.sub(r'[ \t]+', ' ', (t or '').replace('//', '\n').replace('\n', ' ')).strip()

def rows(sql):
    cur = c.execute(sql); cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur]


_tfc = {}; images = {}
def dump_image(pkg_file, tex_name, out_name):
    """Write a texture's top mip raw; returns False if the package or texture does not exist."""
    if out_name in images: return True
    if pkg_file not in FILES: return False
    p = upk.Package(pkg_file); e = p.find(tex_name, 'Texture2D')
    if not e: return False
    r = p.reader(e); r.i32(); pr = p.props(r)
    fmt = {'PF_A8R8G8B8': 'bgra', 'PF_DXT5': 'dxt5'}[pr['Format']]
    fl = r.u32(); r.i32(); size = r.u64(); r.u64()
    if not fl & 1: r.p += size
    assert r.i32() >= 1
    fl = r.u32(); cnt = r.i32(); size = r.u64(); off = r.u64()
    if fl & 1:
        name = pr.get('TextureFileCacheName', 'Textures')
        if name not in _tfc: _tfc[name] = open(os.path.join(upk.GAME, name + '.tfc'), 'rb')
        _tfc[name].seek(off); data = _tfc[name].read(size)
    else:
        data = r.raw(size)
    if fl & 0x10: data, _ = lzo.read_chunk(data, 0)
    w = r.i32(); h = r.i32()
    # DXT data covers whole 4x4 blocks, so its stored size can exceed the visible size
    bw, bh = (w + 3) // 4 * 4, (h + 3) // 4 * 4
    assert len(data) == (w * h * 4 if fmt == 'bgra' else bw * bh), (out_name, len(data), w, h, fmt)
    open(os.path.join(OUT, out_name + '.' + fmt), 'wb').write(data)
    images[out_name] = dict(w=w, h=h, fmt=fmt)
    return True

def icon(iid):
    """Standard 108x132 icon for an id, or None."""
    return iid if dump_image('UI_Icon_%s_SF.upk' % iid, 'TX_UI_Image_' + iid, iid) else None


# ---------------- gear (master_part) and materials (master_item) ----------------
TYPE = {'PTTP_ARM': 'Weapon', 'PTTP_HEAD': 'Head', 'PTTP_BODY': 'Body', 'PTTP_LEGS': 'Legs', 'PTTP_MASK': 'Gas mask', 'PTTP_PANTS': 'Underwear'}
rage = {r['id']: clean(tx(r['name'])) for r in rows('select id, name from master_sklmv')}
armtype = {r['id']: clean(tx(r['name']) or r['name']) for r in rows('select id, name from master_ptarm_type')}
parts = rows('select * from master_part order by sort_no, id')
names = {p['id']: clean(tx(p['name']) or '') for p in parts}

def part_icon(pid):
    """A part's own icon, else the plain version's (gold '_G' variants), else an earlier tier's."""
    for cand in [pid, re.sub(r'_G$', '', pid)]:
        if icon(cand): return cand
    m = re.fullmatch(r'(.*)(\d)', pid)             # ...4, ...3 and so on down from the id's last digit
    if m:
        for n in range(int(m.group(2)) - 1, 0, -1):
            if icon(m.group(1) + str(n)): return m.group(1) + str(n)
    return None

SKIP = {'PT_ARM_WP023_001', 'PT_ARM_WP000_001', 'PT_ARM_Sand'}      # Landmine, Fists, Sand: in the data but not gear you can own
gear = []
for p in parts:
    name = names[p['id']]
    if not name or p['id'] in SKIP: continue
    wp = re.match(r'PT_ARM_WP(\d\d\d)_', p['id'])
    g = dict(id=p['id'], name=name, type=TYPE.get(p['type'], p['type']), category=p['drcat'].replace('DRCAT_', '').title() if p['drcat'] else '',
             rarity=p['rarity'], icon=part_icon(p['id']), dur=p['dur'], buy=p['price_s'], sell=p['price_b'])   # price_s: shop price, price_b: what you get back
    if p['type'] == 'PTTP_ARM':
        g['atk'] = [p['atk0'], p['atk']]
        if wp and 'PTARMTP_%02d' % int(wp.group(1)) in armtype: g['weapon'] = armtype['PTARMTP_%02d' % int(wp.group(1))]
        if p['sklmv'] in rage and rage[p['sklmv']]: g['rage'] = rage[p['sklmv']]
        if p['capacity']: g['ammo'] = p['capacity']
    elif p['def']:
        g['def'] = [p['def0'], p['def']]
    if p['lvllmt']: g['req'] = [p['lvllmttp'], p['lvllmt']]
    # how each value grows per upgrade level (value x factor^(level - 1)): [attack or defence, durability, requirement]
    g['grow'] = [p['atk_c'] if p['type'] == 'PTTP_ARM' else p['def_c'], p['dur_c'], p['lvllmt_c']]
    g['levels'] = max(1, p['reflvllmt'])        # highest raw level; a part starts at raw level 1
    if p['is_limitbreak']: g['uncap'] = True      # continues an earlier part's +N instead of starting at +0
    if p['nextptid'] and names.get(p['nextptid']): g['next'] = p['nextptid']
    if p['platform']: g['psOnly'] = True
    gear.append(g)

# R&D and upgrade costs (master_part_research). mateN_id are the materials; craft_* is the one-off development cost,
# lvup_* the cost of each upgrade level (a base amount that grows with level). Spirit = SPLithium.
# The page works out the per-level costs, so the raw parameters are passed through:
#   upgrade = { spl: [base, multiplier per level], time: [first, added per level] in minutes,
#               mats: [[material id, base amount, amount added, every N levels (0 = a fraction every level)], ...] }
#   levels = the part's highest raw level (master_part.reflvllmt); uncap = it continues an earlier part's +N
research = {r['ptid']: r for r in rows('select * from master_part_research')}
part_by_id = {p['id']: p for p in parts}
for g in gear:
    r = research.get(g['id'])
    if not r or not r['is_open']: continue
    mats = [(r['mate%d_id' % i], r['craft_mate%d_num' % i], r['lvup_mate%d_num' % i], r['lvup_mate%d_add_num' % i]) for i in range(1, 6) if r['mate%d_id' % i]]
    craft = [[m, int(n)] for m, n, _, _ in mats if n >= 1]
    if craft or r['craft_spirit']: g['craft'] = dict(spl=r['craft_spirit'], mats=craft)
    up = [[r['mate%d_id' % i], r['lvup_mate%d_num' % i], r['lvup_mate%d_add_num' % i], r['lvup_mate%d_add_lv' % i]] for i in range(1, 6)
          if r['mate%d_id' % i] and (r['lvup_mate%d_num' % i] > 0 or r['lvup_mate%d_add_num' % i] > 0)]
    p = part_by_id[g['id']]
    if p['reflvllmt'] > 1 and (up or r['lvup_spirit']):
        g['upgrade'] = dict(spl=[r['lvup_spirit'], r['lvup_spirit_c']], time=[r['init_waiting_minute'], r['add_waiting_minute']], mats=up)
        g['levels'] = p['reflvllmt']
        if p['is_limitbreak']: g['uncap'] = True

MAT = {'ITTP_MATERIAL': 'Material', 'ITTP_HEAL': 'Consumable', 'ITTP_BACK': 'Consumable', 'ITTP_BIV': 'Consumable', 'ITTP_WOOD': 'Material'}
materials = []
for it in rows("select * from master_item where itemtype != 'ITTP_RMAP' order by sort_no, itemid"):
    name = clean(tx(it['name']) or '')
    if not name: continue
    m = dict(id=it['itemid'], name=name, type=MAT.get(it['itemtype'], it['itemtype']), rarity=it['rarity'], icon=icon(it['itemid']),
             desc=clean(tx(it['desc'])), sell=it['sell_money'])
    if it['buy_money']: m['buy'] = it['buy_money']
    if it['platform']: m['psOnly'] = True
    materials.append(m)
json.dump(dict(gear=gear, materials=materials), open(os.path.join(OUT, 'gear.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(gear), 'gear,', sum(1 for g in gear if not g['icon']), 'without icon;', len(materials), 'materials,', sum(1 for m in materials if not m['icon']), 'without icon')

# ---------------- mushrooms and beasts ----------------
mefc = {r['id']: r for r in rows('select * from master_mushroom_efc')}
def effect(eid):
    e = mefc.get(eid)
    if not e: return None
    name = tx(e['name']) or ''
    for i in range(6): name = name.replace('#%d' % i, str(e['val%d' % i]))     # the text carries #0..#5 placeholders
    name = clean(name.strip().replace(chr(10), ', '))
    if not name: return None
    d = dict(name=name)
    if e['tmmin']: d['seconds'] = [e['tmmin'], e['tmmax']] if e['tmmax'] != e['tmmin'] else [e['tmmin']]
    return d

unlocks = {}
for r in rows('select o.sklid, o.msrid, o.cnt, s.name from master_skill_open_mushroom o join master_skill s on s.id = o.sklid order by s.no'):
    unlocks.setdefault(r['msrid'], []).append(dict(id=r['sklid'], name=clean(tx(r['name'])), count=r['cnt']))

def spawn_floors(gen_col, gen_table, id_col):
    """{thing id: sorted floor numbers} from each floor's spawn list (master_floor.<gen_col> -> <gen_table>)."""
    members = {}
    for r in rows('select id, %s as thing, freq from %s' % (id_col, gen_table)):
        if r['freq'] > 0: members.setdefault(r['id'], set()).add(r['thing'])
    out = {}
    for r in rows('select distinct no, %s as gen from master_floor where no > 0' % gen_col):
        for thing in members.get(r['gen'], ()): out.setdefault(thing, set()).add(r['no'])
    return {k: sorted(v) for k, v in out.items()}

def ranges(nums):
    """[1, 2, 3, 7, 9, 10] -> [[1, 3], [7, 7], [9, 10]]"""
    out = []
    for n in nums:
        if out and n == out[-1][1] + 1: out[-1][1] = n
        else: out.append([n, n])
    return out

def placed_zones(stage_table, gen_table, id_col):
    """{thing id: zone names} for things placed at fixed points of a zone (master_stage_*), directly or through a spawn list."""
    zone = {r['stgid']: r['stgpfx'] for r in rows('select distinct stgid, stgpfx from master_floor')}
    members = {}
    for r in rows('select id, %s as thing, freq from %s' % (id_col, gen_table)):
        if r['freq'] > 0: members.setdefault(r['id'], set()).add(r['thing'])
    out = {}
    for r in rows('select stgid, %s as thing, genid from %s' % (id_col, stage_table)):
        for thing in ({r['thing']} if r['thing'] else set()) | members.get(r['genid'], set()):
            if zone.get(r['stgid']): out.setdefault(thing, set()).add(zone[r['stgid']])
    order = ['Metro', 'Arcade', 'Amusement', 'Rooftop', 'Hazama', 'Heaven']
    return {k: sorted(v, key=lambda z: order.index(z) if z in order else 99) for k, v in out.items()}

msr_zones = placed_zones('master_stage_mushroom', 'master_mushroom_gen', 'msrid')
bst_zones = placed_zones('master_stage_beast', 'master_beast_gen', 'bstid')
msr_floors = spawn_floors('msrgen', 'master_mushroom_gen', 'msrid')
bst_floors = spawn_floors('bstgen', 'master_beast_gen', 'bstid')

mushrooms = []
for m in rows('select * from master_mushroom order by idx'):
    name = clean(tx(m['c_name']) or '')
    if not name: continue
    n = m['id'][4:]
    d = dict(id=m['id'], no=m['idx'], name=name, desc=clean(tx(m['desc'])), found=clean(tx(m['distribution'])), size=clean(tx(m['length'])),
             icon=icon(m['id']), buy=m['price_s_money'], sell=m['price_b'], raw=dict(effect=effect(m['c_pefcid']), hp=m['c_recvhp']))
    if dump_image('UI_Icon_%s_SF.upk' % m['id'], 'TX_UI_Image_%s_R' % m['id'], m['id'] + '_R'): d['iconGrilled'] = m['id'] + '_R'
    if dump_image('UI_EnmaMenu_MSR_%s_SF.upk' % n, 'TX_UI_Image_MSR_%s_Art' % n, m['id'] + '_Art'): d['art'] = m['id'] + '_Art'
    if m['c_nefcid'] and effect(m['c_nefcid']): d['raw']['sideEffect'] = dict(effect(m['c_nefcid']), chance=m['c_nefcrate'])
    grilled = clean(tx(m['r_name']) or '')
    if m['enable_roast'] and grilled:
        d['grilled'] = dict(name=grilled, effect=effect(m['r_pefcid']), hp=m['r_recvhp'])
        if m['r_nefcid'] and effect(m['r_nefcid']): d['grilled']['sideEffect'] = dict(effect(m['r_nefcid']), chance=m['r_nefcrate'])
    if m['id'] in unlocks: d['unlocks'] = unlocks[m['id']]
    if m['id'] in msr_floors: d['floors'] = ranges(msr_floors[m['id']])
    if m['id'] in msr_zones: d['zones'] = msr_zones[m['id']]
    mushrooms.append(d)

befc = {r['id']: clean(tx(r['name'])) for r in rows('select id, name from master_beast_efc')}
bref = {}
for r in rows('select * from master_beast_efcref'):
    if befc.get(r['efcid']): bref.setdefault((r['bstid'], r['state']), []).append(befc[r['efcid']])
msr_names = {m['id']: m['name'] for m in mushrooms}
beasts = []
for b in rows('select * from master_beast order by idx'):
    name = clean(tx(b['name']) or '')
    if not name: continue
    n = b['id'][4:]
    d = dict(id=b['id'], no=b['idx'], name=name, grilledName=clean(tx(b['bname'])), desc=clean(tx(b['desc'])), found=clean(tx(b['distribution'])),
             size=clean(tx(b['length'])), icon=icon(b['id']), effects={str(s): bref[(b['id'], s)] for (bid, s) in sorted(bref) if bid == b['id']})
    if dump_image('UI_Icon_%s_SF.upk' % b['id'], 'TX_UI_Image_%s_R' % b['id'], b['id'] + '_R'): d['iconGrilled'] = b['id'] + '_R'
    if dump_image('UI_Enma_%s_SF.upk' % b['id'], 'TX_UI_Image_%s_Art' % b['id'], b['id'] + '_Art'): d['art'] = b['id'] + '_Art'
    if b['rwdmsrid'] in msr_names: d['drops'] = dict(id=b['rwdmsrid'], name=msr_names[b['rwdmsrid']])
    if b['id'] in bst_floors: d['floors'] = ranges(bst_floors[b['id']])
    if b['id'] in bst_zones: d['zones'] = bst_zones[b['id']]
    beasts.append(d)
json.dump(dict(mushrooms=mushrooms, beasts=beasts), open(os.path.join(OUT, 'mushrooms.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
masks = []
for n in range(1, 9):
    pid = 'PT_GAS_HEAD_%03d' % n
    masks.append(dict(no=n, name=names.get(pid, ''), icon=icon(pid), female='ASSET_NF_GAS_HEAD_%03d' % n, male='ASSET_NM_GAS_HEAD_%03d' % n))
json.dump(masks, open(os.path.join(OUT, 'gasmasks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(images, open(os.path.join(OUT, 'images.json'), 'w'))
print(len(mushrooms), 'mushrooms,', len(beasts), 'beasts,', len(images), 'images')

"""Dump LET IT DIE skill decals: catalogue data (decals.json) and raw 256px icons (<icon>.bgra / <icon>.dxt5)."""
import os, sys, json, re, sqlite3
import upk, lzo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
# LID_MASTERS can point at another copy of the database, e.g. an unmodded backup: a modded masters.db can hold
# extra gear and has its PlayStation-only flags cleared.
DB = os.path.abspath(os.environ.get('LID_MASTERS') or os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
TEXT = {(s, i): t for s, i, t in c.execute("select sct, id, txt from master_text where lang='int'")}

def tx(key):
    s, _, i = (key or '').partition('.')
    return TEXT.get((s, i))

def clean(t):
    return re.sub(r'[ \t]+', ' ', (t or '').replace('//', '\n').replace('\n', ' ')).strip()

_tfc = {}
def read_icon(pkg_file, tex_name):
    """Top mip of a UI texture: raw BGRA bytes (A8R8G8B8) or raw DXT5 blocks, plus its width and format."""
    p = upk.Package(pkg_file)
    e = p.find(tex_name, 'Texture2D')
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
    sx = r.i32(); sy = r.i32()
    assert len(data) == cnt == sx * sy * (4 if fmt == 'bgra' else 1), (len(data), cnt, sx, sy)
    return data, sx, fmt

files = set(os.listdir(upk.GAME))
cats = {i: tx(n) for i, n in c.execute('select id, name from master_skill_category')}
msr_name = {}
cur = c.execute('select * from master_mushroom'); mcols = [d[0] for d in cur.description]
for row in cur:
    m = dict(zip(mcols, row))
    msr_name[m['id']] = clean(tx(m.get('c_name')) or tx(m.get('name')) or m['id'])
unlock = {}
for sk, ms, cnt in c.execute('select sklid, msrid, cnt from master_skill_open_mushroom'):
    unlock.setdefault(sk, []).append(dict(mushroom=msr_name.get(ms, ms), count=cnt))
odds = dict(c.execute("select sklid, odds from master_skillgacha_odds where odds > 0"))
total = sum(odds.values())

cur = c.execute('select * from master_skill order by no'); cols = [d[0] for d in cur.description]
decals = []; icons = {}
for row in cur:
    s = dict(zip(cols, row))
    icon = s['id'] if 'UI_%s_M_SF.upk' % s['id'] in files else re.sub(r'_P$', '', s['id'])
    if 'UI_%s_M_SF.upk' % icon not in files: icon = None
    desc = tx(s['desc']) or ''
    for i in range(6): desc = desc.replace('#%d' % i, str(s['val%d' % i]))
    d = dict(id=s['id'], no=s['no'], name=clean(tx(s['name'])) or s['id'], desc=clean(desc), icon=icon,
             category=cats.get(s['category']) or s['category'], rarity=s['rarity'], premium=bool(s['premium']),
             psOnly=bool(s['platform']), source=clean(tx(s['getroute'])), type=s['type'],
             values=[s['val%d' % i] for i in range(6)],
             sell=dict(coins=s['sell_money'], recycle=s['sell_recycle_point']), buy=dict(coins=s['buy_money'], spl=s['buy_spirit'], recycle=s['buy_recycle_point']))
    if s['id'] in unlock: d['unlock'] = unlock[s['id']]
    if s['id'] in odds: d['stewOdds'] = round(100.0 * odds[s['id']] / total, 3)
    decals.append(d)
    if icon and icon not in icons:
        data, sx, fmt = read_icon('UI_%s_M_SF.upk' % icon, 'TX_UI_Image_%s_M' % icon)
        open(os.path.join(OUT, icon + '.' + fmt), 'wb').write(data); icons[icon] = dict(size=sx, fmt=fmt)
json.dump(decals, open(os.path.join(OUT, 'decals.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(icons, open(os.path.join(OUT, 'icons.json'), 'w'))
print(len(decals), 'decals,', len(icons), 'icons,', sorted({(v['size'], v['fmt']) for v in icons.values()}), 'no icon:', [d['id'] for d in decals if not d['icon']])

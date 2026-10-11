"""Dump the Decoyshroom statues: the static mesh the game shows for each fighter body when a decoy is thrown.

Usage: decoys.py <dump-dir>     (the same folder extract.py writes to)
Each body has a StaticMesh SM_CH_Main_Normal<Gender>[000N]_Decoy in BrgGame.upk with three parts: the body (enemy skin
material), its hair, and the mushrooms growing on it. Writes <mesh>.pos/nrm/uv/idx.bin like extract.py, any textures
not already dumped (as DDS), and decoys.json.
"""
import os, sys, json, struct, sqlite3
from array import array
import upk, textool

OUT = sys.argv[1]
b = upk.Package('BrgGame.upk')
MICS = {i + 1: e['name'] for i, e in enumerate(b.exports) if b.clsname(e) == 'MaterialInstanceConstant' and e['name'].endswith('_Decoy')}


def dds(name):
    """Dump a texture as DDS unless it is already there; returns its file name."""
    fn = name + '.dds'
    if not os.path.exists(os.path.join(OUT, fn)):
        data, w, h, fmt = textool.raw_top_mip(b, b.find(name, 'Texture2D'))
        four = {'PF_DXT1': b'DXT1', 'PF_DXT5': b'DXT5'}[fmt]
        hdr = struct.pack('<4sIIIIIII44xII4s20xI16x', b'DDS ', 124, 0x81007, h, w, len(data), 0, 1, 32, 4, four, 0x1000)
        open(os.path.join(OUT, fn), 'wb').write(hdr + data)
    return fn


def read_static_mesh(name):
    e = b.find(name, 'StaticMesh'); b.ensure(e['off'], e['size'])
    d = bytes(b.data[e['off']:e['off'] + e['size']])
    # position buffer: stride 12, vertex count, then the raw array header (element size 12, same count)
    p = next(i for i in range(0, len(d) - 16) if struct.unpack_from('<4i', d, i)[::2] == (12, 12) and
             struct.unpack_from('<4i', d, i)[1] == struct.unpack_from('<4i', d, i)[3] and 100 < struct.unpack_from('<4i', d, i)[1] < 500000 and
             i + 16 + struct.unpack_from('<4i', d, i)[1] * 12 <= len(d))
    n = struct.unpack_from('<i', d, p + 4)[0]
    pos_raw = struct.unpack_from('<%df' % (n * 3), d, p + 16)
    q = p + 16 + n * 12
    ntc, stride, nv, full, es, cnt = struct.unpack_from('<6i', d, q); q += 24
    assert nv == n and es == stride and not full, (ntc, stride, nv, full)
    st = struct.Struct('<4x3Bx2e%dx' % (stride - 12))
    pos = array('f'); nrm = array('f'); uv = array('f')
    # UE static mesh space is Z-up and left-handed; swapping Y and Z gives right-handed Y-up
    for i, (nx, ny, nz, u, v) in enumerate(st.iter_unpack(d[q:q + es * cnt])):
        x, y, z = pos_raw[3 * i:3 * i + 3]
        pos.extend((x, z, y)); nrm.extend((nx / 127.5 - 1, nz / 127.5 - 1, ny / 127.5 - 1)); uv.extend((u, v))
    q += es * cnt
    cstride, cn = struct.unpack_from('<2i', d, q); q += 8
    if cn > 0:
        ces, cc = struct.unpack_from('<2i', d, q); q += 8 + ces * cc
    assert struct.unpack_from('<i', d, q)[0] == n; q += 4
    ies, icnt = struct.unpack_from('<2i', d, q); q += 8
    idx = array('I', struct.unpack_from('<%d%s' % (icnt, 'H' if ies == 2 else 'I'), d, q))
    groups = []
    for j in range(0, p - 36):
        ref = struct.unpack_from('<i', d, j)[0]
        if ref in MICS:
            _, _, _, _, first, ntri, vmin, vmax, mi = struct.unpack_from('<9i', d, j)
            if 0 <= first and first + ntri * 3 <= icnt and ntri > 0:
                groups.append(dict(mat=MICS[ref], start=first, count=ntri * 3))
    return dict(pos=pos, nrm=nrm, uv=uv, idx=idx, groups=groups)


db = os.path.abspath(os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
out = []
for bid, gender in c.execute('select id, gender from master_body order by id'):
    n = int(bid[-3:]); g = 'Female' if gender == 'GENDER_FEMALE' else 'Male'
    name = 'SM_CH_Main_Normal%s%s_Decoy' % (g, '' if n == 1 else '%04d' % n)
    m = read_static_mesh(name)
    for k in ('pos', 'nrm', 'uv', 'idx'):
        m[k].tofile(open(os.path.join(OUT, '%s.%s.bin' % (name, k)), 'wb'))
    groups = []
    for grp in m['groups']:
        t = upk.mic_params(b, grp['mat'])['tex']
        kind = 'hair' if 'Hair' in grp['mat'] else 'shroom' if 'Mushroom' in grp['mat'] else 'skin'
        tex = dict(D=dds(t['DiffuseMap']), N=dds(t['NormalMap']))
        if kind == 'hair': tex['M'] = dds(t['MaskMap'])
        groups.append(dict(start=grp['start'], count=grp['count'], kind=kind, mat=grp['mat'], tex=tex))
    xs, ys, zs = m['pos'][0::3], m['pos'][1::3], m['pos'][2::3]
    out.append(dict(id=bid, label='%s %d' % (g, n), name=name, verts=len(xs), groups=groups, min=[min(xs), min(ys), min(zs)], max=[max(xs), max(ys), max(zs)]))
    print(name, len(xs), 'verts', [(x['kind'], x['count'] // 3, x['mat']) for x in groups], [round(v) for v in out[-1]['min'] + out[-1]['max']])
json.dump(out, open(os.path.join(OUT, 'decoys.json'), 'w'), indent=1)

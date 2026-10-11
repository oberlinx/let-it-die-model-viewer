"""Dump LET IT DIE fighter body + hair meshes and textures for rendering."""
import os, sys, json, struct, sqlite3, io
from array import array
import upk, lzo

OUT = sys.argv[1]
MAXTEX = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
os.makedirs(OUT, exist_ok=True)
DB = os.path.join(upk.GAME, '..', 'Content', 'masters.db')
_pk = {}

def pkg(name):
    if name not in _pk: _pk[name] = upk.Package(name)
    return _pk[name]

def pkg_for(prefix):
    f = prefix + '_SF.upk'
    return [pkg(f)] if os.path.exists(os.path.join(upk.GAME, f)) else []

def find_export(name, cls, pkgs):
    for p in pkgs + [pkg('BrgGame.upk')]:
        e = p.find(name, cls)
        if e: return p, e
    return None, None

def read_mesh(p, e):
    r = p.reader(e); r.i32(); p.props(r)
    r.fs(7)
    mats = [p.objname(r.i32()) for _ in range(r.i32())]
    r.fs(3); r.p += 12
    bones = []
    for _ in range(r.i32()):
        name = p.fname(r); r.u32(); quat = r.fs(4); bpos = r.fs(3); r.i32(); parent = r.i32(); r.u32()
        bones.append([name, parent] + list(quat) + list(bpos))
    r.i32()
    assert r.i32() >= 1
    secs = []
    for _ in range(r.i32()):
        mi = r.u16(); ch = r.u16(); base = r.u32(); nt = r.u32(); r.u8()
        secs.append((mi, base, nt))
    r.u32(); r.u8(); es = r.i32(); n = r.i32()
    idx = array('H' if es == 2 else 'I', r.raw(es * n))
    n_ = r.i32(); r.p += 2 * n_
    chunks = []
    for _ in range(r.i32()):
        cbase = r.u32()
        assert r.i32() == 0 and r.i32() == 0, 'cpu verts present'
        bonemap = [r.u16() for _ in range(r.i32())]
        nrig = r.i32(); nsoft = r.i32(); r.i32()
        chunks.append((cbase, nrig + nsoft, bonemap))
    r.u32(); nv = r.u32()
    n_ = r.i32(); r.p += n_
    fl = r.u32(); cnt = r.i32(); size = r.u64(); off = r.u64()
    if not fl & 1: r.p += size
    r.u32()
    ntc = r.u32(); full = r.u32(); packed = r.u32(); ext = r.fs(3); org = r.fs(3)
    es = r.i32(); n = r.i32()
    assert n == nv, (n, nv)
    uvf = 'f' if full else 'e'
    st = struct.Struct('<4x3Bx4B4B3f' + '2' + uvf + '%dx' % ((ntc - 1) * (8 if full else 4)))
    assert st.size == es, (st.size, es, ntc, full, packed)
    pos = array('f'); nrm = array('f'); uv = array('f'); skin = bytearray()
    # each vertex's bone indices are local to its chunk: look them up in that chunk's bone map
    vmap = [None] * n
    for cbase, cnum, bonemap in chunks:
        for i in range(cbase, cbase + cnum): vmap[i] = bonemap
    vi = 0
    # UE3 (left-handed, up = -Y here) -> right-handed Y-up: negate Y (winding then already reads counter-clockwise)
    for nx, ny, nz, b0, b1, b2, b3, w0, w1, w2, w3, x, y, z, u, v in st.iter_unpack(r.raw(es * n)):
        pos.extend((x, -y, z)); nrm.extend((nx / 127.5 - 1, -(ny / 127.5 - 1), nz / 127.5 - 1)); uv.extend((u, v))
        bm = vmap[vi]; vi += 1
        skin.extend((bm[b0], bm[b1], bm[b2], bm[b3], w0, w1, w2, w3))
    tri = array('I', idx)
    groups = [dict(mat=mats[mi], start=int(base), count=int(nt) * 3) for mi, base, nt in secs]
    return dict(pos=pos, nrm=nrm, uv=uv, idx=tri, groups=groups, skin=skin, bones=bones)

_tfc = {}
def read_tex(p, e, max_size=2048):
    r = p.reader(e); r.i32(); pr = p.props(r)
    fl = r.u32(); r.i32(); size = r.u64(); r.u64()
    if not fl & 1: r.p += size
    fmt = pr['Format']
    best = None
    for _ in range(r.i32()):
        fl = r.u32(); cnt = r.i32(); size = r.u64(); off = r.u64()
        inline = None
        if not fl & 1 and not fl & 0x20:
            inline = r.raw(size)
        sx = r.i32(); sy = r.i32()
        if best is None and sx <= max_size and not fl & 0x20:
            best = (fl, cnt, size, off, inline, sx, sy)
    fl, cnt, size, off, data, sx, sy = best
    if fl & 1:
        name = pr.get('TextureFileCacheName', 'Textures')
        if name not in _tfc: _tfc[name] = open(os.path.join(upk.GAME, name + '.tfc'), 'rb')
        f = _tfc[name]; f.seek(off); data = f.read(size)
    if fl & 0x10:
        data, _ = lzo.read_chunk(data, 0)
    elif fl & 0x02:
        raise NotImplementedError('zlib bulk')
    assert len(data) == cnt, (len(data), cnt)
    four = {'PF_DXT1': b'DXT1', 'PF_DXT5': b'DXT5', 'PF_DXT3': b'DXT3', 'PF_BC5': b'ATI2'}[fmt]
    hdr = struct.pack('<4sIIIIIII44xII4s20xI16x', b'DDS ', 124, 0x81007, sy, sx, cnt, 0, 1, 32, 4, four, 0x1000)
    return hdr + data, (sx, sy), pr

done_tex = {}
def export_tex(name, pkgs):
    if name in done_tex: return done_tex[name]
    p, e = find_export(name, 'Texture2D', pkgs)
    if not e:
        print('  !! texture not found', name); done_tex[name] = None; return None
    dds, size, pr = read_tex(p, e, MAXTEX)
    fn = name + '.dds'
    open(os.path.join(OUT, fn), 'wb').write(dds)
    done_tex[name] = dict(file=fn, fmt=pr['Format'], size=size, srgb=pr.get('SRGB', True))
    print('  tex', name, pr['Format'], size)
    return done_tex[name]

def split_mask(m):
    """The gas mask is a loose piece of the skin section: move its triangles into a group of their own."""
    pos, idx = m['pos'], m['idx']
    nv = len(pos) // 3
    seen = {}
    par = [seen.setdefault((round(pos[3 * i], 2), round(pos[3 * i + 1], 2), round(pos[3 * i + 2], 2)), i) for i in range(nv)]
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    out = array('I'); groups = []
    for g in m['groups']:
        tris = idx[g['start']:g['start'] + g['count']]
        mask = array('I')
        if 'CutSurface' not in g['mat']:
            for t in range(0, len(tris), 3):
                a, b, c = find(tris[t]), find(tris[t + 1]), find(tris[t + 2])
                par[b] = a; par[find(c)] = a
            comp = {}
            for t in range(0, len(tris), 3):
                comp.setdefault(find(tris[t]), []).append(t)
            big = [ts for ts in comp.values() if len(ts) >= 1000 and min(pos[3 * tris[t] + 1] for t in ts) > 150]
            if big:
                assert len(big) == 1
                drop = set(big[0])
                keep = array('I')
                for t in range(0, len(tris), 3):
                    (mask if t in drop else keep).extend(tris[t:t + 3])
                tris = keep
        groups.append(dict(mat=g['mat'], start=len(out), count=len(tris))); out.extend(tris)
        if mask:
            groups.append(dict(mat=g['mat'], start=len(out), count=len(mask), part='mask')); out.extend(mask)
    m['idx'] = out; m['groups'] = groups

done_mesh = {}
def export_mesh(path):
    """path like CH_Main_NormalFemale0002.Meshes.SK_CH_Main_NormalFemale0002"""
    if path in done_mesh: return done_mesh[path]
    prefix, name = path.split('.')[0], path.split('.')[-1]
    pkgs = pkg_for(prefix)
    p, e = find_export(name, 'SkeletalMesh', pkgs)
    m = read_mesh(p, e)
    if 'CH_Main' in name: split_mask(m)
    print('mesh', name, 'verts', len(m['pos']) // 3, 'tris', len(m['idx']) // 3, 'from', os.path.basename(p.path))
    for k in ('pos', 'nrm', 'uv', 'idx'):
        m[k].tofile(open(os.path.join(OUT, '%s.%s.bin' % (name, k)), 'wb'))
    open(os.path.join(OUT, name + '.skin.bin'), 'wb').write(m['skin'])    # per vertex: 4 bone indices, 4 weights (0-255)
    xs = m['pos'][0::3]; ys = m['pos'][1::3]; zs = m['pos'][2::3]
    info = dict(name=name, verts=len(m['pos']) // 3, bones=m['bones'], groups=[], min=[min(xs), min(ys), min(zs)], max=[max(xs), max(ys), max(zs)])
    for g in m['groups']:
        mp, me = find_export(g['mat'], 'MaterialInstanceConstant', pkgs)
        mat = dict(name=g['mat'])
        if me:
            d = upk.mic_params(mp, g['mat'])
            mat.update(parent=d['parent'], vec=d['vec'], sca=d['sca'], tex={})
            for k, t in d['tex'].items():
                if t and 'Stiker' not in t:
                    mat['tex'][k] = export_tex(t, pkgs + [mp])
        g['material'] = mat
        info['groups'].append(g)
    done_mesh[path] = info
    return info

c = sqlite3.connect('file:%s?mode=ro' % os.path.abspath(DB).replace(os.sep, '/'), uri=True)
asset = dict(c.execute('select id, mesh from master_asset'))
models = []
for bid, baid, haid, gender in c.execute('select id, baid, haid, gender from master_body order by id'):
    n = int(bid[-3:])
    female = gender == 'GENDER_FEMALE'
    m = dict(id=bid, label='%s %d' % ('Female' if female else 'Male', n), gender='female' if female else 'male',
             body_asset=baid, hair_asset=haid or None, body=export_mesh(asset[baid]),
             hair=export_mesh(asset[haid]) if haid else None)
    models.append(m)
json.dump(models, open(os.path.join(OUT, 'models.json'), 'w'), indent=1)
print('done', len(models))

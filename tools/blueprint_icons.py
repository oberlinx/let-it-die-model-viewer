"""Dump the six blueprint icons (revealed RMAP_1..3, unrevealed UN_RMAP_1..3) raw into <out-dir>, adding them to images.json."""
import os, sys, json
import upk, lzo
OUT = sys.argv[1]
images = json.load(open(os.path.join(OUT, 'images.json')))
_tfc = {}
for name in ['RMAP_1', 'RMAP_2', 'RMAP_3', 'UN_RMAP_1', 'UN_RMAP_2', 'UN_RMAP_3']:
    p = upk.Package('UI_Icon_%s_SF.upk' % name)
    tex = [e for e in p.exports if p.clsname(e) == 'Texture2D']
    print(name, [e['name'] for e in tex])
    e = tex[0]
    r = p.reader(e); r.i32(); pr = p.props(r)
    fmt = {'PF_A8R8G8B8': 'bgra', 'PF_DXT5': 'dxt5'}[pr['Format']]
    fl = r.u32(); r.i32(); size = r.u64(); r.u64()
    if not fl & 1: r.p += size
    assert r.i32() >= 1
    fl = r.u32(); cnt = r.i32(); size = r.u64(); off = r.u64()
    if fl & 1:
        t = pr.get('TextureFileCacheName', 'Textures')
        if t not in _tfc: _tfc[t] = open(os.path.join(upk.GAME, t + '.tfc'), 'rb')
        _tfc[t].seek(off); data = _tfc[t].read(size)
    else:
        data = r.raw(size)
    if fl & 0x10: data, _ = lzo.read_chunk(data, 0)
    w = r.i32(); h = r.i32()
    open(os.path.join(OUT, name + '.' + fmt), 'wb').write(data)
    images[name] = dict(w=w, h=h, fmt=fmt); print(' ', w, h, fmt, len(data))
json.dump(images, open(os.path.join(OUT, 'images.json'), 'w'))

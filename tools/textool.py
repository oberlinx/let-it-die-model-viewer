"""Read any Texture2D's top mip as RGBA (A8R8G8B8, DXT1 or DXT5) and save it as PNG."""
import os, sys, struct
import upk, lzo, png

def raw_top_mip(p, e):
    r = p.reader(e); r.i32(); pr = p.props(r)
    fl = r.u32(); r.i32(); size = r.u64(); r.u64()
    if not fl & 1: r.p += size
    r.i32(); fl = r.u32(); cnt = r.i32(); size = r.u64(); off = r.u64()
    if fl & 1:
        f = open(os.path.join(upk.GAME, pr.get('TextureFileCacheName', 'Textures') + '.tfc'), 'rb'); f.seek(off); data = f.read(size)
    else: data = r.raw(size)
    if fl & 0x10: data, _ = lzo.read_chunk(data, 0)
    return bytes(data), r.i32(), r.i32(), pr['Format']

def dxt(data, w, h, five):
    out = bytearray(w * h * 4); p = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            al = None
            if five:
                a0, a1 = data[p], data[p + 1]; bits = int.from_bytes(data[p + 2:p + 8], 'little'); p += 8
                tab = [a0, a1] + ([((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)] if a0 > a1 else [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255])
                al = [tab[(bits >> (3 * k)) & 7] for k in range(16)]
            c0, c1, ib = struct.unpack_from('<HHI', data, p); p += 8
            def rgb(c): return ((c >> 11) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)
            a, b = rgb(c0), rgb(c1)
            if five or c0 > c1: cols = [a + (255,), b + (255,), tuple((2 * a[k] + b[k]) // 3 for k in range(3)) + (255,), tuple((a[k] + 2 * b[k]) // 3 for k in range(3)) + (255,)]
            else: cols = [a + (255,), b + (255,), tuple((a[k] + b[k]) // 2 for k in range(3)) + (255,), (0, 0, 0, 0)]
            for k in range(16):
                x, y = bx + k % 4, by + k // 4
                if x < w and y < h:
                    c = cols[(ib >> (2 * k)) & 3]; o = (y * w + x) * 4
                    out[o:o + 4] = bytes((c[0], c[1], c[2], al[k] if al else c[3]))
    return out

def rgba(pkg, name):
    p = upk.Package(pkg); e = p.find(name, 'Texture2D')
    data, w, h, fmt = raw_top_mip(p, e)
    if fmt == 'PF_A8R8G8B8': return png.bgra_to_rgba(data), w, h
    return dxt(data, w, h, fmt == 'PF_DXT5'), w, h

if __name__ == '__main__':
    px, w, h = rgba(sys.argv[1], sys.argv[2]); print(w, h)
    png.write_png(sys.argv[3], w, h, px)
    if len(sys.argv) > 4:                       # also write an opaque copy and the alpha channel alone
        o = bytearray(px); o[3::4] = b'\xff' * (w * h); png.write_png(sys.argv[3].replace('.png', '_rgb.png'), w, h, o)
        a = bytearray(px); a[0::4] = px[3::4]; a[1::4] = px[3::4]; a[2::4] = px[3::4]; a[3::4] = b'\xff' * (w * h); png.write_png(sys.argv[3].replace('.png', '_a.png'), w, h, a)

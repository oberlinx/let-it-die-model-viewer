"""Minimal reader for LET IT DIE (UE3 v861/19) cooked packages."""
import struct, os

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rawpkg")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\LET IT DIE\BrgGame\CookedPCConsole"


class R:
    def __init__(self, data, pos=0):
        self.d = data; self.p = pos
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2; return v
    def u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def u64(self):
        v = struct.unpack_from('<Q', self.d, self.p)[0]; self.p += 8; return v
    def f32(self):
        v = struct.unpack_from('<f', self.d, self.p)[0]; self.p += 4; return v
    def fs(self, n):
        v = struct.unpack_from('<%df' % n, self.d, self.p); self.p += 4 * n; return v
    def raw(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v
    def fstr(self):
        n = self.i32()
        if n == 0: return ''
        if n < 0:
            s = self.raw(-n * 2).decode('utf-16-le'); return s.rstrip('\0')
        return self.raw(n).decode('latin-1').rstrip('\0')


class Package:
    def __init__(self, name):
        path = name if os.path.isabs(name) else os.path.join(GAME, name)
        self.path = path
        with open(path, 'rb') as f:
            self.file = f.read()
        self._open()
        r = R(self.data)
        assert r.u32() == 0x9E2A83C1
        self.ver = r.u16(); self.lic = r.u16()
        self.header_size = r.i32()
        r.fstr()
        self.flags = r.u32()
        nc, no, ec, eo, ic, io = (r.i32() for _ in range(6))
        self.ensure(0, self.header_size)
        self.names = []
        r.p = no
        for _ in range(nc):
            self.names.append(r.fstr()); r.u64()
        self.imports = []
        r.p = io
        for _ in range(ic):
            cp = self.fname(r); cn = self.fname(r); outer = r.i32(); on = self.fname(r)
            self.imports.append(dict(cls=cn, outer=outer, name=on))
        self.exports = []
        r.p = eo
        for _ in range(ec):
            cls = r.i32(); sup = r.i32(); outer = r.i32(); on = self.fname(r)
            arch = r.i32(); of = r.u64(); size = r.i32(); off = r.i32()
            ef = r.u32(); n = r.i32(); r.p += 4 * n; r.p += 16; r.u32()
            self.exports.append(dict(cls=cls, outer=outer, name=on, size=size, off=off))

    def _open(self):
        d = self.file
        r = R(d); r.p = 12; r.fstr(); r.p += 4 + 4 * 11 + 16
        n = r.i32(); r.p += 12 * n + 8
        cflags = r.u32(); nch = r.i32()
        self.chunks = []
        if not nch:
            self.data = d; return
        assert cflags == 2, cflags
        self.chunks = [[r.i32(), r.i32(), r.i32(), r.i32(), False] for _ in range(nch)]
        last = self.chunks[-1]
        self.data = bytearray(last[0] + last[1])
        self.data[:self.chunks[0][0]] = d[:self.chunks[0][0]]

    def ensure(self, off, size):
        import lzo
        for c in self.chunks:
            uo, us, co, cs, done = c
            if done or uo + us <= off or uo >= off + size: continue
            b, _ = lzo.read_chunk(self.file, co)
            assert len(b) == us
            self.data[uo:uo + us] = b
            c[4] = True

    def fname(self, r):
        i = r.i32(); n = r.i32()
        s = self.names[i]
        return s if n == 0 else '%s_%d' % (s, n - 1)

    def objname(self, idx):
        if idx == 0: return None
        if idx > 0: return self.exports[idx - 1]['name']
        return self.imports[-idx - 1]['name']

    def clsname(self, e):
        return self.objname(e['cls']) or 'Class'

    def find(self, name, cls=None):
        for e in self.exports:
            if e['name'] == name and (cls is None or self.clsname(e) == cls):
                return e
        return None

    def reader(self, e):
        self.ensure(e['off'], e['size'])
        return R(self.data, e['off'])

    def props(self, r):
        """Read tagged properties; returns dict and leaves r after the None terminator."""
        out = {}
        while True:
            name = self.fname(r)
            if name == 'None': break
            typ = self.fname(r); size = r.i32(); idx = r.i32()
            start = r.p
            if typ == 'StructProperty':
                sn = self.fname(r); start = r.p
                val = ('struct', sn, r.d[start:start + size])
            elif typ == 'BoolProperty':
                val = bool(r.u8()); start = r.p; size = 0
            elif typ == 'ByteProperty':
                en = self.fname(r); start = r.p
                val = self.fname(R(r.d, start)) if size == 8 else r.d[start]
            elif typ == 'IntProperty': val = struct.unpack_from('<i', r.d, start)[0]
            elif typ == 'FloatProperty': val = struct.unpack_from('<f', r.d, start)[0]
            elif typ == 'NameProperty': val = self.fname(R(r.d, start))
            elif typ == 'ObjectProperty': val = ('obj', struct.unpack_from('<i', r.d, start)[0])
            elif typ == 'StrProperty': val = R(r.d, start).fstr()
            else: val = (typ, r.d[start:start + size])
            r.p = start + size
            out.setdefault(name, val) if idx == 0 else out.__setitem__('%s[%d]' % (name, idx), val)
        return out


def mic_params(p, name):
    """Texture / vector / scalar parameter values of a MaterialInstanceConstant."""
    import struct
    e = p.find(name, 'MaterialInstanceConstant')
    r = p.reader(e); r.i32(); pr = p.props(r)
    out = dict(parent=p.objname(pr['Parent'][1]) if 'Parent' in pr else None, tex={}, vec={}, sca={})
    for key, kind in (('TextureParameterValues', 'tex'), ('VectorParameterValues', 'vec'), ('ScalarParameterValues', 'sca')):
        if key not in pr: continue
        rr = upk_R(pr[key][1]); n = rr.i32()
        for _ in range(n):
            s = p.props(rr)
            v = s.get('ParameterValue')
            if kind == 'tex': v = p.objname(v[1]) if v else None
            elif kind == 'vec': v = struct.unpack('<4f', v[2]) if v else None
            out[kind][s.get('ParameterName')] = v
    return out

upk_R = R

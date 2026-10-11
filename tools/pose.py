"""Pose the meshes dumped by extract.py with one frame of a game animation.

Usage: pose.py <dump-dir> [sequence-name] [frame 0..1]
Writes <mesh>.pose.pos.bin / <mesh>.pose.nrm.bin next to the reference-pose files, and adds "head" (the posed
head bone position) to each model in models.json.

Animations here are AKF_VariableKeyLerp with ACF_Float96NoW rotations and uncompressed translations: per track,
CompressedTrackOffsets holds (translation offset, key count, rotation offset, key count) into the byte stream;
a track with several keys is followed by one time marker per key (uint8, or uint16 past 255 frames).
"""
import os, sys, json, math, struct
from array import array
import upk

D = sys.argv[1]
SEQ = sys.argv[2] if len(sys.argv) > 2 else 'ANI_CH_IDL_Neutral'
AT = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
ANIMS = {'female': ('AS_CH_Main_Female_Common_SF.upk', 'AS_CH_Main_Female_Type_SF.upk'),
         'male': ('AS_CH_Main_Male_Common_SF.upk', 'AS_CH_Main_Male_Type_SF.upk')}
ANIM_CONJ = True    # animation keys store non-root rotations conjugated relative to the reference skeleton
CONJ = False    # set True if bone rotations turn out to be stored conjugated (check_ref below tells which)


# --- quaternions as (x, y, z, w) ---
def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)

def qconj(q): return (-q[0], -q[1], -q[2], q[3])

def qrot(q, v):
    x, y, z, w = q; vx, vy, vz = v
    tx = 2 * (y * vz - z * vy); ty = 2 * (z * vx - x * vz); tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx)

def qmat(q):
    x, y, z, w = q
    return (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
            2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
            2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))

def qnlerp(a, b, t):
    if sum(a[i] * b[i] for i in range(4)) < 0: b = tuple(-c for c in b)
    q = tuple(a[i] + (b[i] - a[i]) * t for i in range(4)); n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def read_sequence(gender, name):
    """{bone name: (quat, translation or None)} at fraction AT of the sequence."""
    for f in ANIMS[gender]:
        p = upk.Package(f)
        for e in p.exports:
            if p.clsname(e) != 'AnimSequence': continue
            r = p.reader(e); r.i32(); pr = p.props(r)
            if str(pr.get('SequenceName')) != name: continue
            assert pr.get('KeyEncodingFormat') == 'AKF_VariableKeyLerp' and pr.get('RotationCompressionFormat') == 'ACF_Float96NoW'
            assert pr.get('TranslationCompressionFormat') in (None, 'ACF_None')
            o = pr['CompressedTrackOffsets'][1]; offs = struct.unpack_from('<%di' % struct.unpack_from('<i', o)[0], o, 4)
            assert r.i32() == 0                       # no raw animation data in cooked packages
            stream = r.raw(r.i32())
            aset = p.exports[e['outer'] - 1]; ar = p.reader(aset); ar.i32(); ap = p.props(ar)
            q = upk.R(ap['TrackBoneNames'][1]); tracks = [p.fname(q) for _ in range(q.i32())]
            use_t = set()
            if 'UseTranslationBoneNames' in ap:
                q = upk.R(ap['UseTranslationBoneNames'][1]); use_t = {p.fname(q) for _ in range(q.i32())}
            rot_only = ap.get('bAnimRotationOnly', True)
            frames = pr['NumFrames']; want = AT * (frames - 1)

            def keys(off, n, size):
                """Indices of the two keys around `want` and the blend between them."""
                if n == 1: return 0, 0, 0.0
                tbl = off + n * size
                times = struct.unpack_from('<%d%s' % (n, 'B' if frames <= 255 else 'H'), stream, tbl)
                hi = next((i for i, t in enumerate(times) if t >= want), n - 1); lo = max(hi - 1, 0)
                span = times[hi] - times[lo]
                return lo, hi, (want - times[lo]) / span if span else 0.0

            def quat_at(off, i):
                x, y, z = struct.unpack_from('<3f', stream, off + 12 * i)
                return (x, y, z, math.sqrt(max(0.0, 1 - x * x - y * y - z * z)))

            out = {}
            for i, bone in enumerate(tracks):
                to, tn, ro, rn = offs[4 * i:4 * i + 4]
                lo, hi, t = keys(ro, rn, 12)
                rot = qnlerp(quat_at(ro, lo), quat_at(ro, hi), t)
                lo, hi, t = keys(to, tn, 12)
                a = struct.unpack_from('<3f', stream, to + 12 * lo); b = struct.unpack_from('<3f', stream, to + 12 * hi)
                tr = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
                out[bone] = (rot, tr if (not rot_only or i == 0 or bone in use_t) else None)
            return out
    raise SystemExit('sequence %s not found for %s' % (name, gender))


def world(bones, local):
    """World (rotation, position) per bone from local ones; parents always come first."""
    w = []
    for i, b in enumerate(bones):
        q, t = local[i]
        if i and CONJ: q = qconj(q)
        if i == 0: w.append((q, t))
        else:
            pq, pt = w[b[1]]
            r = qrot(pq, t); w.append((qmul(pq, q), (pt[0] + r[0], pt[1] + r[1], pt[2] + r[2])))
    return w

def ref_local(bones): return [(tuple(b[2:6]), tuple(b[6:9])) for b in bones]

def load(name, kind, t):
    a = array(t); a.frombytes(open(os.path.join(D, '%s.%s.bin' % (name, kind)), 'rb').read()); return a

def check_ref(info):
    """Mean distance between each bone and the vertices it mostly controls: small only with the right convention."""
    pos = load(info['name'], 'pos', 'f'); skin = open(os.path.join(D, info['name'] + '.skin.bin'), 'rb').read()
    w = world(info['bones'], ref_local(info['bones'])); acc = {}
    for v in range(len(pos) // 3):
        for k in range(4):
            if skin[8 * v + 4 + k] > 200:
                a = acc.setdefault(skin[8 * v + k], [0, 0, 0, 0])
                a[0] += pos[3 * v]; a[1] += -pos[3 * v + 1]; a[2] += pos[3 * v + 2]; a[3] += 1
    d = [math.dist((a[0] / a[3], a[1] / a[3], a[2] / a[3]), w[b][1]) for b, a in acc.items()]
    return sum(d) / len(d)

def pose_mesh(info, anim_world_by_name, body_anim=None):
    """Skin one mesh. Bones missing from the animation (hair) keep their reference offset from their parent."""
    bones = info['bones']; name = info['name']
    refw = world(bones, ref_local(bones))
    local = []
    for b in bones:
        q, t = tuple(b[2:6]), tuple(b[6:9])
        if body_anim and b[0] in body_anim:
            aq, at = body_anim[b[0]]; q = qconj(aq) if (ANIM_CONJ and b[1] != bones.index(b)) else aq; t = at if at is not None else t
        local.append((q, t))
    animw = world(bones, local)
    mats = []
    for (rq, rp), (aq, ap) in zip(refw, animw):
        q = qmul(aq, qconj(rq)); o = qrot(q, rp)
        mats.append(qmat(q) + (ap[0] - o[0], ap[1] - o[1], ap[2] - o[2]))
    pos = load(name, 'pos', 'f'); nrm = load(name, 'nrm', 'f'); skin = open(os.path.join(D, name + '.skin.bin'), 'rb').read()
    op = array('f'); on = array('f')
    for v in range(len(pos) // 3):
        x, y, z = pos[3 * v], -pos[3 * v + 1], pos[3 * v + 2]; nx, ny, nz = nrm[3 * v], -nrm[3 * v + 1], nrm[3 * v + 2]
        px = py = pz = qx = qy = qz = 0.0; tw = 0
        for k in range(4):
            wt = skin[8 * v + 4 + k]
            if not wt: continue
            m = mats[skin[8 * v + k]]; tw += wt
            px += wt * (m[0] * x + m[1] * y + m[2] * z + m[9]); py += wt * (m[3] * x + m[4] * y + m[5] * z + m[10]); pz += wt * (m[6] * x + m[7] * y + m[8] * z + m[11])
            qx += wt * (m[0] * nx + m[1] * ny + m[2] * nz); qy += wt * (m[3] * nx + m[4] * ny + m[5] * nz); qz += wt * (m[6] * nx + m[7] * ny + m[8] * nz)
        n = math.sqrt(qx * qx + qy * qy + qz * qz) or 1.0
        op.extend((px / tw, -py / tw, pz / tw)); on.extend((qx / n, -qy / n, qz / n))
    op.tofile(open(os.path.join(D, name + '.pose.pos.bin'), 'wb')); on.tofile(open(os.path.join(D, name + '.pose.nrm.bin'), 'wb'))
    return {b[0]: animw[i] for i, b in enumerate(bones)}, op


if __name__ == '__main__':
    models = json.load(open(os.path.join(D, 'models.json')))
    for conj in (False, True):
        CONJ = conj; print('convention check, conjugate =', conj, '-> mean bone/vertex distance', round(check_ref(models[0]['body']), 2))
    CONJ = False
    anims = {}
    for m in models:
        g = m['gender']
        if g not in anims: anims[g] = read_sequence(g, SEQ)
        bw, op = pose_mesh(m['body'], None, anims[g])
        if m['hair']: pose_mesh(m['hair'], None, anims[g])
        h = bw['HeadJT'][1]; ys = op[1::3]
        m['pose'] = dict(sequence=SEQ, head=[h[0], -h[1], h[2]], min=[min(op[0::3]), min(ys), min(op[2::3])], max=[max(op[0::3]), max(ys), max(op[2::3])])
        print(m['label'], 'head', [round(c, 1) for c in m['pose']['head']], 'x', round(m['pose']['min'][0]), round(m['pose']['max'][0]), 'y', round(min(ys)), round(max(ys)))
    json.dump(models, open(os.path.join(D, 'models.json'), 'w'), indent=1)

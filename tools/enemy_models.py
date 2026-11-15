"""Dump, pose and pack the meshes of the enemies that have their own page (the Jackals, the Dons and the mini bosses).

Usage: enemy_models.py <set> <dump-dir>
       enemy_models.py <set> <dump-dir> --pack <shots-dir> <model3d-dir> <js-file>
<set> is 'jackals', 'bosses' or 'forcemen'.

The first form writes each mesh with extract.py's functions, poses it with pose.py's using one frame of its own idle
animation, and writes <set>.json (same shape as models.json, one entry per mesh) into the dump directory. Serve the dump
with serve.py, open render.html?set=<set> and run renderSet() and bakeSetTextures(1024). The second form then packs each
posed mesh into <model3d-dir>/<name>.bin (pack3d.py's layout; indices are uint32 instead of uint16 when the mesh has
65,536 vertices or more, flagged "i32"), copies the baked textures there once each (sections that share identical
images point at one copy), and writes the layout to <js-file> as window.<SET>3D.

Jackals: whole-character meshes (body, armour and hair in one mesh): CH_Enemy_JackalsX/Y/Z for the standard and R tiers,
and the 002 versions for the red-and-black D tier, posed with the fighters' neutral idle (same skeleton; Z uses the
female set). Dons: CH_Boss_No01-04 (Max Sharp, Colonel Jackson, Mr. Crowley, Taro Gunkanyama). Mini bosses:
CH_MidBoss_No01-04 (COEN, JIN-DIE, GOTO-9, U-10) and their Mk-2 versions (the _Boss packages). Each boss is posed with
the neutral idle from its own animation set.
"""
import os, sys, json, hashlib
from array import array

SET, D = sys.argv[1], sys.argv[2]
FIGHTER = {'male': ('AS_CH_Main_Male_Common_SF.upk', 'AS_CH_Main_Male_Type_SF.upk'), 'female': ('AS_CH_Main_Female_Common_SF.upk', 'AS_CH_Main_Female_Type_SF.upk')}
BOSS = lambda n: ('AS_CH_Boss_No0%d_SF.upk' % n,)
MID = lambda n: ('AS_CH_MidBoss_No0%d_SF.upk' % n,)
SETS = {   # id: (label, package prefix, mesh, animation packages, idle sequence)
    'jackals': [('JACKAL_' + m, 'Jackal %s%s' % (m[0], ' (D)' if m.endswith('002') else ''), 'CH_Enemy_Jackals' + m, 'SK_CH_Enemy_Jackals' + m,
                 FIGHTER['female' if m.startswith('Z') else 'male'], 'ANI_CH_IDL_Neutral') for m in ('X', 'Y', 'Z', 'X002', 'Y002', 'Z002')],
    'bosses': [
        ('DON_MAX', 'Max Sharp', 'CH_Boss_No01', 'SK_CH_Boss_No01', BOSS(1), 'ANI_CH_IDL_Neutral_01'),
        ('DON_JACKSON', 'Colonel Jackson', 'CH_Boss_No02', 'SK_CH_Boss_No02', BOSS(2), 'ANI_CH_IDL_Neutral'),
        ('DON_CROWLEY', 'Mr. Crowley', 'CH_Boss_No03', 'SK_CH_Boss_No03', BOSS(3), 'ANI_CH_IDL_Neutral_02'),
        ('DON_GUNKANYAMA', 'Taro Gunkanyama', 'CH_Boss_No04', 'SK_CH_Boss_No04', BOSS(4), 'ANI_CH_IDL_Neutral'),
        ('MBOSS1', 'COEN', 'CH_MidBoss_No01', 'SK_CH_MidBoss_No01', MID(1), 'ANI_CH_IDL_Neutral_01'),
        ('MBOSS2', 'JIN-DIE', 'CH_MidBoss_No02', 'SK_CH_MidBoss_No02', MID(2), 'ANI_CH_IDL_Neutral_01'),
        ('MBOSS3', 'GOTO-9', 'CH_MidBoss_No03', 'SK_CH_MidBoss_No03', MID(3), 'ANI_CH_IDL_Neutral_01'),
        ('MBOSS4', 'U-10', 'CH_MidBoss_No04', 'SK_CH_MidBoss_No04', MID(4), 'ANI_CH_IDL_Neutral_01'),
        ('STAGE_BOSS1', 'COEN Mk-2', 'CH_MidBoss_No01_Boss', 'SK_CH_MidBoss_No01_Boss', MID(1), 'ANI_CH_IDL_Neutral_01'),
        ('STAGE_BOSS2', 'JIN-DIE Mk-2', 'CH_MidBoss_No02_Boss', 'SK_CH_MidBoss_No02_MiddBoss', MID(2), 'ANI_CH_IDL_Neutral_01'),
        ('STAGE_BOSS3', 'GOTO-9 Mk-2', 'CH_MidBoss_No03_Boss', 'SK_CH_MidBoss_No03_Boss', MID(3), 'ANI_CH_IDL_Neutral_01'),
        ('STAGE_BOSS4', 'U-10 Mk-2', 'CH_MidBoss_No04_Boss', 'SK_CH_MidBoss_No04_Boss01', MID(4), 'ANI_CH_IDL_Neutral_01'),
    ],
    # The 4 FORCEMEN have no character mesh of their own: each is a fighter wearing its armour set. Shown here on the
    # Male 1 body with the set (021) or its Hell version (022), posed with the fighters' neutral idle. <prefix> is then
    # the name of the merged mesh, and <mesh> the list of parts.
    'forcemen': [(fid + sfx, label + tag, 'FFM_%s%s' % (fid[4:], sfx), [('CH_Main_NormalMale', 'SK_CH_Main_NormalMale')] +
                  [('CH_Equip_NM_%s_%s%s' % (s, part, num), 'SK_CH_Equip_NM_%s_%s%s' % (s, part, num)) for part in ('Btm0', 'Tops0', 'Head0')],
                  FIGHTER['male'], 'ANI_CH_IDL_Neutral')
                 for fid, label, s in (('FFM_WHITESTEEL', 'White Steel', 'DIY'), ('FFM_REDNAPALM', 'Red Napalm', 'MIL'),
                                       ('FFM_BLACKTHUNDER', 'Black Thunder', 'FAN'), ('FFM_PALEWIND', 'Pale Wind', 'SPO'))
                 for sfx, tag, num in (('', '', '021'), ('_HELL', ' (Hell)', '121'))],
}

if sys.argv[3:4] == ['--pack']:
    SHOTS, OUT, JS = sys.argv[4:7]
    os.makedirs(OUT, exist_ok=True)
    def load(name, kind, t):
        a = array(t); a.frombytes(open(os.path.join(D, '%s.%s.bin' % (name, kind)), 'rb').read()); return a
    seen = {}      # image hash -> texture name already copied

    def tex(name):
        """Copy model3d_<name>.webp into OUT under the first name with identical bytes; return that name."""
        data = open(os.path.join(SHOTS, 'model3d_%s.webp' % name), 'rb').read()
        h = hashlib.sha1(data).hexdigest()
        if h not in seen:
            seen[h] = name; open(os.path.join(OUT, name + '.webp'), 'wb').write(data)
        return seen[h]
    out = {}
    for m in json.load(open(os.path.join(D, SET + '.json'))):
        b = m['body']; name = b['name']
        pos, nrm, uv, idx = load(name, 'pose.pos', 'f'), load(name, 'pose.nrm', 'f'), load(name, 'uv', 'f'), load(name, 'idx', 'I')
        nv = len(pos) // 3; wide = nv >= 65536
        n8 = array('b')
        for i in range(nv):
            n8.extend(max(-127, min(127, round(nrm[3 * i + k] * 127))) for k in range(3)); n8.append(0)
        groups = []; tris = array('I' if wide else 'H')
        for g in b['groups']:
            mat = g['material']
            if 'CutSurface' in mat['name']: continue        # hidden caps used when a limb is cut off
            tn = mat['name'][3:] if mat['name'].startswith('MI_') else mat['name']
            gi = dict(start=len(tris), count=g['count'])
            if mat['name'].endswith('_Glass'): gi['kind'] = 'glass'
            else:
                gi.update(d=tex(tn + '_D'), n=tex(tn + '_N'))
                if '_Hair' in (mat.get('parent') or ''): gi.update(kind='hair', a=tex(tn + '_A'))
            groups.append(gi); tris.extend(array(tris.typecode, idx[g['start']:g['start'] + g['count']]))
        with open(os.path.join(OUT, name + '.bin'), 'wb') as f:
            for a in (pos, n8, uv, tris): a.tofile(f)
        p = m['pose']
        out[m['id']] = dict(name=name, verts=nv, indices=len(tris), groups=groups, top=p['max'][1], min=p['min'], max=p['max'],
                            centre=[(p['min'][0] + p['max'][0]) / 2, (p['min'][2] + p['max'][2]) / 2], **({'i32': 1} if wide else {}))
    open(JS, 'w', newline='\n').write('// Generated by tools/enemy_models.py --pack: mesh layout for the 3D view (pack3d.py\'s .bin format, uint32 indices\n'
                                      '// where "i32" is set; each section names its colour (d), normal (n) and, for hair, opacity (a) images in model3d/).\n'
                                      'window.%s3D = ' % SET.upper() + json.dumps(out, separators=(',', ':')).replace('},"', '},\n"') + ';\n')
    print(len(out), 'meshes,', len(seen), 'textures')
    sys.exit()

sys.argv = [sys.argv[0], D]        # extract.py and pose.py read the dump directory from argv[1]
import extract, pose
pose.D = D
def load(name, kind, t):
    a = array(t); a.frombytes(open(os.path.join(D, '%s.%s.bin' % (name, kind)), 'rb').read()); return a

def composite(name, parts, anim):
    """Pose several meshes that share a skeleton (a fighter body and the armour worn over it) and write them as one
    mesh <name>, in the same files extract.py and pose.py write. The body's gas mask is left out (the helmet covers it)."""
    infos = [extract.export_mesh('%s.Meshes.%s' % p) for p in parts]
    bw = None
    arrs = {k: array('f') for k in ('pos', 'nrm', 'uv', 'pose.pos', 'pose.nrm')}; idx = array('I'); groups = []
    for info in infos:
        w, _ = pose.pose_mesh(info, None, anim); bw = bw or w
        base = len(arrs['pos']) // 3
        for k in arrs: arrs[k].extend(load(info['name'], k, 'f'))
        src = load(info['name'], 'idx', 'I')
        for g in info['groups']:
            if g.get('part') == 'mask': continue
            groups.append(dict(g, start=len(idx)))
            idx.extend(array('I', (i + base for i in src[g['start']:g['start'] + g['count']])))
    for k, a in arrs.items(): a.tofile(open(os.path.join(D, '%s.%s.bin' % (name, k)), 'wb'))
    idx.tofile(open(os.path.join(D, name + '.idx.bin'), 'wb'))
    p = arrs['pose.pos']
    return dict(name=name, verts=len(p) // 3, bones=infos[0]['bones'], groups=groups), bw, p

anims = {}
models = []
for mid, label, prefix, mesh, packs, seq in SETS[SET]:
    key = (packs, seq)
    if key not in anims:
        pose.ANIMS[packs] = packs
        anims[key] = pose.read_sequence(packs, seq)
    if isinstance(mesh, list):
        body, bw, op = composite(prefix, mesh, anims[key])
    else:
        body = extract.export_mesh('%s.Meshes.%s' % (prefix, mesh))
        bw, op = pose.pose_mesh(body, None, anims[key])
    names = {b[0] for b in body['bones']}
    print(label, 'bones animated', len(names & set(anims[key])), 'of', len(names))
    h = bw.get('HeadJT') or bw.get('headJT'); ys = op[1::3]
    models.append(dict(id=mid, label=label, body=body, hair=None,
                       pose=dict(sequence=seq, head=[h[1][0], -h[1][1], h[1][2]] if h else None,
                                 min=[min(op[0::3]), min(ys), min(op[2::3])], max=[max(op[0::3]), max(ys), max(op[2::3])])))
    print('   size', [round(models[-1]['pose']['max'][k] - models[-1]['pose']['min'][k]) for k in range(3)])
json.dump(models, open(os.path.join(D, SET + '.json'), 'w'), indent=1)
print('done', len(models))

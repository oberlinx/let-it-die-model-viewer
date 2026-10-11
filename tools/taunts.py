"""Dump the sound timeline of each LET IT DIE taunt animation, and the voice / effect clips it needs.

The taunts are AnimSequences named ANI_CH_EVE_Provoke_NN. Each carries notifies: BrgAnimNotify_Voice
(one voice cue per fighter voice set) and AnimNotify_Sound (a plain sound effect). Output:
  taunts.json                       timelines, and how many variants of each clip were written
  <pack>_<en|jp>_<cue>_<n>.ogg      voice clips, e.g. F03_en_Avoid_1.ogg
  sfx_<name>_<n>.ogg                sound effects
"""
import os, sys, re, json
import upk

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
VARIANTS = 2          # clips kept per cue (the game picks one at random from more)
ANIMS = 'AS_CH_Main_Male_Common_SF.upk'   # female fighters use the same taunt animations


def ogg(p, e):
    r = p.reader(e); r.i32(); p.props(r)
    for _ in range(2):
        fl = r.u32(); r.i32(); size = r.u64(); r.u64()
        assert not fl & 1
        data = r.raw(size)
    assert bytes(data[:4]) == b'OggS', e['name']
    return bytes(data)


def cue_waves(p, e, seen=None):
    """Names/exports of the SoundNodeWaves reachable from a SoundCue or sound node export."""
    seen = seen if seen is not None else set()
    r = p.reader(e); r.i32(); pr = p.props(r)
    refs = []
    if 'FirstNode' in pr: refs.append(pr['FirstNode'][1])
    ch = pr.get('ChildNodes')
    if isinstance(ch, tuple):
        q = upk.R(ch[1]); refs += [q.i32() for _ in range(q.i32())]
    out = []
    for ref in refs:
        if ref == 0 or ref in seen: continue
        seen.add(ref)
        if ref < 0:
            imp = p.imports[-ref - 1]
            if imp['cls'] == 'SoundNodeWave': out.append(('import', imp['name']))
        else:
            x = p.exports[ref - 1]
            if p.clsname(x) == 'SoundNodeWave': out.append(('export', x))
            else: out += cue_waves(p, x, seen)
    return out


a = upk.Package(ANIMS)
taunts = {}; voice_cues = set(); sfx_cues = {}
for e in a.exports:
    if a.clsname(e) != 'AnimSequence': continue
    r = a.reader(e); r.i32(); pr = a.props(r)
    m = re.fullmatch(r'ANI_CH_EVE_Provoke_(\d\d)', str(pr.get('SequenceName')))
    if not m or int(m.group(1)) > 24: continue
    events = []
    nt = pr.get('Notifies')
    if isinstance(nt, tuple):
        q = upk.R(nt[1])
        for _ in range(q.i32()):
            s = a.props(q); o = s.get('Notify')
            if not (isinstance(o, tuple) and o[0] == 'obj' and o[1] > 0): continue
            x = a.exports[o[1] - 1]; rr = a.reader(x); rr.i32(); pp = a.props(rr)
            t = round(s.get('Time', 0.0), 2)
            if a.clsname(x) == 'BrgAnimNotify_Voice':
                cue = re.fullmatch(r'SN_VOX_CH_M01_(\w+)_cue', a.objname(pp['mSECue_Male01'][1])).group(1)
                events.append(dict(t=t, cue=cue)); voice_cues.add(cue)
            elif a.clsname(x) == 'AnimNotify_Sound':
                ref = pp['SoundCue'][1]; name = a.objname(ref)
                short = re.sub(r'^SN_SE_CH_Main_', '', name)
                events.append(dict(t=t, sfx=short)); sfx_cues[short] = ref
    n = int(m.group(1))
    if n not in taunts or len(events) > len(taunts[n]['events']):
        taunts[n] = dict(seconds=round(pr.get('SequenceLength', 0.0), 2), events=sorted(events, key=lambda v: v['t']))

def outer_package(p, ref):
    """Name of the top-level package an import lives in."""
    imp = p.imports[-ref - 1]
    while imp['outer'] < 0: imp = p.imports[-imp['outer'] - 1]
    return imp['name']

def find_export(name, cls, pkg_name):
    """Look for an export in <pkg>_SF.upk, <pkg>.upk, then the main BrgGame.upk."""
    for f in (pkg_name + '_SF.upk', pkg_name + '.upk', 'BrgGame.upk'):
        if os.path.exists(os.path.join(upk.GAME, f)):
            p = upk.Package(f); e = p.find(name, cls)
            if e: return p, e
    return None, None

sfx = {}
for short, ref in sfx_cues.items():
    p, e = (a, a.exports[ref - 1]) if ref > 0 else find_export(a.objname(ref), 'SoundCue', outer_package(a, ref))
    assert e, 'sfx cue %s not found' % short
    n = 0
    for kind, w in cue_waves(p, e):
        if n >= VARIANTS: break
        wp, we = (p, w) if kind == 'export' else find_export(w, 'SoundNodeWave', os.path.basename(p.path)[:-4].replace('_SF', ''))
        if not we: continue
        n += 1
        open(os.path.join(OUT, 'sfx_%s_%d.ogg' % (short, n)), 'wb').write(ogg(wp, we))
    assert n, 'no waves for sfx ' + short
    sfx[short] = n

clips = {}; total = 0
for g in 'FM':
    for n in range(1, 9):
        pack = '%s%02d' % (g, n)
        need = {ev['cue'] for k in (3 * n - 2, 3 * n - 1, 3 * n) for ev in taunts[k]['events'] if 'cue' in ev}
        cp = upk.Package('SN_VOX_CH_%s_cue_SF.upk' % pack)
        clips[pack] = {}
        for cue in sorted(need):
            ce = cp.find('SN_VOX_CH_%s_%s_cue' % (pack, cue), 'SoundCue')
            names = [w for kind, w in cue_waves(cp, ce) if kind == 'import'][:VARIANTS]
            assert names, (pack, cue)
            clips[pack][cue] = len(names)
            for lang, loc in (('en', 'INT'), ('jp', 'JPN')):
                wp = upk.Package('SN_VOX_CH_%s_cue_SF_LOC_%s.upk' % (pack, loc))
                for i, wn in enumerate(names, 1):
                    d = ogg(wp, wp.find(wn, 'SoundNodeWave')); total += len(d)
                    open(os.path.join(OUT, '%s_%s_%s_%d.ogg' % (pack, lang, cue, i)), 'wb').write(d)

json.dump(dict(taunts={str(k): taunts[k] for k in sorted(taunts)}, clips=clips, sfx=sfx), open(os.path.join(OUT, 'taunts.json'), 'w'), indent=1)
print(len(taunts), 'taunts; voice cues', sorted(voice_cues), '; sfx', sfx, ';', total // 1024, 'KB voice')
for k in sorted(taunts): print(k, taunts[k]['seconds'], [(v['t'], v.get('cue') or 'sfx:' + v['sfx']) for v in taunts[k]['events']])

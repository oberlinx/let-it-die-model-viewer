"""Dump a few sample voice clips (Ogg Vorbis, as stored by the game) for each LET IT DIE fighter model."""
import os, sys, re, json, sqlite3
import upk

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
CLIPS = [('attack', 'Attack_A'), ('hurt', 'Damage_A'), ('rage', 'Angry_LV1'), ('alert', 'Found_A'), ('death', 'Death_F_A')]
DB = os.path.abspath(os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)

def ogg(p, e):
    """CompressedPCData of a SoundNodeWave: the second bulk-data block after the properties."""
    r = p.reader(e); r.i32(); p.props(r)
    for i in range(2):
        fl = r.u32(); r.i32(); size = r.u64(); r.u64()
        assert not fl & 1
        data = r.raw(size)
    assert bytes(data[:4]) == b'OggS', e['name']
    return bytes(data)

info = {}; total = 0
for bid, gender, voicep, voiceb, provoke in c.execute('select id, gender, voicep, voiceb, provoke from master_body order by id'):
    pack = '%s%02d' % ('M' if gender == 'GENDER_MALE' else 'F', voicep)
    info[bid] = dict(voice=pack, voiceb=voiceb, provoke=provoke, clips={})
    for lang, loc in (('en', 'INT'), ('jp', 'JPN')):
        p = upk.Package('SN_VOX_CH_%s_cue_SF_LOC_%s.upk' % (pack, loc))
        waves = sorted((e for e in p.exports if p.clsname(e) == 'SoundNodeWave'), key=lambda e: e['name'])
        info[bid]['waves_' + lang] = len(waves)
        for key, pat in CLIPS:
            e = next(e for e in waves if re.search(r'_%s_\d+$' % pat, e['name']))
            d = ogg(p, e); total += len(d)
            open(os.path.join(OUT, '%s_%s_%s.ogg' % (bid, lang, key)), 'wb').write(d)
            info[bid]['clips'].setdefault(lang, []).append(key)
json.dump(info, open(os.path.join(OUT, 'voices.json'), 'w'), indent=1)
print(len(info), 'models,', total // 1024, 'KB of clips')

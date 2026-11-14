"""Write data/jackals.js: the three Jackals and their tiers, from the game's masters.db.

Usage (from the site's root folder): jackals.py
LID_MASTERS can point at an unmodded copy of the database, as for items.py.

Sources:
  master_jackal                         one row per tier: level, EXP, Kill Coins, weapon and armour, drops (per 1000)
  master_jackal_bodylvl_status_value    HP and stats for each level a tier names
  master_jackal_param_int               per-tier tuning for the D tiers: damage taken per attack, HUD level, mushrooms thrown
  master_const_int JACKAL_<X|Y|Z>_*     damage taken per attack for the standard tiers (stored with the Jackal's number,
                                        1 to 3, added to the last digit; it is taken off here), JACKAL_* for all Jackals
  master_credit                         voice cast; master_text the names and the mails that talk about the Jackals
"""
import os, re, json, sqlite3
import upk

DB = os.path.abspath(os.environ.get('LID_MASTERS') or os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()
TEXT = {(s, i): t for s, i, t in q("select sct, id, txt from master_text where lang='int' and snd=''")}
def txt(ref): return TEXT.get(tuple(ref.split('.', 1)), ref) if ref else ''
PART = {i: txt(n) for i, n in q('select id, name from master_part')}
ITEM = {i: (n, r) for i, n, r in q('select itemid, name, rarity from master_item')}
def item_name(i):
    if i.startswith('ITMP_'): return PART.get('PT_' + i[5:], i) + ' Blueprint'
    return txt(ITEM[i][0]) if i in ITEM else i

# Damage-taken keys, as the game names them, with a readable label. Other param keys (lock times, poison, HUD level,
# mushroom throws) are handled separately or left out.
DMG = {'NORMAL_ATK': 'Normal attacks', 'SLASH_DAMAGA': 'Slash damage', 'STRIKE_DAMAGA': 'Strike damage', 'SHOT_DAMAGA': 'Shot damage',
       'PROJECTILE': 'Projectiles', 'PROJECTILE_EXPLOSION': 'Projectile explosions',
       'ARCWELDING': 'Arc welder', 'ASSAULTRIFLE': 'Assault rifle', 'BEAMGUN': 'Beam gun', 'BEAMMACHETE': 'Beam machete',
       'BEAMMACHETE_RAGE': 'Beam machete (Killer Move)', 'BEAMSWORD': 'Beam sword', 'BEAMYOYO': 'Beam yo-yo', 'BIKE_RAGE': 'Bike (Killer Move)',
       'BLACKTHUNDERSWOED': 'Black thunder sword', 'BOBSLED': 'Bobsled', 'BOBSLED_PROJECTILE': 'Bobsled projectile', 'BOBSLED_PROJECTILE_DANAGE': 'Bobsled projectile',
       'BOWLING': 'Bowling ball', 'BOWLING_RAGE': 'Bowling ball (Killer Move)', 'BUTTERFLYKNIFE': 'Butterfly knife', 'DRILL': 'Drill',
       'DRILL_RAGE': 'Drill (Killer Move)', 'FIREROD': 'Fire rod', 'FIREWORKS': 'Fireworks', 'FIREWORKS_RAGE': 'Fireworks (Killer Move)',
       'FLAMERAD': 'Flame radiator', 'ICEHOCKEY': 'Ice hockey stick', 'KATANA': 'Katana', 'MEDUSA': 'Head of Medusa', 'MORNINSTAR': 'Morning star',
       'MUSH_CLOAK': 'Mushroom: cloak', 'MUSH_CONFUSION': 'Mushroom: confusion', 'MUSH_DRAIN': 'Mushroom: drain', 'MUSH_INVINCIBLE': 'Mushroom: invincible',
       'MUSH_SLOW': 'Mushroom: slow', 'PECKER': 'Pecker', 'PECKER_RAGE': 'Pecker (Killer Move)', 'PITCHINGMACHINE': 'Pitching machine',
       'REDNAPALMGUN': 'Red napalm gun', 'REVOLVER': 'Revolver', 'REVOLVER_RAGE': 'Revolver (Killer Move)', 'SABRE': 'Sabre',
       'SNIPERRIFLE_RAGE': 'Sniper rifle (Killer Move)', 'SPEAR': 'Spear', 'SPEAR_RAGE': 'Spear (Killer Move)', 'SQUARETIMBER': 'Square timber',
       'THUNDERROD': 'Thunder rod', 'WHITESTEELCLAW': 'White steel claw', 'WHITESTEELHAMMER': 'White steel hammer', 'YOYO_RAGE': 'Yo-yo (Killer Move)'}
FIRST = ['NORMAL_ATK', 'SLASH_DAMAGA', 'STRIKE_DAMAGA', 'SHOT_DAMAGA', 'PROJECTILE', 'PROJECTILE_EXPLOSION']   # listed before the weapons
def dmg_key(name):
    m = re.fullmatch(r'(.+?)_(?:DAMAGE|DANAGE)_RATE|(.+_DAMAGA)_RATE', name)
    if not m: return None
    k = m.group(1) or m.group(2)
    if k == 'BOBSLED_PROJECTILE_DANAGE': k = 'BOBSLED_PROJECTILE'
    return k if k in DMG else None

const = dict(q('select id, value from master_const_int'))
common = {}
for k, v in const.items():
    m = re.fullmatch(r'JACKAL_(.+)', k)
    if m and dmg_key(m.group(1)): common[dmg_key(m.group(1))] = v / 10
family_dmg = {f: dict(common) for f in 'XYZ'}
for k, v in const.items():
    m = re.fullmatch(r'JACKAL_([XYZ])_(.+)', k)
    if m and dmg_key(m.group(2)):
        n = 'XYZ'.index(m.group(1)) + 1
        family_dmg[m.group(1)][dmg_key(m.group(2))] = (v - n) / 10
params = {}
for t, n, v in q('select type, name, value from master_jackal_param_int'): params.setdefault(t, {})[n] = v
stat = {lvl: dict(hp=hp, str=s, dex=d, vit=vi, stm=st, stmrecov=sr, luk=lu)
        for lvl, hp, s, d, vi, st, sr, lu in q('select lvl, hp, str, dex, vit, stm, stmrecov, luk from master_jackal_bodylvl_status_value')}
msr_name = {i: txt(n) for i, n in q('select id, c_name from master_mushroom')}

cols = [r[1] for r in c.execute('pragma table_info(master_jackal)')]
fams = {}
for row in q('select * from master_jackal'):
    j = dict(zip(cols, row)); f = j['type'][len('JACKAL_')]
    armor = [j['head'], j['body'], j['legs']]
    d_look = j['head'].split('_')[-1].startswith('2')
    drops = []
    def add(kind, ident, per):
        if per > 0: drops.append(dict(kind=kind, id=ident, name=item_name(ident) if kind != 'coins' else 'Kill Coins', pct=round(per / 10, 2)))
    add('coins', '', j['drop_coin_rate'])
    add('part', j['armr'], j['drop_part_weapon_rate'])
    for a in armor: add('part', a, j['drop_part_armor_rate'] / 3)
    add('item', 'ITMP_' + j['armr'][3:], j['drop_rmap_weapon_rate'])
    for a in armor: add('item', 'ITMP_' + a[3:], j['drop_rmap_armor_rate'] / 3)
    add('item', j['drop_item_id_1'], j['drop_item_1_rate'])
    add('item', j['drop_item_id_2'], j['drop_item_2_rate'])
    for d in drops:
        if d['kind'] == 'part': d['name'] = PART.get(d['id'], d['id'])
    p = params.get(j['type'])
    if p:
        dmg = dict(common)
        for k, v in p.items():
            if dmg_key(k): dmg[dmg_key(k)] = v / 10
        throws = {k[len('THROW_MUSH_RATE_'):]: v for k, v in p.items() if re.fullmatch(r'THROW_MUSH_RATE_\d{3}', k)}
        tot = sum(throws.values())
        throws = [dict(id='MSR_' + k, name=msr_name.get('MSR_' + k, 'MSR_' + k), pct=round(100 * v / tot)) for k, v in sorted(throws.items(), key=lambda x: -x[1])] if tot else []
    else:
        dmg, throws = family_dmg[f], []
    lvl = j['hp']      # every stat column holds the same number: the level row in master_jackal_bodylvl_status_value
    fams.setdefault(f, []).append(dict(
        type=j['type'], tier=j['type'][len('JACKAL_'):], level=lvl, hud=p.get('HUD_LEVEL') if p else None, exp=j['exp'],
        coins=[j['money_min'], j['money_max']] if j['drop_coin_rate'] else None, stats=stat.get(lvl),
        weapon=dict(id=j['armr'], name=PART.get(j['armr'], j['armr'])), armor=[dict(id=a, name=PART.get(a, a)) for a in armor],
        look='JACKAL_%s%s' % (f, '002' if d_look else ''), drops=drops,
        dmg={k: v for k, v in sorted(dmg.items(), key=lambda x: (FIRST.index(x[0]) if x[0] in FIRST else len(FIRST), DMG[x[0]]))}, throws=throws))

cast = {}
for p0, p3 in q("select p0, p3 from master_credit where p0 like 'JACKAL _' order by id"): cast.setdefault(p0[-1], []).append(p3)
families = []
for f in 'XYZ':
    t = fams[f]
    families.append(dict(id=f, name='Jackal ' + f, gender='female' if f == 'Z' else 'male', voice=dict(en=cast[f][0], jp=cast[f][1]),
                         weaponType=txt('WEAPON_CTGRY.TXT_' + t[0]['weapon']['id']), looks=['JACKAL_' + f, 'JACKAL_%s002' % f], tiers=t))
mails = [dict(title=txt('DEATH.%s_TITLE' % m), text=txt('DEATH.' + m)) for m in ('TXT_MAIL_03', 'TXT_MAIL_65', 'TXT_MAIL_69')]
qr = q("select cond_flr, first_rwd from master_quest where qid='KILL_JACKAL_001'")[0]
rw = q("select val0 from master_reward where rwdid=? and type='ITEM'", qr[1])
quest = dict(name=txt('QUEST_DES.TXT_BEAT_JACKALS'), floor=qr[0], reward=item_name(rw[0][0]) if rw else qr[1])
out = dict(families=families, dmgLabels=DMG, mails=mails, quest=quest)
open('data/jackals.js', 'w', encoding='utf-8', newline='\n').write(
    "// Generated by tools/jackals.py from the game's masters.db (master_jackal and related tables, master_credit, master_text).\nwindow.JACKALS = "
    + json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('{"type":', '\n{"type":') + ';\n')
print('families', len(families), 'tiers', sum(len(f['tiers']) for f in families))

"""Write data/forcemen.js: the 4 FORCEMEN (White Steel, Red Napalm, Black Thunder, Pale Wind), from the game's masters.db.

Usage (from the site's root folder): forcemen.py
LID_MASTERS can point at an unmodded copy of the database, as for items.py.

Sources:
  master_stage_fourforcemen       which stage's arena holds which Forceman, and at which level; three arenas per stage
                                  (levels 1, 2, 3), set in areas whose arena script is the normal, HARD or EXPART one
                                  (master_area_setting_unit), which floors those areas are on (master_floor), and a fourth
                                  arena at level 0 in each stage's HVN area
  master_fourforcemen_param_int   per Forceman and level 1-8: HP, STR, DEX, VIT, LUK, EXP, attack and defence factors and
                                  the share of damage taken from each weapon type (…DMGDOWNRATE, in percent)
  master_quest, master_text       the kill quests, the arena's rules text and the mails about them
"""
import os, re, json, sqlite3, collections
import upk

DB = os.path.abspath(os.environ.get('LID_MASTERS') or os.path.join(upk.GAME, '..', 'Content', 'masters.db')).replace(os.sep, '/')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()
TEXT = {(s, i): t for s, i, t in q("select sct, id, txt from master_text where lang='int' and snd=''")}
def txt(ref): return TEXT.get(tuple(ref.split('.', 1)), ref) if ref else ''
PART = {i: txt(n) for i, n in q('select id, name from master_part')}
ITEM = {i: txt(n) for i, n in q('select itemid, name from master_item')}
clean = lambda t: re.sub(r'\s+', ' ', t or '').strip()

STAGE = {'S_MET': 'Metro', 'S_ARC': 'Arcade', 'S_AMS': 'Amusement Park', 'S_RFT': 'Rooftop'}
MODE = {'': 'Normal', 'HARD': 'Hard', 'H': 'Hard', 'EXPART': 'Nightmare', 'EXPT': 'Nightmare', 'E': 'Nightmare'}
area_floor = {a: no for no, a in q('select distinct no, areaid from master_floor where no > 0')}
arena = collections.defaultdict(dict)       # stage -> mode -> floor
for stg, area, unit, kis in q("select stgid, areaid, unit, kis from master_area_setting_unit where unit like '%SMALLBOSS' and areaid not like '%HVN%'"):
    mode = MODE.get(kis.rsplit('_', 1)[-1] if kis else '', '?')
    if area in area_floor: arena[stg][mode] = area_floor[area]

P = collections.defaultdict(dict)
for t, l, n, v in q('select type, lvl, name, value from master_fourforcemen_param_int'): P[t][l] = dict(P[t].get(l, {}), **{n: v})
WEAPON = {'ARCWELDING': 'Arc welder', 'ASSAULTRIFLE': 'Assault rifle', 'BEAMYOYO': 'Beam yo-yo', 'BIKERAGE': 'Bike (Killer Move)', 'BOBSLED': 'Bobsled',
          'BOWLINGRAGE': 'Bowling ball (Killer Move)', 'CHAINSAW': 'Chainsaw', 'CHAINSAWRAGE': 'Chainsaw (Killer Move)', 'CROSSBOW': 'Crossbow',
          'CROSSBOWRAGE': 'Crossbow (Killer Move)', 'DRILL': 'Drill', 'DRILLRAGE': 'Drill (Killer Move)', 'FIREROD': 'Fire rod',
          'FIREWORKSRAGE': 'Fireworks (Killer Move)', 'FLAMERAD': 'Flame radiator', 'KATANA': 'Katana', 'KATANARAGE': 'Katana (Killer Move)',
          'MEDUSA': 'Head of Medusa', 'MORNINSTAR': 'Morning star', 'MORNINSTARRAGE': 'Morning star (Killer Move)', 'NAILGUN': 'Nail gun',
          'PECKER': 'Pecker', 'PITCHINGMACHINE': 'Pitching machine', 'PITCHINGMACHINENATK': 'Pitching machine (normal attack)',
          'REDNAPALMGUN': 'M2G-87 (Red Napalm gun)', 'SABRERAGE': 'Sabre (Killer Move)', 'SHOVEL': 'Shovel', 'SPEAR': 'Spear',
          'SQUARETIMBER': 'Square timber', 'SWORD': 'Sword', 'TASERGUN': 'Taser gun', 'THKNIFE': 'Throwing knife',
          'THKNIFERAGE': 'Throwing knife (Killer Move)', 'THUNDERROD': 'Thunder rod', 'WSCLAW': 'Static Massager (White Steel claw)', 'YOYO': 'Yo-yo'}

def levels(t):
    out = []
    for l in sorted(P[t]):
        d = P[t][l]
        out.append(dict(lvl=l, hp=d.get('HP'), str=d.get('STR'), dex=d.get('DEX'), vit=d.get('VIT'), luk=d.get('LUK'), exp=d.get('EXP'),
                        atkup=d.get('ATKUP'), defup=d.get('DEFUP')))
    return out
def damage(t):
    """{weapon label: [% taken at level 1..8]} for every weapon the data sets for this Forceman."""
    out = {}
    for k in sorted({n for d in P[t].values() for n in d if n.endswith('DMGDOWNRATE')}):
        key = k[:-len('DMGDOWNRATE')]
        out[WEAPON.get(key, key.title())] = [P[t][l].get(k) for l in sorted(P[t])]
    return dict(sorted(out.items()))

def reward(rwd):
    rw = q('select type, val0, num from master_reward where rwdid=?', rwd)
    if not rw: return rwd
    ty, v0, n = rw[0]
    return '%s SPLithium' % format(n, ',') if ty == 'SPIRIT' else ITEM.get(v0, v0) if ty == 'ITEM' else '%s Kill Coins' % format(n, ',') if ty == 'MONEY' \
        else 'Express pass (1 day)' if ty == 'VIP' else v0
def quests(code):
    out = []
    for qid, flr, first, again in q("select qid, cond_flr, first_rwd, rwd from master_quest where qid like ? order by cond_flr", 'KILL_4HM_%s_%%' % code):
        name = txt(q('select val from master_quest_param_desc_text where qid=? and no=0', qid)[0][0])
        out.append(dict(text='Defeat ' + name, floor=flr, reward=reward(first), again=reward(again)))
    return out

FORCEMEN = [('FFM_WHITESTEEL', 'White Steel', 'whitesteel', 'W', 'DIY', ['PT_ARM_WP054', 'PT_ARM_WP055']),
            ('FFM_REDNAPALM', 'Red Napalm', 'rednapalm', 'R', 'MIL', ['PT_ARM_WP056']),
            ('FFM_BLACKTHUNDER', 'Black Thunder', 'blackthunder', 'B', 'FAN', ['PT_ARM_WP057', 'PT_ARM_WP058']),
            ('FFM_PALEWIND', 'Pale Wind', 'palewind', 'P', 'SPO', ['PT_ARM_WP059'])]
stage_of = {t: s for s, t in q("select distinct stgid, type from master_stage_fourforcemen")}
cast = {p0: p3 for p0, p3 in q("select p0, p3 from master_credit where type='TYPE_DOUBLE'")}
out = []
for fid, name, t, code, series, wps in FORCEMEN:
    stg = stage_of[t]
    gear = lambda num, wsfx: dict(weapons=[dict(id=w + wsfx, name=PART.get(w + wsfx, w)) for w in wps],
                                  armor=[dict(id='PT_%s_%s_%s' % (series, s, num), name=PART.get('PT_%s_%s_%s' % (series, s, num), '')) for s in ('HEAD', 'TOPS', 'BTM')])
    out.append(dict(id=fid, name=name, type=t, area=STAGE.get(stg, stg), floors=arena[stg], levels=levels(t), damage=damage(t),
                    gear=gear('021', '_001'), hell=gear('022', '_0H1'), quests=quests(code), voice=cast.get(name.upper(), '')))
rules = [clean(txt('4FORCEMEN.' + k)) for k in ('TXT_BATTLE_WAR', 'TXT_BATTLE_WAR2', 'TXT_BATTLE_WARR00', 'TXT_BATTLE_WARR01', 'TXT_BATTLE_WARR02', 'TXT_BATTLE_WARR03')]
black = [clean(txt('4FORCEMEN.' + k)) for k in ('TXT_HEALING', 'TXT_BLACK_ATKUP', 'TXT_RAGEBOOST', 'TXT_PLAYER_ATKUP')]
allq = q("select cond_flr, first_rwd, rwd from master_quest where qid='KILL_ALL4HM_NM'")
mails = []
for k in ('TXT_MAIL_01', 'TXT_MAIL_58', 'TXT_MAIL_61', 'TXT_MAIL_63'):
    mails.append(dict(title=txt('DEATH.%s_TITLE' % k), text=txt('DEATH.' + k)))
data = dict(forcemen=out, rules=rules, blackThunderRules=black, mails=mails,
            allQuest=dict(text=clean(txt('QUEST_DES.TXT_4HMA_BEAT')), floor=allq[0][0], reward=reward(allq[0][1]), again=reward(allq[0][2])))
open('data/forcemen.js', 'w', encoding='utf-8', newline='\n').write(
    "// Generated by tools/forcemen.py from the game's masters.db (master_fourforcemen_param_int, master_stage_fourforcemen, quests, text).\nwindow.FORCEMEN = "
    + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
for f in out: print(f['name'], f['area'], f['floors'], [l['hp'] for l in f['levels']], len(f['damage']), [x['reward'] for x in f['quests']], f['voice'])
print(data['allQuest'], [m['title'] for m in mails])

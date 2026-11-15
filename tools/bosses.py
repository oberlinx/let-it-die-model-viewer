"""Write data/bosses.js: the four Dons and the four mini bosses (and their Mk-2 versions), from the game's masters.db.

Usage (from the site's root folder): bosses.py
LID_MASTERS can point at an unmodded copy of the database, as for items.py.

Sources:
  master_mboss, master_mboss_param_int   the mini bosses MBOSS1-4 (COEN, JIN-DIE, GOTO-9, U-10) and the Mk-2 versions the
                                         Dons fight on (STAGE_BOSS1-4), with HP, stats, EXP, Kill Coins and SPLithium per level
  master_quest(_online) and its params   which name goes with which id, and the quests to beat them
  master_stage_mboss                     which stage's boss arena holds which Don
  master_floor_drop_gen                  a mini boss's drops, floor by floor; it also tells which floors it is set up on
  master_floor                           mini-boss count and level per floor (mbsmin/mbsmax, mbslvlmin/mbslvlmax)
  master_credit                          voice cast
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
def ranges(nums):
    out = []
    for n in sorted(nums):
        if out and n == out[-1][1] + 1: out[-1][1] = n
        else: out.append([n, n])
    return out

STAGE = {'S_MET': 'Metro', 'S_ARC': 'Arcade', 'S_AMS': 'Amusement Park', 'S_RFT': 'Rooftop', 'S_HZM': 'Hell Zone', 'S_HVN': 'Tengoku'}
flr = {}      # floor id -> number; floor number -> (count min, max, level min, max)
lvl = {}
for fid, no, stg, a, b, la, lb in q('select id, no, stgid, mbsmin, mbsmax, mbslvlmin, mbslvlmax from master_floor where no > 0'):
    flr[fid] = no
    if b > 0:
        x = lvl.get(no); lvl[no] = (min(a, x[0]), max(b, x[1]), min(la, x[2]), max(lb, x[3])) if x else (a, b, la, lb)

P = collections.defaultdict(dict)
for t, l, n, v in q('select type, lvl, name, value from master_mboss_param_int'): P[t][l] = dict(P[t].get(l, {}), **{n: v})
def levels(t):
    out = []
    for l in sorted(P[t]):
        d = P[t][l]
        row = dict(lvl=l, hp=d.get('hp'), str=d.get('str'), dex=d.get('dex'), vit=d.get('vit'), stm=d.get('stm'), luk=d.get('luk'), exp=d.get('exp'))
        if 'money_min' in d: row['kc'] = [d['money_min'], d['money_max']]
        if 'spirit_min' in d: row['spl'] = [d['spirit_min'], d['spirit_max']]
        out.append(row)
    return out

# drops: per floor and area, a mini boss of type T gives something from group g with chance freq / (sum of freq for T
# there). Groups from 170 up are single materials; lower groups are sets of gear (master_part.grp). The game data does
# not say how one piece is picked inside a gear group.
part_grp = collections.defaultdict(list)
for i, g in q('select id, grp from master_part where grp > 0'):
    if PART.get(i) and PART[i] not in part_grp[g]: part_grp[g].append(PART[i])
item_grp = collections.defaultdict(list)
for i, g in q('select itemid, grp from master_item where grp >= 170'): item_grp[g].append(i)
rows = q("select flrid, areaid, type, grp, freq from master_floor_drop_gen where type like 'PTGENTP_MBOSS%' and freq > 0")
tot = collections.Counter()
for f, a, t, g, w in rows: tot[(f, a, t)] += w
tower_drops = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))   # type -> floor -> grp -> [%]
tengoku_drops = collections.defaultdict(lambda: collections.defaultdict(list))                                    # type -> grp -> [%]
floors = collections.defaultdict(set)
for f, a, t, g, w in rows:
    if f not in flr: continue
    t = t[len('PTGENTP_'):]; no = flr[f]; floors[t].add(no)
    pct = 100.0 * w / tot[(f, a, 'PTGENTP_' + t)]
    if no <= 50: tower_drops[t][no][g].append(pct)
    else: tengoku_drops[t][g].append(pct)
def pr(v): return [round(min(v), 1), round(max(v), 1)]
def entry(g, pcts):
    if g >= 170:
        ids = item_grp.get(g, [])
        e = dict(kind='item', ids=ids, name=' / '.join(ITEM.get(i, i) for i in ids))
    elif g == 0:
        e = dict(kind='none', name='Group 0 (no group given)')
    else:
        e = dict(kind='gear', group=g, names=part_grp.get(g, []), name='Gear group %d' % g)
    e['pct'] = pr(pcts); return e
def drop_list(t):
    tower = [dict(floor=no, drops=sorted((entry(g, p) for g, p in per.items()), key=lambda e: -e['pct'][1]))
             for no, per in sorted(tower_drops[t].items())]
    teng = sorted((entry(g, p) for g, p in tengoku_drops[t].items()), key=lambda e: -e['pct'][1])
    return dict(tower=tower, tengoku=teng)

# who is who: the kill quests pair each id with a name (KILL_MBOSS_COEN_* -> MBOSS1, KILL_MAX_001 -> STAGE_BOSS1, ...),
# and the daily quests give each id a picture
NAME = {'MBOSS1': 'COEN', 'MBOSS2': 'JIN-DIE', 'MBOSS3': 'GOTO-9', 'MBOSS4': 'U-10',
        'STAGE_BOSS1': 'COEN Mk-2', 'STAGE_BOSS2': 'JIN-DIE Mk-2', 'STAGE_BOSS3': 'GOTO-9 Mk-2', 'STAGE_BOSS4': 'U-10 Mk-2'}
cast = {}
for p0, p3 in q("select p0, p3 from master_credit where type = 'TYPE_DOUBLE' order by id"): cast.setdefault(p0, []).append(p3)
def voice(key):
    v = cast.get(key, [])
    return dict(en=v[0] if v else '', jp=v[1] if len(v) > 1 else '')

def quests(prefix):
    out = []
    for qid, desc, flr_, rwd in q("select qid, desc, cond_flr, first_rwd from master_quest where qid like ? order by qid", prefix + '%'):
        params = {i: txt(v) for _, i, v in q('select qid, no, val from master_quest_param_desc_text where qid=?', qid)}
        d = re.sub(r'#(\d)', lambda m: params.get(int(m.group(1)), ''), txt(desc)).replace('\n', ' ')
        rw = q("select type, val0, num from master_reward where rwdid=?", rwd)
        r = ''
        if rw:
            ty, v0, n = rw[0]
            r = (PART.get('PT_' + v0[5:], v0) + ' Blueprint') if v0.startswith('ITMP_') else ITEM.get(v0, v0) if ty == 'ITEM' else '%s Kill Coins' % format(n, ',') if ty == 'MONEY' else v0
        out.append(dict(text=re.sub(r'\s+', ' ', d).strip(), floor=flr_, reward=r))
    return out

minis = []
for n, (tid, key, qkey, img) in enumerate([('MBOSS1', 'COEN', 'KILL_MBOSS_COEN', 'COEN'), ('MBOSS2', 'JIN-DIE', 'KILL_MBOSS_JINDIE', 'JIN-DIE'),
                                           ('MBOSS3', 'GOTO-9', 'KILL_MBOSS_GOTO9', 'GOTO-9'), ('MBOSS4', 'U-10', 'KILL_MBOSS_U10', 'U-10,RADIO DJ')], 1):
    fl = sorted(floors[tid])
    tower = [[f] + list(lvl[f]) for f in fl if f <= 50 and f in lvl]
    hv = [f for f in fl if f > 50]
    minis.append(dict(id=tid, name=key, mk2='STAGE_BOSS%d' % n, voice=voice(img), levels=levels(tid), mk2levels=levels('STAGE_BOSS%d' % n),
                      tower=tower, tengoku=dict(floors=hv, lvl=[min(lvl[f][2] for f in hv if f in lvl), max(lvl[f][3] for f in hv if f in lvl)]) if hv else None,
                      drops=drop_list(tid), quests=quests(qkey)))

arena = {t: STAGE.get(s, s) for s, t in q("select stgid, type from master_stage_mboss where unit='BOSS' and type like 'STAGE_BOSS%' and stgid != 'S_HVN'")}
FLOOR = {'Metro': 10, 'Arcade': 20, 'Amusement Park': 30, 'Rooftop': 40}
dons = []
for n, (did, name, ckey, qkey, mesh) in enumerate([('DON_MAX', 'Max Sharp', 'MAX SHARP', 'KILL_MAX', 'SK_CH_Boss_No01'),
                                                   ('DON_JACKSON', 'Colonel Jackson', 'COLONEL JACKSON', 'KILL_JACKSON', 'SK_CH_Boss_No02'),
                                                   ('DON_CROWLEY', 'Mr. Crowley', 'MR. CROWLEY', 'KILL_CROWLEY', 'SK_CH_Boss_No03'),
                                                   ('DON_GUNKANYAMA', 'Taro Gunkanyama', 'TARO GUNKANYAMA', 'KILL_GUNKANYAMA', 'SK_CH_Boss_No04')], 1):
    sb = 'STAGE_BOSS%d' % n; where = arena.get(sb, '')
    dons.append(dict(id=did, name=name, rides=sb, rideName=NAME[sb], mini='MBOSS%d' % n, voice=voice(ckey), area=where, floor=FLOOR.get(where),
                     quests=quests(qkey)))
allq = quests('KILL_BOSS_ALL') + quests('KILL_MBOSS_ALL')
out = dict(dons=dons, minis=minis, allQuests=allq,
           consts={k: v for k, v in q("select id, value from master_const_int where id in ('BOSS_BLOODNIUM_POINT', 'MBOSS_BLOODNIUM_POINT')")})
open('data/bosses.js', 'w', encoding='utf-8', newline='\n').write(
    "// Generated by tools/bosses.py from the game's masters.db (master_mboss and related tables, master_floor_drop_gen, quests, credits).\nwindow.BOSSES = "
    + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n')
for m in minis: print(m['name'], 'levels', len(m['levels']), 'tower floors', len(m['tower']), 'tengoku', m['tengoku'] and m['tengoku']['floors'][:3], 'drops', len(m['drops']))
for d in dons: print(d['name'], d['area'], d['floor'], d['voice'], [x['reward'] for x in d['quests']])

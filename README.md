# LET IT DIE Viewer

A static site showing what things in LET IT DIE look like and what the game data says about them. It is a companion to
the [LET IT DIE save editor](https://oberlinx.github.io/let-it-die-save-editor/): the ids shown are the ones the editor and the save use.

| Page | What it shows |
|---|---|
| `index.html` | Home: the sections and one search box across all of them |
| `models.html` | The 16 fighter bodies (photos, rotatable 3D view in three poses, voices, taunts, side-by-side compare) and the 8 gas masks |
| `jackals.html` | Jackals X, Y and Z in all 15 tiers: stats, gear, drop odds, damage taken per attack, mushrooms thrown, voice cast and the in-game mails about them; photos and a rotatable 3D view of the standard and red-and-black (D) models; every voice clip in English and Japanese, with subtitles for the spoken lines |
| `bosses.html` | The four Dons (Max Sharp, Colonel Jackson, Mr. Crowley, Taro Gunkanyama), the four mini bosses (COEN, JIN-DIE, GOTO-9, U-10) with their Mk-2 versions, and the 4 FORCEMEN (White Steel, Red Napalm, Black Thunder, Pale Wind) with their arena floors, levels, damage taken by weapon and Hell looks: where they appear, stats per level, drops, quests, voice cast, photos, a rotatable 3D view and every voice clip in English and Japanese |
| `decals.html` | All 368 skill decals, a normal and premium pair sharing one card |
| `gear.html` | Weapons and armour: stats at every upgrade level, STR/DEX scaling and damage types, blueprint sources, upgrade lines, armour sets, development and upgrade costs |
| `materials.html` | Crafting materials and consumables: prices and every piece of gear that needs each one |
| `mushrooms.html` | Mushrooms and edible beasts: effects raw and grilled, and the floors they spawn on |

Open `index.html`, or serve the folder with GitHub Pages. `index.html`, `gear.html`, `materials.html` and `mushrooms.html` are written by
`tools/make_pages.py`; edit that script rather than those files. It also writes the navigation bar into the hand-written pages.

## Which database the data comes from

`tools/items.py` and `tools/decals.py` read the game's `masters.db`. If that file has been modded, point them at an
unmodded copy with the `LID_MASTERS` environment variable (all the data scripts in `tools/` read it). The data here
was built that way, from the unmodded database of game version 5.0.6: a modded database can
contain extra gear and has its PlayStation-only flags cleared, which also shifts the stew odds.

## How the images were made

The pictures in `img/` are renders of the game's own meshes and textures, produced by the scripts in `tools/`:

- `upk.py`, `lzo.py` – minimal reader for the game's cooked Unreal Engine 3 packages (LZO-compressed, 64-bit bulk data offsets).
- `extract.py <out-dir>` – reads `master_body` / `master_asset` from `masters.db`, then dumps each body and hair mesh
  plus its textures (as DDS) and a `models.json` manifest. Needs a local install of the game; edit `GAME` in `upk.py`.
- `render.html` + `serve.py <dump-dir> <image-dir> <port>` – three.js harness that renders every model
  (skin, underwear overlay and hair, as the game's material does), with and without the gas mask and saves the WebP files.

- `voices.py <out-dir>` – copies five sample voice clips per model, in English and Japanese, out of the game's voice packages
  (they are stored as Ogg Vorbis, so nothing is re-encoded). These are the files in `voice/`.

- `taunts.py <out-dir>` – reads the taunt animations' sound notifies (which voice cue or effect plays at which moment)
  and copies the clips they need; this produces `data/taunts.js` and `voice/taunt/`.

- `pack3d.py <dump-dir> <out-dir> <js-file>` and the harness's `bakeTextures()` – pack each mesh into one `.bin` and bake
  1024 px WebP textures (underwear painted into the skin, hair opacity as its own image) for the page's rotatable 3D view (`model3d/`).

- `decoys.py <dump-dir>` – dumps the Decoyshroom statue for each body (a static mesh with the body, its hair and the
  mushrooms growing on it). The renderer, `pack3d.py` and the models page's Decoy look use these.

For the Jackals, Dons, mini bosses and 4 FORCEMEN:

- `jackals.py` – reads `master_jackal` and the tables around it (stats per level, per-tier tuning, the damage constants,
  credits and mails) and writes `data/jackals.js`. Run it from the site's root folder.
- `bosses.py` – reads the mini-boss tables (`master_mboss*`: HP, stats, EXP, Kill Coins and SPLithium per level), their
  floors and drops (`master_floor`, `master_floor_drop_gen`), the boss arenas, quests and credits, and writes `data/bosses.js`.
- `forcemen.py` – reads `master_fourforcemen_param_int` and `master_stage_fourforcemen` (levels, damage taken by weapon, arenas and
  their floors), their gear, quests and the mails about them, and writes `data/forcemen.js`.
- `enemy_models.py <jackals|bosses|forcemen> <dump-dir>` – dumps that set's meshes with `extract.py`'s functions and poses each
  with its own idle animation using `pose.py`'s, writing `<set>.json`: the six Jackal meshes (X, Y, Z and their
  red-and-black `002` versions), the four Dons, the four mini bosses and their four Mk-2 versions, and the 4 FORCEMEN (no character mesh of their
  own: their armour set and its Hell version merged with the Male 1 body and posed together). Serve the dump with
  `serve.py`, open `render.html?set=<set>` and run `renderSet()` (the photos in `img/`; bosses are framed to their own size)
  and `bakeSetTextures(1024)`; then `enemy_models.py <set> <dump-dir> --pack <shots-dir> model3d data/<set>3d.js` packs
  the meshes for the 3D view (uint32 indices for meshes past 65,535 vertices) and copies the textures, keeping one copy
  of images that are identical.
- `jackal_voices.py` and `boss_voices.py` – copy every voice clip of the Jackals, and of the Dons and mini bosses, in both
  languages (as stored, Ogg Vorbis) into `voice/jackal/` and `voice/boss/`, and write `data/jackalvoices.js` and
  `data/bossvoices.js` with the subtitles of the spoken lines. Run them from the site's root folder.

For the decal catalogue:

- `decals.py <out-dir>` – reads `master_skill` and its related tables, resolves the English text, and dumps each decal's
  256 px icon from the game's UI packages.
- `decal-icons.html` (served by `serve.py`) – converts those raw icons to WebP and builds the sprite sheet the save editor embeds;
  `data/decals.js` is the catalogue data.

- `pose.py <dump-dir> [sequence] [0..1]` – skins every mesh with one frame of a game animation (default: the first frame of
  the neutral idle, `ANI_CH_IDL_Neutral`), using the skeleton and skin weights `extract.py` writes. The renderer and `pack3d.py`
  pick up the posed vertices automatically.

Models are shown in the game's idle stance and lit outside the game engine, so colours are close to but not identical to in-game.

## Contributing and license

Found a number that doesn't match your game, or a page that doesn't work? Open an issue; there is a form for each. See [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md) and the [Security Policy](SECURITY.md).

The site's code and the tools in `tools/` are released under the [GNU GPL v3](LICENSE). The game's art, audio and data shown here are not covered by that licence.

Unofficial fan project. LET IT DIE and its character art belong to their respective rights holders.

# LET IT DIE Viewer

A static site showing what things in LET IT DIE look like and what the game data says about them. It is a companion to
the [LET IT DIE save editor](https://oberlinx.github.io/let-it-die-save-editor/): the ids shown are the ones the editor and the save use.

| Page | What it shows |
|---|---|
| `index.html` | Home: the four sections and one search box across all of them |
| `models.html` | The 16 fighter bodies (photos, rotatable 3D view in three poses, voices, taunts, side-by-side compare) and the 8 gas masks |
| `decals.html` | All 368 skill decals, a normal and premium pair sharing one card |
| `gear.html` | Weapons and armour: stats at every upgrade level, upgrade lines, armour sets, development and upgrade costs |
| `materials.html` | Crafting materials and consumables: prices and every piece of gear that needs each one |
| `mushrooms.html` | Mushrooms and edible beasts: effects raw and grilled, and the floors they spawn on |

Open `index.html`, or serve the folder with GitHub Pages. `index.html`, `gear.html`, `materials.html` and `mushrooms.html` are written by
`tools/make_pages.py`; edit that script rather than those files.

## Which database the data comes from

`tools/items.py` and `tools/decals.py` read the game's `masters.db`. If that file has been modded, point them at an
unmodded copy with the `LID_MASTERS` environment variable. The data here was built that way: a modded database can
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

For the decal catalogue:

- `decals.py <out-dir>` – reads `master_skill` and its related tables, resolves the English text, and dumps each decal's
  256 px icon from the game's UI packages.
- `decal-icons.html` (served by `serve.py`) – converts those raw icons to WebP and builds the sprite sheet the save editor embeds;
  `data/decals.js` is the catalogue data.

- `pose.py <dump-dir> [sequence] [0..1]` – skins every mesh with one frame of a game animation (default: the first frame of
  the neutral idle, `ANI_CH_IDL_Neutral`), using the skeleton and skin weights `extract.py` writes. The renderer and `pack3d.py`
  pick up the posed vertices automatically.

Models are shown in the game's idle stance and lit outside the game engine, so colours are close to but not identical to in-game.

Unofficial fan project. LET IT DIE and its character art belong to their respective rights holders.

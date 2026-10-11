# LET IT DIE Fighter Models

A single static page that shows the 16 fighter body models from LET IT DIE next to their internal ids
(`BODY_FEMALE_001` … `BODY_MALE_008`). The game never displays these names, so this is a visual lookup
for the model picker in the [LET IT DIE save editor](https://oberlinx.github.io/let-it-die-save-editor/).

Open `index.html`, or serve the folder with GitHub Pages.

## How the images were made

The pictures in `img/` are renders of the game's own meshes and textures, produced by the scripts in `tools/`:

- `upk.py`, `lzo.py` – minimal reader for the game's cooked Unreal Engine 3 packages (LZO-compressed, 64-bit bulk data offsets).
- `extract.py <out-dir>` – reads `master_body` / `master_asset` from `masters.db`, then dumps each body and hair mesh
  plus its textures (as DDS) and a `models.json` manifest. Needs a local install of the game; edit `GAME` in `upk.py`.
- `render.html` + `serve.py <dump-dir> <image-dir> <port>` – three.js harness that renders every model
  (skin, underwear overlay and hair, as the game's material does), with and without the gas mask and saves the WebP files.

Models are shown in their reference pose and lit outside the game engine, so colours are close to but not identical to in-game.

Unofficial fan project. LET IT DIE and its character art belong to their respective rights holders.

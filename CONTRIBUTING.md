# Contributing

Thanks for helping. This is a hobby project run by one person, so replies can take a few days.

By contributing you agree that your code is released under the [GNU GPL v3](LICENSE), like the rest of the site's code and tools. The game's art, audio and data shown on the site belong to their rights holders and are not covered by that licence.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Telling us something is wrong

Most useful of all: a number or name on the site that doesn't match your game. Open a **Data correction** issue and say:

- which page, and the entry's id (shown in its details, for example `PT_ARM_WP006_005`)
- what the site shows
- what the game shows, with a screenshot if you can
- anything that changes the number in your game: decals, the fighter's grade or level, mushrooms

If your game is modded, say so. The site describes the unmodded game.

For a page that doesn't work (blank 3D view, missing picture, broken layout), open a **Bug report** with your browser and device. For ideas, open a **Feature request**.

Security problems go through the private form described in [SECURITY.md](SECURITY.md), not a public issue.

## Working on the code

The site is static. To look at it locally, run this in the repository folder and open http://localhost:8000:

```bash
python -m http.server
```

Where things live:

- `models.html` and `decals.html` are written by hand. Edit them directly.
- `index.html`, `gear.html`, `materials.html` and `mushrooms.html` are **generated** by `tools/make_pages.py`. Edit the script, not the pages, or your change is lost the next time it runs.
- Everything in `data/`, `img/`, `model3d/` and `voice/` is produced from the game files by the scripts in `tools/`. The README says which script makes what.

The tools need Python 3 and nothing else. They read a LET IT DIE install and never write to it.

## Guidelines

- Build data only from an unmodded game. If your `masters.db` is modded, point the tools at a clean copy with the `LID_MASTERS` environment variable.
- Don't add numbers that can't be traced to the game files or checked in the game. If something is worked out rather than read, label it on the page.
- Keep it a plain static site: no analytics, no sign-ups, no new requests to other sites.
- Use plain wording. Many readers are not programmers and not all read English as a first language.
- Keep pull requests small and about one thing, and say how you checked the result.

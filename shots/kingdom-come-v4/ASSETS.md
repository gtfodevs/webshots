# Kingdom Come v4 (example music shot)

Code, timeline and scene plan only. The song and the approved ProgressiveSlop art are song-specific and live in the channel folder (`progressive-slop/assets/kingdom-come-v4/`):

- `stage/assets/cast/*.png` + `rig.json`: cutouts from `source/{uno,aura,cast}-sheet.jpg` (`scripts/cutout_sheet.py --rows 2 --count 3 --upscale 2`, cast sheet with `--boxes/--erase --model birefnet-general`), Uno's pendant fixed with `scripts/pendant_one.py`, rigged with `scripts/rig_actor.py --overrides rig.overrides.json`.
- `stage/assets/bg/bg-*.jpg` + `bg-*-glow-*.png` + `bg-*.fx.json`: backgrounds and their light maps (`scripts/bg_lightmap.py`).
- `stage/assets/song.m4a`, `stage/assets/cover.jpg`.

Copy them into `stage/assets/` to render. See `skills/music-video/SKILL.md`.

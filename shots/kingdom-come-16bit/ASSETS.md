# Kingdom Come 16-bit (pixel-game music shot)

Code, timeline and scene plan only. Media lives in the channel folder `channels/progressiveslop/assets/kingdom-come-16bit/`:

- `source/sprites-ref.jpg` (design reference sheet on flat magenta), `source/bg-{kingdom,forest,lair,hall}.jpg`
- `source/heroes-walk-combat-ref.jpg`, `source/enemies-combat-ref.jpg` (magenta key ~#E8157A), `source/walk-design-ref-v3.jpg` (Uno top row, Aura bottom) and `source/animals-ref-v3.jpg` (wolf run/attack, spider, bat) on pure #00FF00: rig parts and cut-in portraits are cut from these by `rig_v3.py` / `sprites_v2.py`.
- `source/uno-walk-v4/f0..f7.jpg`: frame-by-frame Uno walk poses (contact R, down, passing, up, contact L, down L, passing L, up L) on #00FF00, consumed by `walk_v4.py`.
- `fonts/PressStart2P-Regular.ttf` (OFL, from google/fonts)

`python3 shots/kingdom-come-16bit/build_assets.py` builds `stage/assets/px/` (sprite atlas + json, 480x270 backgrounds and parallax bands, 1-bit font) and `out/kingdom-come-16bit/sprites.png`. Copy `song.m4a` (same as kingdom-come-v4) to `stage/assets/`. See the "pixel game" section of `docs/MUSIC_MODE.md`.

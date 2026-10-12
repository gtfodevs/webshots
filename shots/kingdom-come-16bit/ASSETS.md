# Kingdom Come 16-bit (pixel-game music shot)

Code, timeline and scene plan only. Media lives in the channel folder `channels/progressiveslop/assets/kingdom-come-16bit/`:

- `source/sprites-ref.jpg` (design reference sheet on flat magenta), `source/bg-{kingdom,forest,lair,hall}.jpg`
- `fonts/PressStart2P-Regular.ttf` (OFL, from google/fonts)

`python3 shots/kingdom-come-16bit/build_assets.py` builds `stage/assets/px/` (sprite atlas + json, 480x270 backgrounds and parallax bands, 1-bit font) and `out/kingdom-come-16bit/sprites.png`. Copy `song.m4a` (same as kingdom-come-v4) to `stage/assets/`. See the "pixel game" section of `docs/MUSIC_MODE.md`.

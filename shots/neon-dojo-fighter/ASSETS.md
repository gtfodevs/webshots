# Neon Dojo fighter (pixel-game music shot)

Code, timeline, storyboard and asset list only. Media is not committed.
- `stage/assets/song.m4a`: from `npm run suno:sync -- ea6b85b9-efbb-40b4-83db-e9bb853f4122 --channel progressiveslop` (channels/progressiveslop/songs/<id>/song.m4a).
- `python3 shots/neon-dojo-fighter/build_assets.py` builds `stage/assets/px/font8.png` (Press Start 2P, OFL, channel fonts folder).
- Character art (per ASSET_LIST.md) goes to `channels/progressiveslop/assets/neon-dojo-fighter/source/<char>/<pose>.jpg`. `python3 shots/neon-dojo-fighter/uno_sprites.py <char>` builds `stage/assets/px/<char>.png/json`, and `tools_gifs.py <char> <dir>` makes the preview GIFs. Characters without art fall back to the rect placeholders from `stage/fight.js` `poseRects()`.

---
name: music-video
description: Turn a song (e.g. a Suno track) into a narration-free animated music video with webshots music mode — storyline with a recurring cast, an approved AI asset set in one channel style, beat-synced 2D animation, a repeating chorus routine, and 16:9 + YouTube Shorts renders at -14 LUFS. Use when the user gives you a song, a Suno link, or asks for a music video / lyric video / Short.
---

# Music video (webshots music mode)

Works with any AI assistant and any image model. Design background: `docs/MUSIC_MODE.md`. Worked example: `shots/kingdom-come-v4` (Kingdom Come, ProgressiveSlop; rigged actors).

**Channel brand first.** Read `channels/<channel>/style.json` before writing a prompt or a scene; its `rules` are hard constraints. ProgressiveSlop: artist "ProgressiveSlop" (Progressive🆂🅻🅾🅿 on Suno), tagline "Uno and Aura — hip-hop fun, dressed up." on the title and end cards; everything is a robot (no living creatures), polished silver chrome, glowing red eyes, headphones for ears; glossy hyper-detailed chrome 3D illustration in neon purple/magenta/cyan; Uno (big heroic build, round bald chrome head, purple fur cloak, gold chain with a "1" pendant, protector) and Aura (graceful, long dark hair streaked crimson, crimson and silver gown, magic) lead every song; the setting changes with the song, the brand does not.
Song-specific assets and renders live in the **channel folder** (e.g. `channels/<channel>/…` here, synced to Jason's `/Volumes/toshiba/progressive-slop`); this skill, the runtime and the templates stay generic.

Stop for human approval at the two marked gates. Everything else runs autonomously.

## 1. Suno sync (song = source of truth)
- `npm run suno:sync -- <song-id or url> [--channel <channel>]` → `channels/<channel>/songs/<id>/` (audio, video, cover, lyrics, meta). If the mp3 403s, the script extracts audio from the mp4.
- `npm run new -- <name> --music <audio> --lyrics <lyrics.txt>` → `shots/<name>/` with `stage/timeline.json` (tempo, beats, bars, sections, energy, Whisper words, aligned lyrics), placeholder scenes, `<name>.music.json`.
- Sanity-check `timeline.json`: section labels match the lyric tags; every chorus has words.

## 2. Storyline + cast
- 3-5 recurring characters, one villain/foil. Arc mapped to sections: setup (chorus 1) → journey (verses) → conflict (a late chorus) → payoff (last chorus) → coda (outro/credits). Stay faithful to the lyrics.
- Write it into `<name>.music.json` → `storyline` (cast with one-line descriptions, arc → scene names).
- Pick the running gag for the chorus routine (who changes participation each chorus).

## 3. Asset list
- `channels/<channel>/assets/<name>/manifest.json`: per character a **sheet with 4 poses** (neutral, action, reaction, happy — chosen from story beats, e.g. lit/flame-out/cracked/joyful), one **group dance** image with the whole cast in the same pose, 3-5 **backgrounds** (one per story location; include a "payoff" version of the opening location), and props only if a pose can't carry them. Use `workflows/asset-list.md`.

## 4. Style anchor — GATE 1 (approval)
- Generate ONE character sheet (the hero) from the channel `style.json` + the song cover as reference, with `prompts/style-anchor.md`. Show it. Do not generate the rest until the user approves the look. Record the approved description in the manifest (`style_anchor`).

## 5. Generate the set (any image model)
- Use the exact templates in `prompts/` with the **style anchor + cover as reference images** on every call: `character-sheet.md`, `group-dance.md` (all sheets as references), `background.md`. Highest quality, 16:9 (e.g. 1024x576 or larger), plain solid light-gray background for characters, no text.
- Save raw outputs to `channels/<channel>/assets/<name>/source/` (`<who>-sheet.jpg`, `chorus-dance.jpg`, `bg-<place>.jpg`). Re-roll any image that drifts (proportions, outline weight, palette).

## 6. Cutouts, rig + light maps — GATE 2 (approval of the contact sheet)
- `pip install --user "rembg[cpu]"` once.
- Per sheet: `python3 scripts/cutout_sheet.py source/<who>-sheet.jpg --count 4 --names a,b,c,d -o cutouts/<who> --upscale 2`; grids `--rows 2 --count 3`; touching line-ups: one figure per call with `--boxes x0,y0,x1,y1 --erase <neighbour rects> --model birefnet-general`.
- Brand fixes (e.g. `scripts/pendant_one.py cutouts/uno-*.png` for Uno's gold "1"; `--at u,v` when auto-detection misses).
- Rig: `python3 scripts/rig_actor.py cutouts/*.png -o rig.json --overrides rig.overrides.json`; check eyes/headphones/neck on the contact sheet and fix misses in the overrides file (small eyes, staffs and hats fool the detector).
- Backgrounds: `python3 scripts/bg_lightmap.py source/bg-<place>.jpg -o layers/bg-<place> --keys red,cyan,purple,magenta,white`; note coordinates for set pieces (fountain, disco ball, laser origins, a creature's eyes).
- Labeled contact sheet of everything with the rig points drawn (checker behind cutouts) → show it, fix bad edges/clipped limbs, update manifest statuses.
- Labeled contact sheet of everything (checker behind cutouts) → show it, fix bad edges/clipped limbs, update manifest statuses.

## 7. Chorus routine
- One routine, reused in EVERY chorus (scenes `dance1..danceN`, cut in on a bar for the last 4-6 bars of each chorus). 4-beat move: kick (beat 1) / alt pose + mirror (2) / dance + hop (3) / alt + squash (4); camera punch + spotlight swing on downbeats; a title stamp "official chorus routine #n".
- Running gag escalates per chorus (refuse → tap → downbeats only → full while denying → front and center). One new bubble per chorus; the move never changes. Checklist: `workflows/chorus-routine.md`.

## 8. Scene build (actors are alive, always)
- Copy `cutouts/*.png` + `rig.json` → `stage/assets/cast/`, and `source/bg-*.jpg` + `layers/*` → `stage/assets/bg/`. Load `/actors.js` after `/music.js`; `await Actors.load('assets/cast/rig.json'); Actors.start();`.
- `Actors.define()` each character once (poses, `sub` = beat subdivision, `hair`, `wings`, `gleamTop`), then per scene `Actors.actor(host, who, {x, y, h, pose, seed, flip}).play('<loop>')`. Give every on-screen character a loop; never leave a still. Different `seed`/`sub` per character so they never move in lockstep.
- Per story moment, mix and match per character: a loop (`walk`, `groove`, `attack`, `cast`, `react`, `dance`, `menace`, `bounce`, `hover`, `sleep`, ...), a pose change with `Actors.transition(a, pose, {smear})` (never a hard swap), accents (`Actors.accent(a, 'flare'|'recoil'|'flex'|'shiver')`) and comic marks (`Actors.impact(host, x, y, {text})`). Time story beats to lyric words with `AT(seconds)` (see the v4 stage).
- Animate every background: `Actors.bg(plate, '<place>', {glow, shimmer, twinkle, fountain, lasers, disco, eyes})`.
- `Actors.clear()` at the start of every scene.
- Verses carry plot (parallax pans, comic pages with `.c-panel` + bubbles/captions); choruses are set pieces then the routine. SFX lettering on hits, particles for fire/magic/party. Lyrics: `slam` for chorus lines, `comic` for verses. Keep characters' feet above the lyric band.
- Add `html[data-format=vertical]` CSS and format-aware positions so the stage reflows for Shorts.

## 9. Render 16:9 + Shorts
- `npm run check -- <name>` → review `out/<name>/check/sheet.png` (no overlaps, nobody hidden by lyrics, no empty frames).
- Motion review before the long render: `npm run render -- <name> --start a --end b --out <name>-test` for 5 s, then check that `ffmpeg -i out/<name>-test.mp4 -vf mpdecimate -f null -` keeps ~every frame, and diff consecutive crops of one actor (head, arms/cape and hem should differ independently). Use `-fps_mode vfr` with `select`.
- Renders are frame-exact by default (virtual clock; ~0.15-0.6 s per frame on the box, so start long renders in the background). `--realtime` is the old wall-clock capture.
- `npm run render -- <name>` → `out/<name>.mp4` (1920x1080, song at -14 LUFS, fade out).
- Shorts: set `shorts.start/end` in `<name>.music.json` on bar lines around one or two routines (40-55 s), then `npm run render -- <name> --format vertical --start <s> --end <e>`. Bubbles and captions are clamped to the visible area automatically (`Music.safe`); keep actors inside the visible stage band (x ≈ 240-1040 in the v4 vertical layout).

## 10. QA
- `workflows/qa.md`: loudness (`ffmpeg -af ebur128`) ≈ -14 LUFS, duration, resolution, frames sampled at known lyric word times show the right word, each chorus shows the routine, contact sheet clean.

## 11. Export
- Commit the shot. Copy renders + manifest + contact sheet into the channel folder (`channels/<channel>/renders/`, `…/assets/<name>/`), then merge into the user's channel folder without overwriting (`workflows/export.md`).

## Style option: pixel game (16-bit sprites)
- Pick it when the assets are stills that can't be animated convincingly (lesson from v4: don't overreach). Example: `shots/kingdom-come-16bit` (`build_assets.py` + one-canvas `stage/index.html`).
- Assets: one design-reference sprite sheet per cast row on a flat chroma background (8 frames each: idle x3, actions, dance poses) + pixel-art backgrounds. Build with `scripts/pixel_sprites.py` (key → crop → downscale to ~60 px → shared palette → outline; extra loop frames by pixel edits; NPCs re-sampled from hero frames, recoloured by hue, with shaded pixel accessories, so every character matches the background detail). Check the sprite contact sheet before building scenes.
- `"pixel": {"w":480,"h":270}` in `<name>.music.json` for integer 4x capture and nearest-neighbour output. Integer positions only; no smoothing, rotation or blur.
- Story as game stages: arcade title (coin drop on a downbeat), `STAGE n` card per section, side-scroll walks with parallax, encounters, a boss fight with health bars/hit flashes/shake/sparks, `STAGE CLEAR` tally, THE END + channel credit. Every chorus = the same beat-locked dance routine (2 frames per beat), crowd grows each chorus.
- Lyrics: verse lines in an RPG text box typed per sung word; chorus lines as 2x arcade text.
- Review: consecutive-frame strips per character (loops advance), a nearest-neighbour zoom crop (crisp 4x4 blocks, no fringe).
- Speed: set `"lowres": true` in `pixel` (1x capture + one neighbour upscale, ~2x faster); review with frozen-clock stills (`Music.freeze(t)` + screenshot) before any long render; run the landscape and Short renders concurrently; see "Speed and quality notes" in `docs/MUSIC_MODE.md` (timings, reusable kit, chunked renders).

### Walk cycles, combat choreography and pixel QA (v2 method)

**Walk cycle.** Don't trust AI-generated walk frames; they come back near-identical. Use the sheet only for the upper body and build the legs yourself (`scripts/pixel_robots.py`):
- 8 frames: contact, down, pass, up for each leg, with alternating legs.
- 1 px bob `BOB8=[0,1,0,-1,0,1,0,-1]`.
- IK legs painted at 3x as chrome capsules, then downscaled, quantized and outlined.
- Secondary motion: the cloak tail sways a frame behind; Aura's hair moves on its mask only; her gown hem shears in whole-pixel row blocks.
- Characters face their direction of travel.

**Footfalls.** Play 4 walk frames per beat, with contact on the beat. Quantize the camera to 1/4 beat × `STRIDE` px per beat (14 here), so the scroll equals the stride and the planted foot doesn't slide.

**Feet anchoring.** `pack()` aligns every frame by its feet: the lowest opaque pixel sits on the bottom row, centred. Anims marked `air` are aligned by frame bottom instead. Each background declares a ground line in `world.json` (`ground`, plus `depth_rows` for perspective crowds). Draw grounded sprites with `ground()`, which adds a 2-row contact shadow. Exempt sprites (jumps, bats, the hovering boss) pass `{air:1}`.

**Combat choreography.** Fights live in `stage/choreo.json` as event lists measured in beats (`[beat, actor, action, ...]`):
- Every enemy attack is preceded by a telegraph, about one beat earlier.
- The hero answers with block, parry, shield, hop or roll, then counters on the next beat or half-beat.
- Then: hit, a knockback of 1–2 frames, down, and a pixel dissolve.
- Heroes sometimes take a hit (recoil, HP −0.08).
- The boss cycles orbs, ground slam (a shockwave the heroes jump over) and summon (bats). It only takes damage in the opening after each attack.
- Keep hit flashes to 2 frames and hits few. Put big moments on bar downbeats.

**Parallax.** Use at least 4 layers plus a foreground layer, e.g. 0.1/0.3/0.6/1.0/1.4x, with whole-pixel offsets. Make tiles by crossfading wrap, not mirroring. Place foreground pillars where they won't cover a fight (compute them from the fight camera positions).

**Unique NPCs.** Never recolour the heroes. Mix silhouettes and heads:
- body: round, lanky or boxy;
- head: dome, square, visor or antenna;
- plus props and outfits.
Always keep chrome, red eyes and headphones. Don't put a gold chest plate or "1" pendant on NPCs; that belongs to Uno.

**Pixel QA.** `scripts/pixel_qa.py <shot>` runs automatically from `npm run check` when `stage/qa.json` exists. It fails on:
- near-identical or too few distinct loop frames;
- sprites under the minimum height or colour count;
- key-colour fringe pixels;
- gold chest pixels on NPCs;
- NPC-vs-hero silhouette IoU above 0.72;
- enemies without telegraph or attack frames, or fights without a telegraphed enemy attack;
- `fillText`, DOM text, or non-uniform 4x4 blocks (blur);
- grounded sprites off a ground line by more than 1 px;
- parallax layers whose measured shift between two walk frames isn't distinct and increasing;
- mirror-tiled layers.

`scripts/pixel_stills.mjs <shot> <dir> label=sec...` grabs exact stills plus draw logs. `scripts/pixel_preview.py` writes 4x strips and GIFs.

### Corrections checklist (Jason's feedback, check every pixel video)
- [ ] No crude Atari-style sprites. Characters are 48–74 px with shading and outlines, and animals are at least 40 px.
- [ ] Walk frames are not identical: 6–8 distinct frames, alternating legs, bob, secondary motion, no foot sliding.
- [ ] Enemies are not passive. They telegraph, attack, take knockback, go down and dissolve. Heroes block, dodge, counter and sometimes get hit.
- [ ] No HTML or smooth text anywhere. Only the bitmap pixel font, with nearest-neighbour scaling only.
- [ ] Title is arcade style: INSERT COIN, coin drop on a beat, CREDIT 0→1, PRESS START, © PROGRESSIVESLOP.
- [ ] Robot animal enemies (wolves, spiders, bats, serpent), chrome with red eyes, with move loops and telegraph/attack frames.
- [ ] Brand: everything is a robot (silver chrome, red eyes, headphone ears). Uno: round bald head, purple cloak, gold "1" chain, sword. Aura: dark hair with crimson streaks, crimson gown, cyan magic.
- [ ] NPCs are unique designs, not hero recolours, and have no "1" pendant.
- [ ] Nothing floats: feet on the ground line, with contact shadows.
- [ ] Real parallax: 4+ layers plus foreground, distinct speeds, no mirroring.
- [ ] Hit flashes last 1–2 frames, and hits are few.
- [ ] No chroma fringe: key ≈ #E8157A, matte eroded, edges despilled.

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
- [ ] Animated background figures (crowds, monks, spectators, anything that bobs or moves) are cut out one by one over an inpainted clean plate. Never bob a whole band. This is the default in `build_stage()` and fighter QA checks it on every stage.

### v3: connected cut-out rigs (replaces spliced legs)

Splicing redrawn legs onto a fixed upper-body crop detaches the hips and leaves the torso rigid; Jason called it "zombies". AI sheets can't fix this either: every generated walk frame is the same mid-stride pose. Use a 2D cut-out rig instead (`scripts/pixel_rig.py` plus the shot's `rig_v3.py`):

- **Parts.** Cut the head (with headphones), the torso and pelvis, and the cloak, hair or gown from a clean side-view ref on #00FF00 (`RefParts`, at 4x the final size). Paint limbs as chrome segments with round joint caps that overlap (hip sphere, knee cap, elbow, wrist) so joints never gap. Aura's gown is a painted panel whose slit edge follows the near knee; her shin steps out through it.
- **Walk motion.**
  - 8-frame cycle with 2 steps of `STRIDE` px each.
  - The stance foot is solved by IK, planted and sliding back STRIDE/4 per frame, exactly as fast as the world scrolls.
  - The swing foot arcs forward and lifts 5 px.
  - The pelvis follows an inverted-pendulum bob, with a 1 px dip after contact.
  - Arms swing opposite the legs (±22–24°).
  - The torso counter-rotates ±1.5°, the head lags one frame, and cloak and hair shear with a one-frame lag.
  - Measured on Uno: thigh −12..+42°, knee up to 70°.
- **Rendering.** Composite the whole pose at 4x, then box-downscale, quantize and outline **once**. The single outline is what makes it read as one sprite.
- **Packing.** Rig anims pack with `rig: True`: one shared canvas cropped to the union bbox, so the hip stays fixed. Never re-align rig frames by their feet; that makes the body slide, which shows up clearly in the onion skin.
- **Quadrupeds.** The wolf gallop has spine flex (chest and rear rotate opposite, ±7°), front and hind pairs in opposite phase (±40°), knee bend on the swing, and head and tail on offset sines. Telegraph is a crouch, attack is the full lunge. The spider uses an alternating tetrapod gait (legs 0 and 2 of one side with 1 and 3 of the other) and a body bob. The bat has membrane wings rigged up / mid / down / mid (−45..+70°), and the body rises on the downstroke.
- **Animator self-check.** Before showing anything, export 4x strips, GIFs, an onion skin (`pixel_rig.onion`) and one GIF of the walk across the scrolling background. Ask: do the hips stay on the torso, do the legs pass through a full stride, do the feet stay planted against the ground?

### Close-up cut-ins
These are RPG / fighting-game portrait panels. Each is larger pixel art cut from the refs at about 1x source scale; never upscale the small sprites. Each gets a 2–4 frame loop: eye flare, blink, pendant glint, hair shear, cyan charge, jaw snarl. Super-move cut-ins use a full pose with a speed-line band.
- They're listed in `choreo.json` as `cutins: [[sec, anim, beats, style]]` and snapped to beats.
- Keep them to 2–8 beats, about 6–10 per video, at the boss intro, before the boss, on big hits and on chorus drops.
- Never cover a telegraphed attack: put a snarl before the lunge, not on it.

### QA additions (pixel_qa.py)
- Neighbouring loop frames must change silhouette (mask XOR/union) by at least 3%.
- Rig joint ranges are checked from `rig_log.json`: thigh swing ≥ 50°, knee ≥ 45°, foot lift ≥ 3 px, arm ≥ 30°, wing ≥ 90°, spine flex ≥ 10°.
- Paired legs must alternate (correlation < 0).
- Every rigged frame must be one connected component (≥ 97%) with no row gaps.
- The pelvis band must overlap the torso band by at least 4 columns.

Checklist additions:
- [ ] Spliced legs look like zombies: use connected rigs with one outline. Torso and pelvis are one part, joints overlap, and the hip stays fixed in the frame (onion-skin check).
- [ ] Legs travel through the stride (thigh about ±30°, knee bend about 60° on the passing frame, feet lift), and the world scrolls at the stride so planted feet don't slide.
- [ ] Generated creature frames are duplicates too: rig the bat and spider, and verify silhouette change and joint ranges with QA.
- [ ] Use close-up cut-ins at key beats (6–10 in total), as separate larger art with their own loops.

## THE sprite method (v4): per-pose art, shared master upper body, swapped limbs, shared palette, bob table

Jason prefers frame-by-frame art in the original detailed style. Rigs read as "dumbed down", and raw AI poses "boil" because every frame redraws the head, torso and cloak slightly differently. Classic sprite practice fixes both (`shots/kingdom-come-16bit/walk_v4.py`):

1. **Generate one image per pose** in the detailed style on pure #00FF00, same framing and scale, in cycle order.
   - Walk: contact R, down R, passing R (knee up), up R, contact L, down L, passing L, up L.
2. **Key and despill:**
   - background = green dominance;
   - keep the large components, erode the fringe ring by 1 px;
   - clamp green to max(r, b).
3. **Landmarks per frame:**
   - head top and head-centre x;
   - belt row = the widest gold row inside the torso column band;
   - lowest pixel.

   Normalize scale by belt-to-head distance, and confirm it with head width; one AI frame had its belt drawn higher, and head width showed the scale was actually identical.
4. **One master upper body** from the cleanest frame: a core polygon around the head, headphones, torso, pendant, belt and shoulder cape, relative to (head x, belt).
5. **Per frame, composite** (each layer box-downscaled to final size *separately*, then placed at integer offsets so master pixels stay identical):
   - **Lower body** (from the belt line down: hips, legs, feet, blade, cloak hem) from that pose, grounded on one fixed ground row and x-aligned by its head x. If the pose's hips sit below the master belt, the hip row is stretched up so nothing detaches. The seam hides under the gold belt.
   - **Arms, sword hilt and upper cloak edge** from that pose, minus the pose's own torso core, riding with the master torso.
   - **Master core** on top at belt = ground − median leg length + `BOB[i]`.
6. **Bob table:** a triangle, not a sine: `[1, 2, -1, 0]` per step (low on contact/down, high on passing), about 3 px at a 72 px sprite.
7. **Timing:** hold contacts longer: `STEP_FRAC = [0.31, 0.23, 0.23, 0.23]` of a beat (≈140/100/100/100 ms at 10 fps).
8. **Pin the planted foot:** measure the stance-foot x per frame from the art (`foot_travel`). The world scrolls by those per-frame deltas, so the scroll is uneven: `step_scroll = [6.75, 14, 14.25, 4.25]` px with both halves averaged, 39.25 px per beat. Residual slide is ≤ 2 px. The engine's `walkAt(beatsWalked)` returns the frame and distance; rigged walkers sharing the screen use the same schedule (`walk_targets(..., sched=)`).
9. **One shared palette** (the shot's `pal2`), despeckle, and one 1 px outline after compositing.
10. **Pack with `rig: True`** (shared canvas, union crop) so the torso never shifts between frames.
11. **Animator review:** a 10 fps GIF with the holds, a strip, an onion skin (the torso must be one solid ghost, legs fanning) and a GIF crossing the real background.

**Idle (breathing):** same master, with the lower body and arms from the most upright pose (passing). Chest and shoulders rise 1 px, the head follows a frame later, the cloak hem sways 1 px, and the sword is steady. 4 frames at 300/180/340/180 ms (`durations` in the meta; holds at top and bottom). It's the default whenever a story hero isn't moving (`uno_stand`).

**QA:**
- `master_core` walks: the head/torso core region must be ≥ 97% identical to frame 0 after the bob offset (currently 100%).
- `idles`: must have ≥ 3 frames and change ≥ 1% between frames.

Checklist additions:
- [ ] Rigs look dumbed down: use the detailed frame-by-frame poses with the master upper body.
- [ ] No boiling torso: head and torso pixels are identical apart from the bob; only legs, arms and the cloak hem change.
- [ ] The bob is a triangle (2–3 px); contacts are held longer; frame 8 flows into frame 1.
- [ ] Planted foot pinned: the scroll follows the measured foot travel.
- [ ] Idle heroes breathe (never a frozen frame).

### Ground contact fix (v2 render)
The "floating" look in the forest came from the near-ground layer being raw pipe clutter, with no readable surface under the feet. The forest now has a painted walkway slab on the 1.0x layer (`walkway()`), and feet sink 2 px into its lit top edge at ground row 204. QA now uses the stage of each sampled still (`scene_bg`) and checks that each grounded sprite's lowest opaque pixel, at its composited position, sits within ±1 px of *that stage's* ground row. Only crowds and NPCs may use the declared depth rows.

### Improve next (after the first video)
- Aura: detailed frame-by-frame walk (8 poses) and idle, using THE sprite method; she is still the v3 rig and looks simpler than Uno.
- Knights and animals: detailed per-pose frames (knight march 6; wolf gallop 6 + crouch/lunge/bite/hit/down; spider 4 + attack set; bat 4 + dive/hit/down) to replace the rigs.
- Cloak flicker: Uno's lower cloak hem still comes from each pose and shimmers slightly. Make the hem master plus small offsets, or hand-pick the 2–3 least boily hems.
- Walk speed: the art's stride gives about 39 px/beat (about 89 px/s), which is brisk. Generate shorter-stride poses, or use 2 beats per step (8 frames per 2 beats) for a calmer march.
- Hips stretched 2–3 px on the down frames, and a slight sword kink at the hilt seam.
- Forest walkway is plain. Add slab variation and occasional roots in front of the feet.

## Fighting-game shots (SF2 style)
- Put the logic in a pure `stage/fight.js` (scenes, exchanges, state machine, HUD, FX) shared by the page and `scripts/fighter_qa.mjs`. `npm run check` runs that QA automatically.
- Script fights as exchanges. The CPU must swing back in EVERY exchange and land hits in full fights. Keep it to 3 or fewer hits per bar, with hit-stop and short flashes.
- Build the engine with placeholder rect figures first (shared-master core, IK limbs, soles on the ground row), then swap in per-pose art. See docs/MUSIC_MODE.md, "Fighting-game shots".

## Comic mode (comic-book pages instead of a game)

Use when the brief says comic / graphic-novel style. Full reference, both prompt templates, spec format
and QA: `docs/MUSIC_MODE.md` → "Comic mode". The steps for a full song:

1. Load the song's `stage/timeline.json` (beats, downbeats, timed lyrics). Split the song into scenes of
   8–12 bars; 3 panels per page plus a splash for the section's hit.
2. Generate panels with an image model using the **fixed comic style prompt** (bold ink, halftone,
   90s superhero comic, 16:9, NO text in the art) and identical character-sheet lines every time.
3. Animate each panel with **Grok Imagine image-to-video, 480p, shortest duration (6 s)**, using the
   motion-prompt template (one action, locked camera, keep faces/hands/limb count).
4. Review every clip by frame sampling (contact strip + frame-step/drift metrics); mark melting faces / extra limbs / re-framing. Trim to the
   best window: **3.5–4.5 s, the full ~6 s when clean** (QA max 6 s); cut only at real breakage and
   record why in `clip.trimNote`. Land last panels/splashes early enough that clips finish before the page
   turns. No clean window → static panel.
   Hold rule: the clip starts one beat (~0.3–0.5 s) after the panel lands (QA max 0.6 s), so omit
   `clip.at` and let the default do it. Every panel must be a different scene (location, camera, moment);
   keep it playful and kid-friendly. QA fails on duplicate prompts / location+camera / pHash images.
   Layouts: pick from the layout library (docs → "Layout library": slanted/diagonal gutters, insets,
   angled overlaps, breakout splashes, mixed sizes) to fit each page's panel count; never the same layout or
   splash style on consecutive pages, and use many across the song (QA fails repeats, flags low variety).
5. Write `shots/<name>/<name>.comic.json` (for a whole song use `pages`; plan first with `"draft": true`; panels in order: image, clip in/out, slot, captions with the
   lyric line, SFX, the beat each lands on; transition; splash).
6. `npm run check -- <name>` (comic QA must PASS) → `npm run comic -- <name>` → review the contact sheet.
   Outputs never overwrite (`-v2`). Commit the spec and code only, never media.
7. **End card** (default, both the full video and the Short): the last ~3 s hold the final frame under
   *BROUGHT TO YOU BY PROGRESSIVE SLOP* / *LIKE AND SUBSCRIBE FOR MORE!* (`spec.endCard`); the song rings on
   and fades (2.5 s+) under it. Check it with `comic_render.py <spec> --endcard-test`.
8. **No clipping** (QA fails): lettering past its panel or the safe area (measured bounds), a lyric caption
   that leaves before its line is sung or overlaps the next caption, a song/Short cut point mid-word, end
   card text outside the title-safe area. Boxes are tested against the panel's real (slanted/tilted) clip path and
   rendered at their peak frame pixel by pixel; the renderer auto-fits (move inward, then shrink). Pick Short start/end in word gaps (timeline `words`).

### Dramatic story workflow (v3+; worked example: `shots/neon-dojo-comic/v3/`)

Every comic video should level up beyond Kingdom Come: real story, real hits. Example files:
`make_v3.py` (the beat sheet as data; writes `plan.md`, `prompts.json`, `motion.txt`), `generate_jobs.json`
(one image job per new panel with its reference images). Art is not committed.

1. **Story first.** Write the full story beat by beat, synced to the lyrics and sections from
   `timeline.json`, before making a single panel. Three acts:
   - **Act 1, early days:** a montage of Uno and Aura learning to pair up under the Sensei. They clash,
     fail (a botched tag) and train, until the tag finally clicks.
   - **Act 2, tournament:** rivals with real stakes. A loss: one hero goes down and Uno carries Aura out.
   - **Act 3, final boss:** a blade lock, the tag-team combo, both super cut-ins, a kid-safe double finisher
     (armour bursts into sparkles), and a resolution (Sensei, belt, sunrise).

   Every page has a **need** line saying what the heroes want or are losing. No page without stakes.
2. **Art direction.** Dramatic, iconic panels; heroes mid-strike, never posing.
   - Cut each fight on the beat as wind-up → strike → impact → reaction.
   - Use extreme angles (worm's-eye, Dutch, top-down, extreme close-up), impact flashes, speed lines,
     screen shake and big SFX lettering.
   - No static standoffs.
3. **Image references.**
   - **Pick references by act.** A reference image that shows the boss leaks the boss into scenes he isn't
     in, so use the Uno/Aura/Sensei sheet for the early acts. Pass only the characters actually in the
     panel (see `generate_jobs.json`).
   - **Spell out every character description in every prompt:** Uno has a round smooth chrome dome, a purple
     fur coat and a gold "1" chain. Aura has a grey robot face, red eyes, dark crimson hair, a modest crimson
     bodysuit and cyan magic. All robots are chrome with red eyes and headphone ears.
   - **Review every panel and regenerate on any of:**
     - a human, or Aura with human skin;
     - an off-model character;
     - a duplicated character or extra limbs;
     - an immodest outfit;
     - low energy or a static pose;
     - text beyond tiny signage.
4. **Grok Imagine.**
   - One clear, fast action per motion prompt (a strike is fine), at 480p and 6 s.
   - Locked or gentle camera; nobody walks toward the camera; no morphing.
   - Review at 8 fps (contact strip plus frame-step spikes). Trim each clip before morphing starts, keep
     3.5–6 s, end before the page turn, and record the reason in a `trimNote`. Regenerate clips that break
     early.
5. **QA gates (`comic_qa.py`, must PASS before rendering):**
   - **Layouts:** no repeats on consecutive pages, and enough variety.
   - **No clipping:** caption and SFX outlines (at their peak, with rotation) must sit inside the panel's
     real clip path and the safe area, and a pixel-level check of each panel's lettering must pass.
   - **End card:** present, and its text fits the title-safe area.
   - **Lyric timing:** captions stay up until the line is sung and never overlap; no audio cut lands
     mid-word.

#### Lessons from the Neon Dojo v3 build

- **Spec builder.** `v3/make_v3_spec.py` turns the beat sheet into `neon-dojo-comic-v3.comic.json`. It
  maps reused panels to their earlier clips (`REUSE_CLIP`) and keeps the 8 fps review verdicts in `TRIMS`.
  Art that has no clip stays a static panel.
- **Clip review.** Look for a big frame-step at 0.1 s or 1–2 s: that is usually a hard cut or camera jump,
  not motion. Trim before it. Also flag the clip if the "finisher" undoes itself (the armour re-forms).
- **Page turns.** A page never turns while a lyric line is still being sung; a short overrun pushes the
  turn one beat later instead of carrying the caption. Carried captions can collide with the next
  page's own lines.
- **Impact SFX.** Set `"impact": true` on a hit's SFX. The panel art flashes white (0.18 s decay) and the
  frame shakes (0.28 s, ±0.8% of width, zoomed 2% so no edge shows). Lettering is drawn after the flash,
  so it stays readable.
- **Short cut points.** Pick Short start and end in word gaps from timeline `words`, after the lyric
  line's `end`. QA warns when an end lands inside a line.

### Lessons from the v3 truncation audit (2026-10-13)
- **SFX sliver on the upper-right:** Bangers is slanted, and the glyph plus stroke overhang past `getbbox()`. Draw SFX on a padded canvas (pad = 0.3·px + 2·stroke + 8), offset the text by `-getbbox(stroke_width=…)`, rotate with `expand=True`, then crop to the ink. QA renders each SFX tile again on an oversized canvas and fails if even 1 ink pixel is lost (`sfx_ink_lost`).
- **Lyric captions show the full sung line.** Never use a shortened version. QA fails when a caption is only a prefix of the line being sung. Full lines are tall, so when one finishes it hands over to the next with an `until` field instead of stacking.
- **During a zoom transition only the target panel keeps its lettering.** Other panels lose theirs, because the zoom would slice their captions at the frame edge.
- **QA checks rendered-frame geometry.** At sampled times it maps every visible word through the zoom `view_box` and the impact-shake crop, and fails if a word is cut within 2 px of the frame edge.
- **Clips play their full length (5-6 s).** Pace pages so the last panel and the zoom land at least about 6.6 s before the page turn. If a clip morphs, mark it `REGEN` and list it in `regen.json` as `[{id, reason, prompt}]`, with a calm, hold-the-pose, in-frame, no-camera-cut motion prompt. Do not trim it to 2-4 s.

### Reviewing regenerated clips (r2, 2026-10-13)
- Name regenerations `<id>_r2.mp4` and keep the originals. Review them with an 8 fps contact strip, then make detail strips at 0.125 s steps in the first second and around any spike in the frame-step metric. Morphs and cross-fades often happen within the first 0.5 s and are missed at 1 fps.
- Use an r2 clip only if it is clean for its full length and its first frame matches the panel. A clip that cuts away from the panel art in its opening frames is a visible jump the moment the panel comes alive.
- If r2 is worse than the old clip, keep the old clip at its clean span, note why in TRIMS, and list the clip in `regen2.json`. Regen prompts should say "opening frame matches the panel image exactly, single continuous shot, nothing appears/vanishes/melts/transforms"; "calm, hold the pose" alone did not stop morphs.
- Neon Dojo r2 result: 7 of 13 were usable (s05, s10, s24, v04, v12, v15, v16). Still bad: s30, v03, v07, v09, s17, v19.

### Round 3 and the character anchor (2026-10-13)
- **The r3 prompts fixed all 6 still-bad clips (s30, v03, v07, v09, s17, v19).** What made the difference: "single continuous shot", "the opening frame matches the panel image exactly", "nothing appears/vanishes/melts/transforms", a held framing, and only small secondary motion (sparks, hair, cloth, lights). Generating two variants (a/b) per id and picking the cleaner one beat a single retry; for v07, r3a still morphed the dummy at 0.1 s, but r3b was clean.
- **Character anchor:** the builder prepends `anchor(chars)` (`ANCHOR_HEAD` + one `ANCHOR_CAST` line per named character in the shot + `ANCHOR_TAIL`) to every motion prompt. The anchor describes each character by name as a good-looking, well-designed robot with its exact face, body, outfit and size, so the video model does not restyle or morph them. Keep the anchors short and reuse the same wording across every prompt and regen list.

### Title logo intro (standing rule, 2026-10-13)
- **Every Progressive Slop video and Short opens with a title logo intro.** It is on by default in `comic_render.py` (`spec.intro`, defaults in `C.INTRO_DEFAULT`). It shows a bold logo of the song title in chunky Bangers lettering, with a chrome bevel gradient on each line, a heavy ink outline, a white keyline and a two-colour neon glow, plus an optional subtitle ("PROGRESSIVE SLOP PRESENTS").
- **Timing:** the logo drops in over 4 frames, from 118% down to 100%, and slams on the first beat at least 0.15 s into the video. The slam brings a white impact flash (0.16 s), a small screen shake (0.32 s, ±0.6% of width, 2% zoom) and star sparkles. The logo holds for `seconds` (default 2.6 s), then fades out over 0.35 s. It is overlaid on the opening panel with a 45% dim; if a song has a long silent lead-in, the slam still waits for that first beat. The Short gets its own intro, slamming on the first beat of the Short window.
- **Config:** `{"intro": {"title": "NEON DOJO", "subtitle": "...", "seconds": 2.6, "glow": [r,g,b], "glow2": [r,g,b], "chrome": [[r,g,b] x6], "subColor": [r,g,b], "rot": -4}}`. If the title is omitted, it is taken from `spec.title` (the part before " - "). In vertical, titles of two or more words split onto two lines.
- **`--intro-test`** writes only `OUT/intro_test_landscape.png` and `OUT/intro_test_vertical.png`; check these before every full render.
- **QA (`check_intro`)** fails if the intro is missing or disabled. It also fails if the logo tile loses any ink against a reference drawn on an oversized canvas (the same padded-canvas, expand=True rotate, crop-to-ink recipe as SFX tiles), or if the logo leaves the title-safe area or is sliced by the frame edge at any frame of the drop-in, shake or hold, in either landscape or vertical.

### Deadstars lessons (2026-10-13)
- **A sky-fight back half works well for escalation.** The first half stays on the ground (arena brawls); from the "lights out" beat on, the fight moves to robot jets in the sky (dogfight, core break, crown descent). That makes a natural climax, and its back half is the right window for the Short. Its risk: video models love to turn jets into standing robots or spawn extra pilots. In Deadstars, 6 of the 14 sky-fight shots grew extra robots in both takes.
- **An explicit "only these characters in shot" clause stops extras.** In every image and motion prompt, name the exact cast and add, for example: "Only Uno and Aura in the shot (plus their two jets); no other robots, no crowd, no pilots, nothing appears." The anchor (`ANCHOR_TAIL`) alone does not stop new characters from fading in; listing who is allowed in the shot does.
- **Edits drift with references, so regenerate from the full text.** Repeated image edits on a reference (an "edit this panel" chain) slowly drift faces, colours and proportions (Aura reading human, Uno getting short). Regenerating from the full prompt text plus the character reference was more reliable than another edit pass.
- **Use a local HSV recolor for costume swaps.** For a colour-only change (for example NULLSTAR purple to black), mask the costume hue range and shift or desaturate it in HSV on the panel. That keeps the art identical and avoids the drift a regeneration brings.
- **Picking takes:** generate 2-3 takes per id, review them all at 8 fps with 0/2/4/5.9 s detail sheets, and pick per id by checking for morphing, extra characters, Aura reading as human, Uno looking short, and text artifacts. Play the pick at near-full length. Flag remaining problems in `FLAG`/`trimNote` instead of trimming them away.
- **Short pages cannot carry a splash zoom.** A page under about 9 s with a zoom-transition splash caps its clips at 2-4 s, or even below zero. Make that panel a regular slot, so every clip still gets about 5.3-6 s.
- **Short cut points:** whisper word boundaries can be back to back, with no gap. When they are, cut exactly on a word boundary (QA allows ±0.03 s).
- **Render audit CLI:** `python3 scripts/comic_render_audit.py SPEC LANDSCAPE.mp4 SHORT.mp4 --out DIR` exits 1 if any caption or SFX is sliced by the frame edge.

### Impact bursts are solid (rule, 2026-10-13)
- **Bursts are never hollow.** The breakout impact burst (the star that breaks out over a splash border behind "BAM!"-style SFX) used to be a cutout of the panel art. Video showed through a black-outlined star, which looked strange. `paint_burst` now fills it solid: an opaque radial white-yellow-orange gradient with halftone dots that grow toward the rim, an ink outline, and the SFX lettering on top.
- **QA (`burst_see_through`)** paints every burst over a black base and over a magenta base and compares the interior (eroded 6 px). If any interior pixel changes, the check fails. It runs for landscape and vertical on every page whose splash uses `breakout`.
- **One lyric per page:** the Deadstars builder letters each lyric line only once per page. Early-landing panels had overlapping lyric windows, so the same line was showing on two panels at once.

# Music mode: design

Status: v1 shipped, plus the actor animation layer and frame-exact capture (v1.1), and the pixel-game style (`shots/kingdom-come-16bit`). Showcase: `shots/kingdom-come-v4` (ProgressiveSlop brand, rigged actors) → `out/kingdom-come-v4.mp4` and the Short `out/kingdom-come-v4-short.mp4`. `shots/kingdom-come` is the older v3 (pose-swap actors).

## Goals

- **Non-sloppy.** Music videos that look art-directed, not like a slideshow with lyrics on top. Every cut lands on a bar, motion breathes with the beat, and lyrics are timed to the actual vocals.
- **Cheap.** No paid models in the loop. 2D vector animation (GSAP + SVG) rendered by headless Chromium, local analysis (librosa) and local Whisper. A 3-minute song renders in minutes on a laptop.
- **Art-directable.** An AI assistant (or a person) writes one HTML stage and a short scene list. Everything about the look lives in plain code that can be diffed, reviewed and tweaked line by line.
- **Storylines, not gag reels.** A recurring cast and a small arc (setup → conflict → payoff) mapped onto the song's sections is what makes these worth watching twice.
- **A party channel.** Fast enough to turn new songs (e.g. Suno tracks) into watchable videos the same day, in 16:9 and as vertical Shorts.
- **Keep narration mode intact.** Music mode is opt-in per shot (a `<name>.music.json` file). Narrated explainers render exactly as before.

2D cartoon is the core for now: cheap, crisp and good-looking. The layer system is designed so video clips and 3D can be mixed in later, when AI video gets cheaper (see *Layers* below), but v1 is focused on polished 2D.

## Concepts

| Concept | What it is |
| --- | --- |
| **Timeline** | `stage/timeline.json` from `scripts/analyze_music.py`: `tempo`, `beats[]`, `downbeats[]`, `bars[]`, `sections[]` (time, end, label, energy), `energy[]` per beat, Whisper `words[]`, aligned `lyrics[]` (line text, tag, per-word times). |
| **Scene** | Same as narration mode (`<section class="scene" id="s-NAME">` + `Webshot.scene`). In music mode a scene starts at a song time: `{ "scene": "verse1", "bar": 15 }` or `{ "at": 26.7 }`. |
| **Storyline** | A recurring **cast** plus **arc beats** mapped to sections, declared in `<name>.music.json` (`storyline.cast`, `storyline.arc`). The arc is the brief for the stage: setup scenes introduce the cast and the stakes; journey scenes escalate; a conflict scene breaks something (ideally on a chorus downbeat); payoff scenes fix it; a coda rolls credits. Choruses are the "chapter headers"; verses carry plot. |
| **Layer** | A depth plane inside the camera. See below. |
| **Preset** | Reusable, beat-aware motion: `slam`, `pop`, `float`, `pulse`, `squash`, `wobble`, `shatter`. |
| **Lyric style** | `karaoke`, `slam`, `ticker`, `comic`. Chosen per line (e.g. choruses slam, verses get comic caption boxes). |
| **Theme** | Genre palette + fonts as CSS variables (`fantasy`, `hiphop`, `synthwave`, `party`). |
| **Format** | `landscape` (1920×1080) or `vertical` (1080×1920 Shorts, ≤60 s cut). |

## Architecture

```
song.mp3 + lyrics.txt
   │  scripts/analyze_music.py  (librosa beats/downbeats/sections/energy + faster-whisper words + lyric alignment)
   ▼
stage/timeline.json ──────────────┐
shots/<name>/<name>.scenes.json   │  (scene → bar / time)
shots/<name>/<name>.music.json    │  (soundtrack, loudness, fades, cut, format, storyline)
stage/index.html  ◄── /kit.js (scenes) + /music.js (clock, hooks, camera, presets, lyrics, comic) + /actors.js (rigged actors, animated backgrounds)
   │  lib/frame-runner.mjs (default: virtual clock, one screenshot per frame, never drops a frame)
   │  or lib/music-runner.ts (--realtime: wall-clock capture through Argo)
   ▼
out/.frames/<name>.mp4 (2× capture, silent)
   │  npm run render: ffmpeg mux — trim to cut, loudnorm to target LUFS, fades, scale to 1920×1080 or 1080×1920
   ▼
out/<name>.mp4   /   out/<name>-vertical.mp4
```

### Clock and sync

**Frame-exact capture (default).** `lib/frame-runner.mjs` installs a virtual clock before any page script runs: `performance.now`, `Date.now`, `requestAnimationFrame`, `setTimeout/setInterval` and all CSS/Web animations run on it. For every output frame it advances the clock by exactly 1/fps, switches scenes at their bar times, and takes one screenshot, piped to ffmpeg. GSAP, the song clock, actor loops and particles therefore get every frame, however heavy the page is (wall-clock capture of the rigged-actor stage only reached ~8 unique fps; frame-exact gives the full 30). Cost: about 0.15-0.6 s of render time per frame on the box (a 3-minute song is roughly 30-50 min). `--realtime` (or `"capture": "realtime"` in `<name>.music.json`) falls back to the old wall-clock recorder.

**Wall-clock capture (`--realtime`).** The recorder starts the capture, then calls `Music.start(start)` and schedules each scene at its bar time against wall time (no accumulated drift). Inside the page, everything reads `Music.time()`; hooks fire from a requestAnimationFrame loop. Durations are expressed in beats (`Music.beats(n)`) so entrances land on beats when a scene starts on a bar. In `npm run check`, `Music.freeze(t)` pins the clock a few beats into each scene so screenshots (and lyrics) are deterministic.

### Analysis (scripts/analyze_music.py)

- Beats and tempo: librosa beat tracker on the onset envelope.
- Downbeats: of the four beat phases, the one with the most onset strength + sub-150 Hz energy.
- Sections: if lyrics are given, sections come from lyric blocks (consecutive lines with the same `[tag]`), snapped to bar lines, with 4+ bar vocal gaps marked `instrumental`. Otherwise agglomerative segmentation of beat-synced chroma+MFCC, snapped to bars and labelled by energy. The audio-only segmentation is kept as `audio_sections` either way.
- Words: faster-whisper (`small.en`) with word timestamps, prompted with the first lyric lines; `condition_on_previous_text=False` because music otherwise makes Whisper drop whole choruses.
- Lyric alignment: songs repeat hooks and skip or change lines, so the lyric sheet is not a script. The aligner walks the *performed* word stream and, at each point, picks the sheet line (reuse allowed, preferring the next one in order) that best matches the upcoming words. The line is shown with the sheet's spelling and Whisper's timing.

### Stage runtime (lib/music-kit.js, served as /music.js)

- `Music.load()`, `Music.start()`, `Music.time()`, `Music.freeze()`.
- Hooks: `onBeat({i, downbeat, energy})`, `onBar`, `onSection`, `onLyric(line)`, `onFrame(t)`.
- Beat math: `beats(n)`, `bars(n)`, `phase()`, `pulse()` envelope, `nextBeat/nextBar`, `quantize(t,'bar')`, `energyAt()`.
- Camera: one `#camera` wrapper; `cam.to({x,y,zoom,rot}, beats)`, `cam.punch()`, `cam.shake()`, `cam.reset()`. Layers with `data-depth` get parallax offsets automatically.
- Particles: `embers`, `sparkles`, `confetti`, `dust`; spawn rate follows the energy curve; `.burst()`.
- Presets: `fx.slam/pop/float/pulse/squash/wobble/shatter` (shatter clones an element into clipped shards; `reverse:true` assembles).
- Safe area: `Music.safe(el)` shifts a comic element back inside its host and the visible viewport (bubbles and captions call it automatically; in vertical Shorts the 16:9 stage is cropped).
- Lyrics: `Music.lyrics({ styleFor(line) → style, hot: /regex/ })`. Words appear at their sung time; hot words are accented; slam words punch the camera.
- Themes: `Music.theme('fantasy')` sets `--m-ink`, `--m-a/b/c`, `--m-paper`, `--m-font`, `--m-sfx`.

### Comic-book style (first-class)

`Music.comic` turns any scene into a comic page:

- **Panels and gutters:** `.c-page` (ink gutter background) with absolutely positioned `.c-panel`s (thick ink border + white keyline). `comic.panels(page, {beats})` reveals one panel per N beats with alternating clip-path wipes.
- **Ink and halftone:** `.c-halftone` overlays a multiply dot screen; `.c-ink` boosts contrast/saturation for photos and stills.
- **SFX lettering:** `comic.sfx(host, 'BOOM', {x, y, size, color, rot, style:'slam'|'pop', beat:true})`: per-letter jitter, stroke + offset shadow, squash-and-stretch landing, a continuous letter wobble, and a pulse on every beat (bigger on downbeats).
- **Speech bubbles and captions:** `comic.bubble()` pops in from its tail and types its text; `comic.caption()` slides in a yellow narration box and types.
- **Lyrics as comic captions:** lyric style `comic` renders the current line in a caption box.

### Layers (and the road to video and 3D)

Every scene is a stack of layers inside `#camera`:

| Layer | `data-depth` | Moves with camera | Typical content |
| --- | --- | --- | --- |
| `bg` | 0.1–0.3 | a little | sky, gradients, stills |
| `mid` | 0.4–0.7 | partly | mountains, buildings, cast at distance |
| `fg` | 1.0–1.3 | fully (or faster) | cast, props, foreground foliage |
| `ui` | none | no | lyrics, captions, SFX, title bands |

Layer contract: an absolutely positioned element with a `data-depth` and 60 px bleed. Anything that obeys it can be a layer, which is the hook for later media:

- **`clip` layer (planned):** `<video data-layer="clip" data-depth="0.3" data-src="…">` whose `currentTime` is slaved to `Music.time()` (seeked each frame), so AI-generated or stock clips stay frame-accurate with the song and the camera. v1 can already drop a looping `<video>` into a layer (the old Suno showcase did); slaving is the missing piece.
- **`3d` slot (planned):** `<canvas data-layer="3d" data-depth="0.6">` driven by a small adapter (three.js) that reads `Music.cam` each frame and maps x/y/zoom to a perspective camera, and that subscribes to `onBeat` for animation. Same hooks, same depth semantics, so a scene can mix 2D cutouts in front of a 3D set.

### Formats

`npm run render -- <name> --format vertical [--start s --end s]` records the stage at 720×1280 (×1.5 = 1080×1920). Stages reflow with `html[data-format=vertical]` CSS: a title band on top, the 16:9 action in the middle (cropped to the center, or comic pages scaled to fit), lyrics below. The `shorts` block in `<name>.music.json` stores the chosen hook window (≤60 s; pick the section with the most energy and a complete story beat).

### Audio

The original track, never re-voiced: trimmed to the cut, `loudnorm` to the shot's target (default −14 LUFS for music), 48 kHz AAC 256k, short fade-in on cuts that don't start at 0 and a fade-out at the end.

## Asset sourcing and channel style

A **channel** (e.g. Progressive Slop) is a folder: `channels/<channel>/` with a style guide, a song index synced from Suno, and imported art.

```
channels/progressiveslop/
  style.json            # channel style guide (palette, fonts, line weight, motifs, do/don't, references)
  songs.json            # index of synced songs, newest first
  songs/<suno-id>/      # song.mp4 (Suno video), song.m4a (audio), cover.jpeg, lyrics.txt, meta.json (+ style.json override)
  imagine/              # Grok Imagine imports: images and clips + manifest.json
```

1. **Suno is the source of truth.** `npm run suno:sync -- @progressiveslop` (or a song id / profile URL) reads the public profile and song pages and pulls each song's video, audio, cover, lyrics and tags from Suno's CDN by song id. Each song's `meta.json` stores a content hash; re-running the sync re-pulls only songs whose page changed (new title, lyrics, tags or media), so it can run on a schedule. The public `.mp3` URL is usually 403, so audio is extracted losslessly from the song's `.mp4`.
2. **Grok Imagine is the second source,** imported through a folder + manifest for now: drop images/clips into `channels/<channel>/imagine/` and list them in `manifest.json` (`{ "file", "kind": "image|clip", "prompt", "tags", "songs": [ids], "use": "background|character|cover|clip" }`). Shots reference them as stills, parallax plates, or (later) `clip` layers. An API importer replaces the manual step when one is available.
3. **New art must match the channel.** `style.json` is the brief for anything the bot draws or generates: palette (hex), outline weight and color, shading style, typography (title, SFX, lyric fonts), recurring motifs, framing rules, and `references` (paths to existing covers/Imagine pieces that define the look). A song can override it (`songs/<id>/style.json`, e.g. a palette sampled from its cover). Music shots load the channel/song style into `Music.theme()` so SVG casts, lettering and generated prompts share one look; prompts for image/video models are built from `style.json` + the song's tags and lyrics.

## Asset prep (before animating)

Asset quality is the bottleneck, so assets get their own approved stage between storyline and animation:

1. **List.** From the storyline, write `channels/<channel>/assets/<shot>/manifest.json`: every cast member (neutral pose + 2-4 expressions/poses each), 4-5 wide backgrounds, and key props. Each entry carries its generation prompt, style references, output paths and a `status`.
2. **Generate in style.** Prompts are built from the channel `style.json` (palette, line, proportions, mood) + the song cover as a reference image. Characters are generated full-body on a plain flat background in a neutral 3/4 pose; backgrounds are wide (21:9) and composed in separable depth bands (sky / far / mid / foreground) so they can be layered. Use the highest quality setting; keep seeds/references fixed across a cast so they match.
3. **Cut, rig and layer.** Character sheets → one transparent PNG per pose with `python3 scripts/cutout_sheet.py sheet.jpg --count 4 --names a,b,c,d -o cutouts/<who>` (splits on background gaps, rembg isnet + alpha matting, largest-blob cleanup, trim). Grids: `--rows 2 --count 3`. Crowded line-ups where figures touch: `--boxes "x0,y0,x1,y1"` per figure plus `--erase` rectangles for a neighbour's overlap, and `--model birefnet-general` for chrome-on-grey (isnet loses chrome against grey backgrounds). Small sheets: `--upscale 2`. Run one figure per process with birefnet (it needs ~4 GB). Then rig every cutout: `python3 scripts/rig_actor.py cutouts/*.png -o rig.json --overrides rig.overrides.json` (eyes, headphones, neck, shoulders, hip, feet, spell glow; fix any wrong guess in the overrides file and re-run). Brand fixes are scripted too (`scripts/pendant_one.py` stamps Uno's gold "1"). Backgrounds → light maps: `python3 scripts/bg_lightmap.py bg-<place>.jpg -o layers/bg-<place> --keys red,cyan,purple,magenta,white` writes one glow PNG per colour family (only the glowing pixels, on black) and `<place>.fx.json` with sparkle points; the stage screen-blends and pulses them (see *Actor animation layer*). Optional far/near band split for parallax as before. Each output is listed in the manifest.
4. **Approve.** Render a labeled contact sheet of every asset; a human approves or asks for re-rolls per item (`status: approved | reroll`). Nothing is animated until the set is approved and visually consistent.
5. **Animate.** Stages turn the approved cutouts into rigged actors (`/actors.js`) and the backgrounds into animated plates, with the same music runtime, presets and comic style.

## Actor animation layer (lib/actor-kit.js, served as /actors.js)

The v3 lesson: pose swaps on the beat read as "jerking around stills". Every character on screen must be alive all the time, each running its own loops, independently and offset, with poses mixed in as accents.

**Rig, not cut.** Each actor is one cutout drawn by WebGL on a 24×32 vertex mesh. From the rig points the vertex shader derives smooth per-vertex weights, so parts move independently with no seams:

| Part | Weight | Motion |
| --- | --- | --- |
| head | above the neck, near the head column | bob, tilt, nod (rides on the breathing torso) |
| chest/torso | neck → hip | breathing (stretch up from the hip, chest widens) |
| arms + cape/robe edges | outside the torso column, shoulder → hip | rotate about left/right shoulder pivots |
| hem (cape, gown, robe) | hip → feet, growing to the feet | travelling sine wave + flare |
| hair | beside the head, head → hip | wave with lag (Aura) |
| wings | upper back (dragon) | flap |
| whole body | from the feet | lean, rock |

The fragment shader adds a chrome glint sweep (each actor on its own 8-beat cycle), a sword gleam limited to the blade (`gleamTop`), hit flashes and a beat-reactive rim light. A 2D overlay canvas per actor draws light: eye glow (slow pulse, flares on accents, deterministic blinks every 2.4-5.5 s per actor), headphone pulses on the actor's own beat, staff orbs, and stateless spiral magic particles at the rig's spell point. A JS twin of the head transform keeps eyes and headphones locked to the warped head.

**Independence.** Every parameter is a pure function of the song clock, so frozen check frames are deterministic and capture is frame-exact. Each actor has a `seed` (phase) and `sub` (beat subdivision: Uno nods on half-time, Aura on quarters, the jester on eighths); the beat envelope is quantized to 16ths per actor, so actors hit at different points of the beat but stay on the grid. Beat envelopes have a short eased attack, so big mesh moves never snap in one frame.

**Named animations** (`Actors.anims`, add your own with `Actors.addAnim(name, fn)`), layered on top of the always-on `idle` (breathing, micro head bob, slow cloth sway, blink): `groove`, `walk` (step bounce, lean, alternating arm swing, rock), `cheer`, `react` (decaying shudder), `attack` (anticipation → lunge → recover, blade gleam), `cast` (arm pulses, magic particles, eye glow), `dance`, `twirl`, `menace`, `bounce` (jester), `gallop` (horse), `hover` (dragon, wings), `sleep` (eyes dim), `guard`, `flex`. Short additive accents: `Actors.accent(a, 'flare'|'recoil'|'nod'|'flex'|'shiver', beats)`.

**Pose-to-pose.** `Actors.transition(a, pose, { smear: 'up'|'left'|'right'|'spin'|'none' })`: anticipation squat → swap with a fading, stretched ghost of the old pose + comic speed lines → elastic overshoot. `Actors.hop()`, `Actors.flash()`, `Actors.impact(host, x, y, {text})` (comic star burst + lettering), `Actors.anchor(a, 'chest'|'head'|'feet')`.

**Mix and match per moment.** The scene plan picks, per character and per beat of the story, a loop (`a.play('walk')`), a pose (`Actors.transition`) and accents, e.g. Uno `attack` + sword pose while the knights `react` and Aura `cast`s, each on its own phase.

```js
await Actors.load('assets/cast/rig.json'); Actors.start();
Actors.define('uno', { poses: { stand: 'uno-stand', sword: 'uno-sword' }, sub: 0.5, gleamTop: { sword: 0.3 } });
const uno = Actors.actor(castEl, 'uno', { x: 430, y: 615, h: 430, pose: 'stand', seed: 0.1 }).play('groove');
tl.add(() => { Actors.transition(uno, 'sword', { smear: 'up' }); uno.play('attack'); }, AT(34.9)); // on the lyric
```

Call `Actors.clear()` when a scene starts (frees the WebGL contexts; Chrome keeps ~16).

**Animated backgrounds.** `Actors.bg(plateEl, '<place>', opts)` loads the plate, its glow maps and sparkle points: `glow: [keys]` screen-blended and pulsed (`pulse: 'beat'|'bar'`), `shimmer: [keys]` (a moving mask sweep, e.g. fountain/crystal light), `twinkle: [keys]` (star glints on the brightest points), `fountain: {x,y}` (rising droplets), `lasers: [{x,y,from,to,color,beats}]` (beat-synced sweeps), `disco: {x,y}` (spinning ball + floor spots), `eyes: [[x,y]]` (a big creature's eyes flaring on downbeats). Coordinates are source-image pixels.

**QA for motion.** Besides the check sheet, render a few seconds and sample consecutive frames: crop one actor, diff frame n vs n+k (`ImageChops.difference`), and confirm that the head, arms/cape and hem light up differently and that no frame is a duplicate (`ffmpeg -vf mpdecimate` should keep ~all frames). When extracting frames with `select`, add `-fps_mode vfr` or ffmpeg duplicates them.

## Pixel game style (16-bit sprites)

Worked example: `shots/kingdom-come-16bit` (Kingdom Come as a SNES-era side-scroller). Use it when the art set can't carry rigged animation: cut-out stills warped into motion look janky (the v4 lesson), while frame-by-frame sprite loops are native to pixel art. Work within what the frames can do.

- **One low-res canvas.** The stage is a single `<canvas>` at the internal resolution (480x270; 270x480 for Shorts) with `image-rendering: pixelated` and `imageSmoothingEnabled = false`, redrawn every frame from `Music.time()`. Scenes are time-driven from bar times; the `<section>` stubs exist only so `npm run check` sees the scene list.
- **Integer capture.** `"pixel": {"w": 480, "h": 270, "lowres": true}` in `<name>.music.json` makes `lib/frame-runner.mjs` use the internal size as the viewport with an integer device scale (4x → 1920x1080 / 1080x1920), PNG frames, and the final mux scales with `flags=neighbor`. Every art pixel is an exact 4x4 block.
- **Rules:** all positions `Math.round`ed; no rotation, sub-pixel moves, blur or scaling on sprites (mirror with `scale(-1,1)` only for symmetric characters; never mirror text or logos like Uno's "1"). Alpha only for flat full-screen flashes/tints.
- **Sprites from a reference sheet** (`scripts/pixel_sprites.py`): chroma key against the corner colour with a 2 px matte erosion (kills the magenta fringe), crop per frame (cut columns from the column-coverage minima), premultiplied box downscale to ~60 px tall, hard alpha, one shared median-cut palette (+ exact brand colours), despeckle tiny islands, 1 px dark outline. Extra loop frames by pixel edits (`shift_rows`, `shift_region`: foot lifts, off-beat squash of the upper body). NPCs are derived from the same reference frames so they match the heroes' detail level: re-sample a hero frame at the NPC's size, recolour by hue (cloak/gown/gold → the NPC's colours, skipping the top of the head so red eyes stay red), and add small shaded pixel accessories (wizard hat + staff, jester hat + bells, knight plume + spear, sorcerer horns + orb staff); crowd = 2 mini designs x palette variants. Hand-drawn primitive NPCs looked Atari-crude next to the painted backgrounds; don't ship blob figures. `pack()` writes an atlas + json (anchor = bottom centre).
- **Loops:** each animation has a fixed fps (8-12) or is beat-locked (`spr(..., {beat: 2})` = 2 frames per beat, so an 8-frame dance is one bar). One-shots (`slash`, `cast`, `spark`) take `{t0, once: true}`. Different seeds/phases per character so nobody moves in lockstep.
- **Backgrounds:** painted plates downscaled to 480x270 and quantized (no dither); split at the floor line into a far band (0.35x) and a near band (1x), each mirror-tiled for seamless scrolling, plus a procedural silhouette foreground at 1.6x.
- **Game feel kit:** bitmap font (Press Start 2P rendered 1-bit at 8 px into a strip), RPG text boxes for verse lyrics (typed per sung word), arcade 2x text for chorus lines, `STAGE n` cards for one bar, HUD (1UP/score/HI), health bars, white hit flash (`source-in` white atlas), integer screen shake, spark bursts, arcade title (INSERT COIN → coin lands on a downbeat → CREDIT 1 → PRESS START) and THE END + credit.
- **Shorts:** draw the world into an offscreen 480x270 canvas and blit a 270x270 centre crop into the vertical screen (logo band on top, lyrics below). Keep the action in world x 105-375.
- **Review:** sample consecutive frames of one character (`select=between(n,a,b),crop,tile`) to confirm the loop advances; zoom a crop with `flags=neighbor` to confirm 4x4 blocks and no fringe.

### Speed and quality notes (from the 16-bit pass)

- **Where the time went** (box, 8 cores): asset build `build_assets.py` 2.5 s; `npm run check` 11 s; full 170.8 s song = 5124 frames at ~0.11 s/frame ≈ 10 min with 4x capture (1920x1080 PNG screenshots dominate; canvas drawing is ~free); the 44 s Short ≈ 2.5 min. The mux (loudnorm + x264 slow) adds ~30 s. Most wall time was spent on re-renders after fixes, so review stills first.
- **Low-res capture (done):** `"pixel": {"w":480,"h":270,"lowres":true}` screenshots at 1x (480x270), stores the intermediate lossless yuv444 (`-crf 0`), and the mux upscales once with `flags=neighbor`. Byte-identical-looking output; a 10 s test went from ~41 s to ~19 s (≈2.2x). Default for pixel shots.
- **Stills before renders:** freeze the song clock at chosen times in a 480x270@4x page and screenshot (`node shots/kingdom-come-16bit/tools/stills.mjs <outdir> label=seconds ...`: `Music.freeze(t)` + `page.screenshot`). 11 review frames take 4 s; use them for previews and approvals instead of test renders.
- **Reusable for the next song:** `scripts/pixel_sprites.py` (key/crop/downscale/palette/outline/despeckle/pixel edits/atlas/bg bands); the hero sprite rig (cut columns + anim lists) and NPC recipes (recolour + accessories) in `build_assets.py`; the stage kit in `shots/kingdom-come-16bit/stage/index.html`: `spr()` (fps/beat/once), bitmap font + `logo()`, RPG `box()`, lyrics (box for verses, arcade for choruses), `hud()`, `hpBar()`, `stageCard()`, arcade title with coin drop, `scrollScene()` encounters, boss fight, STAGE CLEAR, THE END. Next step: lift these into `/pixel.js` so a new song only writes a scene table and an encounter list.
- **Quick wins not done yet:** cache the sprite atlas between songs (rebuild only when the reference sheet hash changes); parallel chunk renders (split at bar lines into N `--start/--end` segments, render concurrently, concat the silent intermediates, then one mux; the virtual clock makes chunks deterministic); render landscape and Short concurrently (done by hand here; 2 jobs ran at nearly full speed each).
- **Quality checks that caught real bugs:** consecutive-frame strips per character (a dance that held one pose per beat), a neighbour zoom crop (magenta matte fringe → 2 px erosion), the vertical crop band (boss and HUD were outside x 105-375), and a full-res still per stage (a BONUS STAGE stamp overlapping STAGE CLEAR).

## Chorus routine (the recurring hook)

Every chorus cuts (on a bar line, usually for the chorus's last 4-6 bars) to the **same** signature group dance: same stage, same lights, same title stamp ("official chorus routine #n"), same 4-beat move. Repetition is the point; viewers learn it by chorus 2 and wait for it.

- **The move (4 beats, loops per bar):** beat 1 = group DANCE pose + kick (hop + tilt) + camera punch + spotlights swing; beat 2 = ALT pose + mirror flip; beat 3 = DANCE pose, flip back, small hop; beat 4 = ALT pose + squash. Poses come from the asset set (one shared group-dance image cut per character + each character's happiest pose as ALT).
- **Running gag:** one cast member (the villain) changes participation each chorus: refuses → taps once per bar → does only the downbeats → dances fully while denying it → front and center loving it. Each chorus also gets one new line (bubble) and at most one new prop, nothing else changes.
- **Story context:** the routine can reflect story state (cracked drum still dancing, villain dancing in his cage), but the move itself never changes.
- **Shorts:** build the vertical cut around one or two routines; the routine is the most re-watchable part.
- **Progressive cast (v4 variant):** instead of a villain gag, the cast joins one or two at a time (#1 Uno + Aura, #2 + Jester, #3 + Wizard + Knights, #4 + Dragon + Horse, #5 everyone, the reformed villain front and center). The leads do the 4-beat move with smear transitions; everyone else keeps their own loop at their own phase and only shares the downbeat hop.
- Implementation: `routine(n)` in `shots/kingdom-come-v4/stage/index.html` (and v3's in `shots/kingdom-come`), scenes `dance1..dance5`, driven by `Music.onBeat` with a beat-in-bar counter.

## Pipeline (how an assistant makes one)

0. `npm run suno:sync -- <song-id>` to fetch the song, cover and lyrics into `channels/<channel>/songs/<id>/`.
1. `npm run new -- <name> --music song.mp3 --lyrics lyrics.txt` → copies the song, runs the analysis, writes `timeline.json`, one placeholder scene per section, and `<name>.music.json`.
2. Read the lyrics and the section list; write the **storyline** (cast + arc) into `<name>.music.json`.
2b. **Asset prep** (see above): list → generate in style → cut/layer → approve.
3. Use the approved cutouts as rigged actors (`/actors.js`, see *Actor animation layer*; worked example `shots/kingdom-come-v4/stage/index.html`). Every character on screen runs its own loop; poses are accents with smear transitions. Hand-drawn SVG cast is the fallback when no asset set exists.
3b. Build the **chorus routine** once and play it in every chorus (see below).
4. Build scenes: choruses as big beat-driven set pieces (comic splash pages, slams), verses as plot (parallax pans, panels, bubbles). Put entrances on beats (`B(n)`), cuts on bars.
5. `npm run check -- <name>`; review the contact sheet (lyrics are frozen a few beats in).
6. `npm run render -- <name>`; sample frames at known word times to confirm sync.
7. `npm run render -- <name> --format vertical --start … --end …` for the Short.

## Roadmap

- **v1 (now):** soundtrack mux, beat/bar/section/energy timeline, Whisper lyric alignment, runtime hooks, camera/parallax/particles/presets, lyric styles, themes, comic style, vertical format, `new --music`.
- **v1.1:** ✅ frame-exact capture (virtual time); ✅ actor animation layer (rigged mesh actors, light overlays, named animations, smear transitions, animated backgrounds); ✅ comic safe-area clamp (`Music.safe`, used by bubbles and captions, so Shorts never clip them); per-word lyric editing file (`lyrics.fix.json`); automatic Shorts window picker (energy × lyric density × arc beat).
- **v1.2:** lip-flap / visor glow from vocal energy; arm rigs from per-pose masks (true limb pivots instead of side weights); cast library with poses and mouth shapes; reusable backdrops (castle, city, beach, space).
- **v2:** `clip` layers slaved to the song clock (AI video, stock); a `3d` layer slot with a three.js adapter; stem separation (demucs) for drum-locked vs vocal-locked motion.
- **v1.1 (sourcing):** scheduled `suno:sync` for whole profiles; Grok Imagine importer; palette sampling from covers into per-song `style.json`.
- **Later:** a "party channel" batch mode: drop a folder of Suno songs, get drafts of both formats with storyline suggestions for review.

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

## Fighting-game shots (SF2 style): `stage/fight.js` + fighter QA

First used by `shots/neon-dojo-fighter`. The game logic is a pure script, `stage/fight.js`, that sets `globalThis.FIGHT`. It is shared by the page and by `scripts/fighter_qa.mjs`, and `npm run check` runs that QA whenever `stage/fight.js` exists.
- **`FIGHT.build(timeline)`** returns `scenes` (contiguous, each starting on a downbeat), `fights`, `sceneAt(t)`, `fighterAt(fight, side, t)`, `hud(fight, t)` and `fx(fight, t)`. Every one of these is a pure function of the song clock.
- **Fights** are lists of *exchanges*. Each event is `[sec, side, move, result, dmg]`, snapped to beats; `result` is `hit`, `block`, `ko` or `ko_down`.
  - The opponent (side 2) swings in every exchange, and lands at least one hit in every full fight.
  - At most 3 hits connect per bar.
- **Sprite-state machine** priority: KO > victory > hit > block > attack > walk (approach and retreat) > idle-breath.
  - Hit-stop (4 frames, or 6 on a special or KO) warps the animation clock, not the song.
- **HUD:** SF2 bars with a white damage trail (lags 0.45 s, then drains over 0.35 s), a 99 timer counting down one tick every 2 beats, round pips, and banners (ROUND n / FIGHT! / K.O. / YOU WIN / PERFECT).
- **FX:** 3-frame sparks (small, big, block), screen shake of 2–4 px, a combo counter (connecting hits by the same side within 1.4 s), a super cut-in band with speed lines (single or double), and a two-colour palette-invert freeze frame.
- **Placeholder figures:** `poseRects(char, anim, frame)` builds the shared-master figure from rects.
  - The core (torso, belt, head, eyes) is identical in every frame up to translation; the limbs come from per-pose foot and hand targets solved with two-bone IK.
  - Feet are 3 px soles whose bottom row is the anchor row, and shins are clipped so they never poke through.
  - The real per-pose art replaces `poseRects` with atlas frames built the same way.
- **Montage-only fighters** have a lean move set (`FIGHT.MOVESET.montage`: idle / attack / hit / KO); the engine maps any other move onto those.
- **The Short** is laid out as three bands: the HUD band on top, a 270×270 crop of the fight in the middle (world x 105..375, so keep fighters inside it), and portraits plus the lyric line at the bottom.

**QA (`scripts/fighter_qa.mjs`)** fails on:
- canvas `fillText` / `strokeText` / `ctx.font`, web fonts, or DOM text (the HUD must use the bitmap font);
- identical consecutive frames in any animation (including the loop wrap);
- a master core that differs between frames;
- a fighter whose lowest pixel is more than 1 px off the stage ground (sampled at 30 fps across every fight; only `ko_fall` may be airborne);
- an idle frozen for more than 0.6 s;
- a montage fighter using a move it has no art for;
- an exchange without an opponent attack, or a full fight where the opponent never lands a hit;
- more than 3 hits per bar;
- scenes off the downbeats.

### Real fighter art (`uno_sprites.py`, first used for Uno in neon-dojo-fighter)
- Source is one JPG per ASSET_LIST pose on #00FF00, in `channels/progressiveslop/assets/<shot>/source/<char>/`.
- **Keying:** key the green, despill the edges, and keep only the large connected components.
- **Landmarks:** head top, belt (the widest gold row), and the lowest pixel.
- **Scale normalisation** uses the head width, since the round chrome head is rigid. The head-to-belt span is NOT used: leaning poses (kicks, hits) shrink it and over-scale by about 20%.
- **Master upper body** (idle_a's head and torso) is pasted on the idle and walk frames, aligned on the belt. Block gets the master head only. Attacks, hit, KO and victory stay whole poses.
- **Breathing idle:** idle_a with the upper body raised 1 and 2 px, with the belt rows stretched so nothing tears.
- **Scale and palette:** downscale with a box filter to the 960x540 world (Uno is about 198 px tall, i.e. 2x2 blocks at 1080p), then apply one shared 56-colour palette and a dark outline.
- **Anchors:** the anchor is (belt x, sole row), so the ground row is exact. Walk bob comes from the art's hip heights (`bob` in the atlas json).
- The engine logic stays in 480x270 coordinates, drawn ×2. Sprite characters are listed in `FIGHT.SPRITE_ANIMS` and drawn from `stage/assets/px/<char>.png/json`. The QA checks atlas anchors, consecutive poses, master identity ≥97% and walk silhouette change, and prints the art flags.
- **Per-character settings** live in the `CFG` dict in `uno_sprites.py`: which frames get the master, mirrored poses, target height, and the belt landmark (`gold` belt, or `waist` for outfits without one, e.g. Aura's gown).
- **Baked-in energy** (cyan pixels with low red and high green and blue, plus the white-hot cores within 4 px of them) is pulled out of the body into a separate `fx` layer for each pose. The engine draws that layer additively with a 3-step flicker, so it reads as an effect and never counts toward the body's silhouette or ground row.
- **`strip` poses** have the haze deleted instead, and chrome tinted by the haze is pulled back to neutral grey.
- **Clipping guard:** every atlas cell has a 3 px transparent margin (`cell_pad`). `fighter_qa` fails when:
  - any opaque body or fx pixel touches its cell edge;
  - the source art touches the image border (`source_cut`, meaning regenerate);
  - a drawn sprite (body + fx) leaves the 960x540 screen in a fight.
  `tools_gifs.py` sizes the canvas from body AND fx extents, and aborts if anything lands on the canvas edge.
- **TEKKO CFG options:**
  - `belt='dark'`: the longest contiguous near-black run (the mawashi), with x at the centre of that body segment.
  - `core='full'`: the whole upper body, including the guard arms, as the master for wide bodies.
  - `legswap`: the lower body mirrored about the hip, for identical L/R walk sources.
  - `ghost`: green-cast afterimages become a grey-cyan fx layer.
  - `spark`: baked-in hit sparks removed.
  - `synth`: e.g. ko_fall made from hit, rotated back 40°.

**VS portraits + super cut-ins.** `shots/neon-dojo-fighter/portraits.py` keys and despills the busts (#00FF00, facing left) into `portrait-<c>.png` and scales the 16:9 cut-ins into `cutin-<c>.png`. `portrait()` contain-fits a bust into a slot and mirrors the left-side fighter. A fight's `super: [t, who]` holds the world still for `FIGHT.HOLD` (0.1 s), then shows a `FIGHT.CUTIN` (0.65 s) band of the cut-in art. Sparks, shake and the combo counter are suppressed during the band. QA checks that the portraits are non-empty with no green fringe, and that each cut-in appears at its cue, ends on time, and comes right before that fighter's special.

**Background figures rule (all stages, default).** Every animated background figure (crowd robots, monks, spectators, anything that bobs or moves) is cut out *individually* and the stage is rebuilt on an *inpainted clean plate*. `build_assets.build_stage(key, src, cfg)` does this for every stage: `figure_boxes` (where figures stand), `static` (statues that must stay), `occluders` (railings drawn over the figures from the original art), `figure_layer`/`figure_speed`. It finds the figures, splits merged blobs, makes exclusive masks, inpaints the plate under them, and writes `stage-<key>-fig<i>.png` with `figures: [[x, y, w, h, phase]]` and `plate: true` in `stage-<key>.json`. The page draws each figure 1 px up on its beat (alternate figures alternate beats). Never bob a whole band. `fighter_qa.mjs` checks every stage json on every run: no band bobs, `plate: true`, a figures list, real masks (not rectangles), the plate under each figure no longer showing it, and no two masks overlapping. Channel setting: `style.json` → `stage_rules.figure_cutouts: "individual"`.

## Comic mode (comic-book music video, not a game)

A song becomes a sequence of comic **pages**. Panels land one at a time on beats, separated by
paper gutters with black ink borders. Each panel holds as still art, then its short Grok Imagine
clip plays *inside the frame*, then it freezes on the clip's last frame. A zoom into a panel
(landing on a downbeat) hands over to a full-frame **splash** for the big hit. Paper grain and a
light halftone sit over everything so 480p clips blend with the 720p+ art; lettering is Bangers
(SIL OFL; `fc-match Bangers`, else downloaded to `~/.cache/webshots/fonts`).

Files: `scripts/comic_lib.py` (layouts, registration, texture, lettering, frame builder),
`scripts/comic_render.py` (MP4s + contact sheet), `scripts/comic_qa.py` (QA). Example scene:
`shots/neon-dojo-comic/neon-dojo-comic.comic.json`.

```bash
npm run comic -- neon-dojo-comic [--out /path/to/out] [--only landscape|vertical] [--short full|cut]   # cut = spec.short {start,end}
npm run check -- neon-dojo-comic      # comic QA (no stage needed)
```

Outputs never overwrite (`-v2`, `-v3` …): `comic-scene-1080p.mp4` (1920x1080), `comic-scene-short.mp4`
(1080x1920; the same spec re-flows into three stacked 16:9 slots + a 1000x1120 splash),
`comic-scene-sheet.png`. Audio is the spec's song section, 30 ms fade in / 0.6 s fade out,
two-pass loudnorm to `song.loudness` (-14 LUFS, TP -1.5).

### Full-song workflow

1. **Timeline.** Use the song's `stage/timeline.json` (`scripts/analyze_music.py`: beats, downbeats,
   sections, timed lyric lines). One comic scene = one section or 8–12 bars (~12–15 s); 3–4 panels per
   page, the last one goes splash on the section's hit.
2. **Panels** (image model, one fixed style prompt for the whole song, 16:9, **no text in the art**;
   all lettering is added by the renderer so it stays sharp and editable). Style prompt template:

   ```
   {SHOT} of {CHARACTERS + ACTION}, {SETTING}. 1990s American superhero comic book panel,
   bold black ink outlines, heavy spot blacks, cel-shaded flat colour with halftone dot shading,
   dynamic foreshortening, speed lines, dramatic {LIGHT, e.g. neon magenta and cyan rim light},
   early-90s comic energy, 16:9 panel, full bleed.
   NO text, no lettering, no speech balloons, no sound effects, no logos, no signatures, no panel borders.
   Characters: {CHARACTER SHEET LINES, identical every panel}.
   ```
   Keep `{CHARACTER SHEET LINES}` byte-identical across the song (costume, colours, helmet, props).
3. **Clips**: Grok Imagine image-to-video from each panel, **480p, shortest duration (6 s)**. Small,
   readable motion only; the camera mostly locked so the clip lines up with the panel. Motion prompt template:

   ```
   Animate this comic panel. {ONE ACTION, e.g. "the fist drives forward and the impact burst flares"}.
   Subtle secondary motion: {hair / cape / rain / sparks / neon flicker}. Camera: locked off
   (or a slow push-in). Keep the exact comic art style, ink lines and colours, keep faces and hands
   unchanged, same number of arms and fingers, no new characters, no morphing, no text, no cuts.
   ```
4. **Review each clip** (`ffmpeg -i c.mp4 -vf "fps=2,scale=368:-1,tile=4x3" -frames:v 1 sheet.png`): the
   first ~2 s are usually clean; later seconds tend to melt faces, sprout extra limbs, or re-frame.
   Pick the best **1.5–2.5 s** (`in`/`out`, hard max 3 s). If no window is clean, leave the panel static.
   **Hold rule (Jason):** a clip starts almost immediately after its panel lands: hold the still for at most
   one beat (~0.3–0.5 s), then the motion plays. Leave `clip.at` out and the renderer starts the clip
   `defaults.holdBeats` (default 1) beats after the landing; QA fails if clip start − panel land > 0.6 s or < 0.25 s (keep the anticipation beat).
   **Every panel is a different scene:** vary the location, camera angle and moment for each panel; never
   reuse a composition. Keep it playful and kid-friendly with small humour beats.
5. **Spec** (`shots/<name>/<name>.comic.json`); all `at` values are song seconds on the beat grid:

   ```jsonc
   {
     "assetsDir": "/path/to/panels-and-clips",          // or env COMIC_ASSETS
     "fps": 30,
     "song": { "audio": "shots/x/stage/assets/song.m4a", "timeline": "shots/x/stage/timeline.json",
               "start": 108.042, "end": 122.137, "loudness": -14 },
     "panels": [{
       "id": "p1", "image": "panels/p1.jpg", "slot": "top-left",   // top-left | top-right | bottom
       "at": 108.042,                                               // beat the panel lands on
       "focus": [0.5, 0.5],                                         // crop centre when the slot aspect differs
       "clip": { "src": "clips/c1.mp4", "in": 0.0, "out": 2.0 },  // optional; "at" defaults to 1 beat after landing
       "lyric": "(Woman) Count it out, one by one",
       "captions": [ { "text": "COUNT IT OUT, ONE BY ONE", "anchor": "br", "at": 109.738, "lyric": true } ],
       "sfx": [ { "text": "SHIIING!", "at": 110.179, "pos": [0.52, 0.32], "rot": -8, "size": 0.17, "color": [255,70,60] } ]
     }],
     "transition": { "type": "zoom", "panel": "p3", "at": 118.306, "dur": 0.418 },  // at = landing downbeat
     "splash": { "image": "panels/p3.jpg", "clip": { … }, "captions": [ … ], "sfx": [ … ] }
   }
   ```
   A whole song uses `"pages": [{ "id", "start", "end", "panels": [...], "transition"?, "splash"? }]` with the
   same panel fields (one page per section; a page may skip the splash). Add `"location"`, `"camera"`,
   `"moment"`, `"scene"`, `"prompt"`, `"refs"`, `"motionPrompt"` per panel at planning time; `"draft": true`
   marks a plan whose art isn't generated yet (QA checks timing/text/uniqueness and reports missing media;
   the renderer refuses drafts). `"outName"` sets the output file prefix. Example:
   `shots/kingdom-come-comic/kingdom-come-comic.comic.json`.
   Lyric lines go in caption boxes (one per panel; an optional narration box like "NEO-TOKYO. MIDNIGHT."
   on the opening panel). One SFX per panel at most, on the beat of the action.
6. **Render + check**: `npm run check -- <name>`, then `npm run comic -- <name>`; look at the contact sheet.
   For a whole song, render each scene and concatenate (each scene's audio is its own song slice, so cut
   scenes edge to edge on the section boundaries).

### How it renders (restraint rules)

- Static hold: one beat, then the clip. Panel entrance: 0.14 s fade + 16 px drop. SFX: a 3-frame stamp (1.25x → 1x), then still. Static →
  clip: 3-frame crossfade. One zoom per page. Nothing shakes, flashes or stacks.
- Clip → panel alignment: Grok re-frames to 736x400, so each clip's first frame is registered onto its
  panel (scale + offset search, NCC). The slot crop is kept inside the clip's coverage and the same crop
  is used for still and clip, so the hand-off doesn't jump.
- Clips: lanczos upscale + light unsharp (r 1.6, 55%), then halftone (45°, 7 px cell, dots grow in
  shadows, 22% strength) + paper grain. Ink borders are drawn after, lettering last.

### Comic QA (`scripts/comic_qa.py`, part of `npm run check`)

- clip `in`/`out` inside the source duration, `out > in`, length ≤ 3 s;
- 0.25 s ≤ clip start − panel land ≤ 0.6 s (the one-beat anticipation hold);
- every panel a different scene: fails on two panels with near-identical prompts (content-word Jaccard
  ≥ 0.6 on `scene`/`prompt`), the same `location` + `camera` pair, or near-identical images
  (64-bit DCT pHash, Hamming ≤ 10; a splash reusing its own panel art is allowed);
- every landing / clip / caption / SFX / transition time within 60 ms of a beat;
- captions + SFX inside the frame and not overlapping while on screen (landscape and vertical);
- no black or empty slot at sampled frames (std, mean and % near-black per visible slot);
- each clip registers on its panel (NCC ≥ 0.75, scale 0.9–1.1) and the first used frame is not re-framed
  (> 3% shift fails); large content change in the used frames is a warning (expected for impact bursts).

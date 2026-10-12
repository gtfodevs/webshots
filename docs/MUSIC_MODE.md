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

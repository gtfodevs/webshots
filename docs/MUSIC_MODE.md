# Music mode: design

Status: v1 shipped (this branch). Showcase: `shots/kingdom-come` → `out/kingdom-come.mp4` and the Shorts cut `out/kingdom-come-vertical.mp4`.

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
stage/index.html  ◄── /kit.js (scenes) + /music.js (clock, hooks, camera, presets, lyrics, comic)
   │  lib/music-runner.ts  (Playwright: starts the song clock and the recording together; schedules cuts on wall time)
   ▼
.argo/<name>/video.mp4 (2× capture, silent)
   │  npm run render: ffmpeg mux — trim to cut, loudnorm to target LUFS, fades, scale to 1920×1080 or 1080×1920
   ▼
out/<name>.mp4   /   out/<name>-vertical.mp4
```

### Clock and sync

The recorder starts the capture, then calls `Music.start(start)` and schedules each scene at its bar time against wall time (no accumulated drift). Inside the page, everything reads `Music.time()`; hooks fire from a requestAnimationFrame loop. Durations are expressed in beats (`Music.beats(n)`) so entrances land on beats when a scene starts on a bar. In `npm run check`, `Music.freeze(t)` pins the clock a few beats into each scene so screenshots (and lyrics) are deterministic.

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
3. **Cut and layer.** Character sheets (N poses side by side) → one transparent PNG per pose with `python3 scripts/cutout_sheet.py sheet.jpg --count 4 --names a,b,c,d -o cutouts/<who>` (splits on background gaps, rembg isnet + alpha matting, largest-blob cleanup, trim). Poses beat parts: acting = pose swaps on beats + squash/stretch + hops, which reads as animation and never shows seams. Backgrounds → at least 2 layers: the full plate (far, depth ~0.3) and a feathered foreground band (near, depth 1), plus a slow Ken Burns pan; true depth splits (depth model + inpaint) are a later upgrade. Each output is listed in the manifest.
4. **Approve.** Render a labeled contact sheet of every asset; a human approves or asks for re-rolls per item (`status: approved | reroll`). Nothing is animated until the set is approved and visually consistent.
5. **Animate.** Stages use the approved PNG parts and layers (as `<image>`/`<img>` layers with `data-depth`) with the same music runtime, presets and comic style.

## Chorus routine (the recurring hook)

Every chorus cuts (on a bar line, usually for the chorus's last 4-6 bars) to the **same** signature group dance: same stage, same lights, same title stamp ("official chorus routine #n"), same 4-beat move. Repetition is the point; viewers learn it by chorus 2 and wait for it.

- **The move (4 beats, loops per bar):** beat 1 = group DANCE pose + kick (hop + tilt) + camera punch + spotlights swing; beat 2 = ALT pose + mirror flip; beat 3 = DANCE pose, flip back, small hop; beat 4 = ALT pose + squash. Poses come from the asset set (one shared group-dance image cut per character + each character's happiest pose as ALT).
- **Running gag:** one cast member (the villain) changes participation each chorus: refuses → taps once per bar → does only the downbeats → dances fully while denying it → front and center loving it. Each chorus also gets one new line (bubble) and at most one new prop, nothing else changes.
- **Story context:** the routine can reflect story state (cracked drum still dancing, villain dancing in his cage), but the move itself never changes.
- **Shorts:** build the vertical cut around one or two routines; the routine is the most re-watchable part.
- Implementation: `routine(n)` in `shots/kingdom-come/stage/index.html`, scenes `dance1..dance5`, driven by `Music.onBeat` with a beat-in-bar counter.

## Pipeline (how an assistant makes one)

0. `npm run suno:sync -- <song-id>` to fetch the song, cover and lyrics into `channels/<channel>/songs/<id>/`.
1. `npm run new -- <name> --music song.mp3 --lyrics lyrics.txt` → copies the song, runs the analysis, writes `timeline.json`, one placeholder scene per section, and `<name>.music.json`.
2. Read the lyrics and the section list; write the **storyline** (cast + arc) into `<name>.music.json`.
2b. **Asset prep** (see above): list → generate in style → cut/layer → approve.
3. Use the approved cutouts as actors (`actor(host, who, {x, y, s, pose})` in `shots/kingdom-come/stage/index.html`: stacked pose `<img>`s, feet-anchored so squash/hop happen from the ground). Hand-drawn SVG cast is the fallback when no asset set exists.
3b. Build the **chorus routine** once and play it in every chorus (see below).
4. Build scenes: choruses as big beat-driven set pieces (comic splash pages, slams), verses as plot (parallax pans, panels, bubbles). Put entrances on beats (`B(n)`), cuts on bars.
5. `npm run check -- <name>`; review the contact sheet (lyrics are frozen a few beats in).
6. `npm run render -- <name>`; sample frames at known word times to confirm sync.
7. `npm run render -- <name> --format vertical --start … --end …` for the Short.

## Roadmap

- **v1 (now):** soundtrack mux, beat/bar/section/energy timeline, Whisper lyric alignment, runtime hooks, camera/parallax/particles/presets, lyric styles, themes, comic style, vertical format, `new --music`.
- **v1.1:** frame-exact capture (virtual time instead of wall time), so heavy scenes can never drop frames; per-word lyric editing file (`lyrics.fix.json`); automatic Shorts window picker (energy × lyric density × arc beat).
- **v1.2:** cast library (`lib/cast/*.svg`) with poses and mouth shapes; lip-flap from vocal energy; reusable backdrops (castle, city, beach, space).
- **v2:** `clip` layers slaved to the song clock (AI video, stock); a `3d` layer slot with a three.js adapter; stem separation (demucs) for drum-locked vs vocal-locked motion.
- **v1.1 (sourcing):** scheduled `suno:sync` for whole profiles; Grok Imagine importer; palette sampling from covers into per-song `style.json`.
- **Later:** a "party channel" batch mode: drop a folder of Suno songs, get drafts of both formats with storyline suggestions for review.

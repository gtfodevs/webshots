# AGENTS.md: how an AI assistant makes a webshot

You are the user's video maker. The user only describes the video they want ("a 60-second video on why the sky is blue"). You do everything else and hand back an MP4. This file works the same for any coding assistant that can run terminal commands and edit files: ChatGPT / Codex, Claude Code, Cursor, Gemini CLI, Copilot and others.

**Ground rules**
- Do every step yourself. Don't send the user commands to run.
- Ask a question only if the request is too vague to choose a subject.
- Defaults: about 60–90 seconds, playful but accurate, voice `am_michael`.
- Keep messages to the user short and plain. Don't paste code or JSON at them.

## 0. First time only: get the machine ready

1. **Check the tools:** `node -v` (needs 20 or newer) and `ffmpeg -version`. If either is missing, install it:
   - macOS: `brew install node ffmpeg`
   - Debian/Ubuntu: `sudo apt install nodejs npm ffmpeg`
   - Windows: `winget install OpenJS.NodeJS FFmpeg`

   If you aren't allowed to install system software, tell the user in one sentence exactly what's missing and stop.
2. **Install:** run `npm run setup` once. It installs the dependencies and Chromium, then runs a self-check. It takes a few minutes and downloads a few hundred MB, so tell the user that before you start.

## 1. Name the video

Pick a short kebab-case name, then run `npm run new -- <name> --title "<Title>"`.

That creates `shots/<name>/` with three files:

| File | What it is |
|---|---|
| `<name>.scenes.json` | The narration: an ordered list of `{ "scene": "id", "text": "what the narrator says", "voice"?: "..." }` |
| `stage/index.html` | The animation: one 1280×720 page with one `<section class="scene" id="s-<id>">` per scene, animated with GSAP |
| `<name>.demo.ts` | Two lines that hand off to the shared recorder. Don't edit it. |

`shots/why-farts-stink/` is a complete, polished example. Read its two files before your first shot.

## 2. Write the narration (`<name>.scenes.json`)

- Use 5–9 scenes, each 1–3 sentences (about 6–15 seconds spoken). Open with a hook and end with a punchline or takeaway.
- Write for the ear: short sentences, numbers written the way they're spoken ("half a part per billion"), and no symbols, emoji or markdown.
- Be factually correct. Hedge real uncertainty ("scientists think…"). Never invent statistics.

## 3. Build the animation (`stage/index.html`)

Start from the template already in the file, and keep its `<script>` tags and its final `Webshot.start()` call.

- **One `<section>` per scene,** with ids exactly `s-` plus the scene id from the narration file.
- **Draw with inline SVG.** Use big, simple characters and objects with thick outlines, and only a few large words per scene. The voice carries the detail.
- **Give each video its own look.** Change the `:root` colour and font tokens to suit the subject; Google Fonts is fine.
- **Animate each scene:**
  ```js
  Webshot.scene('<id>', (tl, el, idle) => {
    tl.from(el.querySelector('.h2'), { y: -40, autoAlpha: 0, duration: 0.6, ease: 'back.out(2)' });  // entrance
    idle(() => gsap.to('#thing', { y: '-=12', yoyo: true, repeat: -1, duration: 0.8 }));                // loop afterwards
  });
  ```
  The entrance goes on `tl` and should finish before the narration line does. Continuous motion goes in `idle()`. DrawSVG (lines that draw themselves) and MotionPath (moving along curves) are already loaded. Other GSAP plugins are at `/vendor/<Plugin>.min.js`.
- **Rules that prevent the bugs we've hit:**
  1. Position SVG objects with a static wrapper `<g transform="translate(x y)">` and animate an **inner** `<g>` that has no `transform` attribute.
  2. Idle loops use **relative** moves (`y: '-=12'`), never absolute ones (`y: -12`).
  3. Never start looping motion inside the entrance. Use `idle()`, which starts it after the entrance finishes.
  4. Use no remote images or scripts other than Google Fonts. Everything else is inline SVG or files inside `stage/`.

## 4. Check it (repeat until clean, about 3 passes at most)

Run `npm run check -- <name>`. It plays every scene and reports these problems:

- page errors
- missing files
- scenes that are in the narration file but not on the stage, or the other way round

It also saves a screenshot of the end of each scene, plus a contact sheet at `out/<name>/check/sheet.png`.

- **If you can view images:** open the sheet and fix anything wrong (overlaps, clipped text, things in the wrong place, empty scenes), then check again.
- **If you can't view images:** fix everything in the problem list, re-read your layout coordinates for overlaps, and tell the user you couldn't visually confirm the frames.

## 5. Render

Run `npm run render -- <name>`. It takes a few minutes, so use a long command timeout or run it in the background. It:

1. generates the voice
2. records the animation timed to each line
3. writes `out/<name>.mp4` plus subtitles in `out/<name>.srt`

The first render downloads the voice model, and later renders reuse it.

## 6. Hand it over

- Spot-check two or three frames, for example `ffmpeg -ss 20 -i out/<name>.mp4 -frames:v 1 out/<name>/frame.png`.
- Then tell the user, in one or two lines, where the file is, how long it is, and which voice it used.
- You can't hear audio. If they ask about the sound, say so.
- Offer one obvious next tweak: a different voice, shorter, funnier, or another topic.

## Music mode (music videos, no narration)

When the user gives you a **song** (mp3/m4a/wav, e.g. a Suno track) instead of a script, make a music video. Full design: `docs/MUSIC_MODE.md`.

1. `pip install --user librosa faster-whisper` once (Python helpers), then
   `npm run new -- <name> --music path/to/song.mp3 --lyrics lyrics.txt` (lyrics optional, `[Chorus]`-style tags help).
   This copies the song into `stage/assets/`, writes `stage/timeline.json` (tempo, beats, bars, sections, energy, Whisper words, aligned lyric lines), one placeholder scene per section in `<name>.scenes.json` (`{"scene": "...", "at": seconds}` or `"bar": n`), and `<name>.music.json` (soundtrack, loudness -14 LUFS, fades, cut, `shorts` window, `storyline`).
2. **Write a storyline before drawing:** a recurring cast (3-5 characters) and arc beats mapped to sections (setup → journey → conflict on a chorus → payoff → coda). Put it in `<name>.music.json`. Verses carry plot, choruses are big set pieces. Stay faithful to the lyrics.
3. Prefer an approved AI asset set (cutout PNG poses + layered backgrounds, see the skill); otherwise draw the cast once as SVG `<symbol>`s and reuse them with `<use>`. Every chorus should end in the same **chorus routine** (docs/MUSIC_MODE.md).
4. Build scenes with `/music.js` (load it after `/kit.js`; `await Music.load('timeline.json')` before `Webshot.start()`):
   - durations in beats: `Music.beats(n)`; scenes start on bars, so entrances at `B(n)` land on beats;
   - hooks: `Music.onBeat(b => ...)` (b.downbeat, b.energy), `onBar`, `onSection`, `onLyric`;
   - camera: wrap scenes in `<div id="camera">`; layers with `data-depth` parallax; `Music.cam.to/punch/shake/reset`;
   - presets: `Music.fx.slam/pop/float/pulse/squash/wobble/shatter`; particles: `Music.particles(el, {kind:'embers'|'sparkles'|'confetti'|'dust'})`;
   - lyrics: `Music.lyrics({ styleFor: line => /chorus/.test(line.tag) ? 'slam' : 'comic', hot: 'fire|drum' })` (styles: karaoke, slam, ticker, comic);
   - comic pages: `.c-page` + `.c-panel` (+ `.c-halftone`), `Music.comic.panels(page,{beats})`, `comic.sfx(host,'BOOM',{...})`, `comic.bubble(host,text,{x,y,tail})`, `comic.caption(host,text)`;
   - themes: `Music.theme('fantasy'|'hiphop'|'synthwave'|'party')`.
   Use a fixed viewport per frame; add `html[data-format=vertical]` CSS so the stage reflows for Shorts.
5. `npm run check -- <name>` (lyrics are frozen a few beats into each scene for the screenshots) and review the contact sheet.
6. `npm run render -- <name>` → `out/<name>.mp4` (1920×1080, song at -14 LUFS, no voice). Shorts: `npm run render -- <name> --format vertical --start 97.3 --end 141.3` → `out/<name>-vertical.mp4` (1080×1920, keep it ≤60 s).
7. Verify sync: grab frames at a few known word times (`timeline.json` → `lyrics[].words[].t`) and confirm the word is on screen.

Example: `shots/kingdom-come`.

**Full step-by-step for any AI: `skills/music-video/SKILL.md`** (with `skills/music-video/workflows/*.md` checklists and `skills/music-video/prompts/*.md` image-prompt templates). Follow it for music videos: Suno sync → storyline → asset list → style anchor approval → generate assets → cutouts/layers → chorus routine → scenes → render 16:9 + Shorts → QA → export. Song-specific assets and renders belong in the channel folder (e.g. Jason's `progressive-slop`), not in this tool.

## Voices

- **Kokoro (default; local, free, no account):**
  - `am_michael` (male, the default)
  - `af_heart` (female)
  - `bf_emma` (British female)
  - `bm_george` (British male)

  Set a voice per scene with `"voice"` in the narration file, or for the whole render with `WEBSHOTS_VOICE=af_heart npm run render -- <name>`.
- **Cloud voices,** only if the user asks and has a key. Install the SDK once, then set the engine:
  - OpenAI: `npm i openai`, then `WEBSHOTS_TTS=openai` (needs `OPENAI_API_KEY`; voices such as `alloy`, `nova`, `onyx`)
  - ElevenLabs: `npm i @elevenlabs/elevenlabs-js`, then `WEBSHOTS_TTS=elevenlabs` (needs `ELEVENLABS_API_KEY`; the voice is an ElevenLabs voice id)

  Run `WEBSHOTS_TTS=<engine> npm run doctor` to confirm it's ready.

## Troubleshooting

- **`dependencies missing`:** run `npm run setup`, and `npm run doctor` shows what's still missing.
- **"stage never became ready" or "scene not found":** check the section ids (`s-<scene>`) and that the script ends with `Webshot.start()`.
- **A scene feels static** because the narration runs longer than the animation: add idle motion or a second beat to the entrance.
- **The render fails partway:** the log names the scene. Voice clips are cached, so rerunning after a fix is quick.
- **They want a walkthrough of a real website instead:** write a custom `<name>.demo.ts` using Argo's `createHumanCursor` and `narration.mark()` (see https://github.com/shreyaskarnik/argo), and keep the same narration file.

## Commands

```bash
npm run setup                          # once
npm run doctor                         # what's installed / missing
npm run new -- <name> --title "Title"
npm run new -- <name> --music song.mp3 --lyrics lyrics.txt   # music video shot + timeline
npm run render -- <name> --format vertical --start 97 --end 141   # music: Shorts 1080x1920 cut
npm run check -- <name>                # -> out/<name>/check/sheet.png
npm run render -- <name>               # -> out/<name>.mp4
npm run preview -- <name>              # live stage at http://127.0.0.1:8231
npm run list
```

## Code map

- `lib/music-kit.js` (served as `/music.js`): music-mode runtime (clock, hooks, camera, parallax, particles, presets, lyrics, comic)
- `lib/music-runner.ts`: recorder for music shots (song clock + bar-scheduled cuts)
- `scripts/analyze_music.py`: beats/bars/sections/energy + Whisper lyric alignment → timeline.json
- `template-music/`: scaffold for `npm run new -- <name> --music`
- `docs/MUSIC_MODE.md`: music mode design and roadmap


- `lib/stage-kit.js`: the stage contract (`Webshot.scene`, `idle`, `Webshot.start`)
- `lib/runner.ts`: the shared recorder (plays scenes in narration order and holds each until its line ends)
- `lib/serve.mjs`: serves a shot's stage, and `/vendor/*` from GSAP
- `scripts/webshots.mjs`: the `new | check | render | preview | list` commands
- `webshots.config.mjs`: video size, voice engine and export settings
- `template/`: what `npm run new` copies
- `out/`: build output, never committed

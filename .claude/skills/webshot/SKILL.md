---
name: webshot
description: Make a narrated, animated explainer video (MP4) from a plain-language description, like "a 60-second video on why the sky is blue". Writes the narration, builds an animated GSAP stage, checks every scene, then renders with a local AI voice. Use whenever the user asks for a video, animation, explainer, short or walkthrough in this repo, or types /webshot.
---

# Make a webshot

Follow **`AGENTS.md`** in the repo root, step by step. It is the single playbook every assistant uses (Claude, ChatGPT/Codex, Cursor, Gemini).

Claude-specific notes:
- The Read tool can view images, so in step 4 always open `out/<name>/check/sheet.png` and look at it.
- `npm run render` takes several minutes. Use a long Bash timeout (up to 600000 ms) or `run_in_background`.
- `.claude/settings.json` pre-approves the `npm run new | check | render | preview | list`, `ffmpeg` and `ffprobe` commands, so the flow runs without permission prompts.

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

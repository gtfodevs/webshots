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

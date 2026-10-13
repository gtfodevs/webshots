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

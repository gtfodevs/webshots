---
name: webshot
description: Make a narrated, animated explainer video (MP4) from a plain-language description, like "a 60-second video on why the sky is blue". Writes the narration, builds an animated GSAP stage, checks every scene, then renders with a local AI voice. Use whenever the user asks for a video, animation, explainer, short or walkthrough in this repo, or types /webshot.
---

# Make a webshot

Read **`docs/VIDEO_PIPELINE.md`** first (general rules for every video type, explainers included: reference-first generation, `docs/panel-check-prompt.md`, clip consistency + drift check, focus regions for 16:9 + Shorts, varied transitions, looping themed background, title intro + end card, no clipping, kid-safe, "Not made for kids"). Then follow **`AGENTS.md`** in the repo root, step by step. It is the single playbook every assistant uses (Claude, ChatGPT/Codex, Cursor, Gemini).

Claude-specific notes:
- The Read tool can view images, so in step 4 always open `out/<name>/check/sheet.png` and look at it.
- `npm run render` takes several minutes. Use a long Bash timeout (up to 600000 ms) or `run_in_background`.
- `.claude/settings.json` pre-approves the `npm run new | check | render | preview | list`, `ffmpeg` and `ffprobe` commands, so the flow runs without permission prompts.

Mode docs (add rules on top of the general flow):
- Narrated explainers: `AGENTS.md` steps 1-6. Scene changes get varied transitions from `/kit.js` by default (`Webshot.transitions(...)` / per-scene `{ transition }` to override).
- Music videos: `docs/MUSIC_MODE.md` + `skills/music-video/SKILL.md`.
- Comic-style videos: `docs/COMIC_MODE.md` + `skills/comic-video/SKILL.md` (layouts, lettering, solid SFX bursts, story/stakes workflow, cover-as-costume reference, Uno/Aura sheets, comic QA and all the dated comic lessons).

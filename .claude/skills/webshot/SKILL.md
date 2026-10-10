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

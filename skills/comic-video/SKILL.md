---
name: comic-video
description: Turn a song or story into a comic-book style video (pages of panels, Grok Imagine clips inside the frames, comic lettering, SFX, splash pages) rendered by scripts/comic_render.py in 16:9 and as a YouTube Short. Use when the brief says comic / graphic-novel style.
---

# Comic-style video

Order of reading: **`docs/VIDEO_PIPELINE.md`** (general rules, all video types) → `docs/MUSIC_MODE.md` (if it is a
music video: timeline, beats, sections, lyrics) → **`docs/COMIC_MODE.md`** (comic-only rules, spec format, QA).

1. **Story first.** Beat-by-beat story synced to the timeline's sections, with a **need** line (stakes) on every page,
   before any panel (`docs/COMIC_MODE.md` → *Dramatic story workflow*).
2. **References.** Lock the cast sheets (`refs/uno-*`, `refs/aura-*`: front/side/back/face) and use the video's cover /
   costume sheet as the costume reference. Pass only the characters actually in each panel.
3. **Panels from references** (fixed comic style prompt, NO text in the art, "only these characters" clause). Vehicle/FX
   panels may be text-only (no characters named, end with "one continuous shot, no people"). Dramatic mid-strike
   action, extreme angles, every panel a different scene, kid-safe.
4. **Panel QA:** run `docs/panel-check-prompt.md` on every panel; any FAIL is regenerated, never animated.
5. **Clips:** Grok Imagine reference-to-video from the panel + sheets; review at 8 fps; run
   `python3 scripts/clip_drift_check.py SPEC --clips 'clips/{id}_*.mp4' --refs refs/`; pick only unflagged takes.
6. **Spec** `shots/<name>/<name>.comic.json` (`pages`, layouts from the layout library, captions with the full lyric
   line, one solid SFX per panel on the beat, `focusRegions` for every face and key moment, `refs`, `bg_video` from
   `scripts/make_loop_bg.py`, `intro`, `endCard`). Entrances and page transitions are varied by default.
7. **QA + render:** `npm run check -- <name>` (comic QA must PASS) → `npm run comic -- <name>` → contact sheet →
   `python3 scripts/comic_render_audit.py SPEC LANDSCAPE.mp4 SHORT.mp4 --out DIR`.
8. Commit spec and code only, never media. Upload as "Not made for kids".

# QA checklist
- [ ] `npm run check -- <name>`: "No problems found"; contact sheet reviewed (no overlaps, feet above the lyric band, no blank frames)
- [ ] `ffprobe` resolution: 1920x1080 (full) / 1080x1920 (Short); Short ≤ 60 s
- [ ] Loudness: `ffmpeg -i out.mp4 -af ebur128 -f null -` → Integrated ≈ -14 LUFS
- [ ] Sync: extract frames at 3-5 word times from `timeline.json` (`lyrics[].words[].t`), confirm the word is on screen
- [ ] Every chorus shows the routine; gag escalates
- [ ] Ending fades out cleanly
- Motion: every on-screen character moves in every frame (no stills); consecutive-frame diffs of one actor show head, arms/cape and hem moving independently; `mpdecimate` keeps ~all frames (frame-exact capture).
- Brand: everything is a chrome robot with red eyes and headphones; ProgressiveSlop + tagline on the title and end cards.
- Shorts: no bubble or caption clipped at the frame edges.

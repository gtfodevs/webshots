# QA checklist
- [ ] `npm run check -- <name>`: "No problems found"; contact sheet reviewed (no overlaps, feet above the lyric band, no blank frames)
- [ ] `ffprobe` resolution: 1920x1080 (full) / 1080x1920 (Short); Short ≤ 60 s
- [ ] Loudness: `ffmpeg -i out.mp4 -af ebur128 -f null -` → Integrated ≈ -14 LUFS
- [ ] Sync: extract frames at 3-5 word times from `timeline.json` (`lyrics[].words[].t`), confirm the word is on screen
- [ ] Every chorus shows the routine; gag escalates
- [ ] Ending fades out cleanly

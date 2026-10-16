# Export checklist
- [ ] Commit the shot in webshots
- [ ] Channel folder layout: `assets/<song>/{source,cutouts,layers,manifest.json,contact-sheet.png}`, `renders/<song>-v<N>.mp4`, `renders/<song>-v<N>-short.mp4`
- [ ] Merge into the user's folder without overwriting: `tar -xkf` or `rsync -a --ignore-existing`; split transfers >100 MB (`split -b 80m`)
- [ ] Verify file counts and that pre-existing files are unchanged (checksums before/after)

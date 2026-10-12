---
name: music-video
description: Turn a song (e.g. a Suno track) into a narration-free animated music video with webshots music mode — storyline with a recurring cast, an approved AI asset set in one channel style, beat-synced 2D animation, a repeating chorus routine, and 16:9 + YouTube Shorts renders at -14 LUFS. Use when the user gives you a song, a Suno link, or asks for a music video / lyric video / Short.
---

# Music video (webshots music mode)

Works with any AI assistant and any image model. Design background: `docs/MUSIC_MODE.md`. Worked example: `shots/kingdom-come` (Kingdom Come, Progressive Slop).
Song-specific assets and renders live in the **channel folder** (e.g. `channels/<channel>/…` here, synced to Jason's `/Volumes/toshiba/progressive-slop`); this skill, the runtime and the templates stay generic.

Stop for human approval at the two marked gates. Everything else runs autonomously.

## 1. Suno sync (song = source of truth)
- `npm run suno:sync -- <song-id or url> [--channel <channel>]` → `channels/<channel>/songs/<id>/` (audio, video, cover, lyrics, meta). If the mp3 403s, the script extracts audio from the mp4.
- `npm run new -- <name> --music <audio> --lyrics <lyrics.txt>` → `shots/<name>/` with `stage/timeline.json` (tempo, beats, bars, sections, energy, Whisper words, aligned lyrics), placeholder scenes, `<name>.music.json`.
- Sanity-check `timeline.json`: section labels match the lyric tags; every chorus has words.

## 2. Storyline + cast
- 3-5 recurring characters, one villain/foil. Arc mapped to sections: setup (chorus 1) → journey (verses) → conflict (a late chorus) → payoff (last chorus) → coda (outro/credits). Stay faithful to the lyrics.
- Write it into `<name>.music.json` → `storyline` (cast with one-line descriptions, arc → scene names).
- Pick the running gag for the chorus routine (who changes participation each chorus).

## 3. Asset list
- `channels/<channel>/assets/<name>/manifest.json`: per character a **sheet with 4 poses** (neutral, action, reaction, happy — chosen from story beats, e.g. lit/flame-out/cracked/joyful), one **group dance** image with the whole cast in the same pose, 3-5 **backgrounds** (one per story location; include a "payoff" version of the opening location), and props only if a pose can't carry them. Use `workflows/asset-list.md`.

## 4. Style anchor — GATE 1 (approval)
- Generate ONE character sheet (the hero) from the channel `style.json` + the song cover as reference, with `prompts/style-anchor.md`. Show it. Do not generate the rest until the user approves the look. Record the approved description in the manifest (`style_anchor`).

## 5. Generate the set (any image model)
- Use the exact templates in `prompts/` with the **style anchor + cover as reference images** on every call: `character-sheet.md`, `group-dance.md` (all sheets as references), `background.md`. Highest quality, 16:9 (e.g. 1024x576 or larger), plain solid light-gray background for characters, no text.
- Save raw outputs to `channels/<channel>/assets/<name>/source/` (`<who>-sheet.jpg`, `chorus-dance.jpg`, `bg-<place>.jpg`). Re-roll any image that drifts (proportions, outline weight, palette).

## 6. Cutouts + parallax — GATE 2 (approval of the contact sheet)
- `pip install --user "rembg[cpu]"` once.
- Per sheet: `python3 scripts/cutout_sheet.py source/<who>-sheet.jpg --count 4 --names a,b,c,d -o cutouts/<who>`; group: `--count 5 --names <left-to-right order> -o cutouts/dance`.
- Backgrounds: far plate (full image, slight blur) + feathered foreground band (near) PNG; pan slowly (Ken Burns). See `workflows/cutouts.md` for the snippet.
- Labeled contact sheet of everything (checker behind cutouts) → show it, fix bad edges/clipped limbs, update manifest statuses.

## 7. Chorus routine
- One routine, reused in EVERY chorus (scenes `dance1..danceN`, cut in on a bar for the last 4-6 bars of each chorus). 4-beat move: kick (beat 1) / alt pose + mirror (2) / dance + hop (3) / alt + squash (4); camera punch + spotlight swing on downbeats; a title stamp "official chorus routine #n".
- Running gag escalates per chorus (refuse → tap → downbeats only → full while denying → front and center). One new bubble per chorus; the move never changes. Checklist: `workflows/chorus-routine.md`.

## 8. Scene build
- Copy `stage/assets/cast/*.png` and `stage/assets/bg/*` from the channel asset folder into the shot.
- Use the `actor()` helper pattern (see `shots/kingdom-come/stage/index.html`): stacked pose imgs, feet-anchored; `pose()` swaps on beats, `squash()`, `hop()`, `bobOnBeat()`, `swapOnBeat()`.
- Verses carry plot (parallax pans, comic pages with `.c-panel` + bubbles/captions); choruses are set pieces then the routine. SFX lettering on hits, particles for fire/magic/party. Lyrics: `slam` for chorus lines, `comic` for verses. Keep characters' feet above the lyric band.
- Add `html[data-format=vertical]` CSS and format-aware positions so the stage reflows for Shorts.

## 9. Render 16:9 + Shorts
- `npm run check -- <name>` → review `out/<name>/check/sheet.png` (no overlaps, nobody hidden by lyrics, no empty frames).
- `npm run render -- <name>` → `out/<name>.mp4` (1920x1080, song at -14 LUFS, fade out).
- Shorts: set `shorts.start/end` in `<name>.music.json` on bar lines around one or two routines (≤60 s), then `npm run render -- <name> --format vertical --start <s> --end <e>`.

## 10. QA
- `workflows/qa.md`: loudness (`ffmpeg -af ebur128`) ≈ -14 LUFS, duration, resolution, frames sampled at known lyric word times show the right word, each chorus shows the routine, contact sheet clean.

## 11. Export
- Commit the shot. Copy renders + manifest + contact sheet into the channel folder (`channels/<channel>/renders/`, `…/assets/<name>/`), then merge into the user's channel folder without overwriting (`workflows/export.md`).

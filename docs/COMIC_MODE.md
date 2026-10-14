# Comic mode: comic-book videos

Comic-only rules. Read **`docs/VIDEO_PIPELINE.md` first**: reference-first generation, the panel QA prompt,
clip consistency / drift check, focus regions, varied transitions, looping backgrounds, title intro + end card,
no clipping and kid-safe rules all apply here and are documented there. For music-specific timing (beats,
sections, lyrics) see `docs/MUSIC_MODE.md`.

## Comic-only rules at a glance

- **Story first, beat by beat, with stakes before panels:** write the whole story synced to the sections before a single
  panel; every page has a **need** line (what the heroes want or are losing). See *Dramatic story workflow*.
- **Page layouts / cells:** use the layout library; never the same layout or splash style on consecutive pages;
  pages fill the paper. See *Layout library*.
- **Comic lettering & captions:** all lettering is added by the renderer (no text in the art), Bangers, lyric/narration
  caption boxes, one SFX per panel on the beat.
- **SFX starbursts are solid, never hollow** (`paint_burst`, QA `burst_see_through`).
- **Dramatic mid-strike fight panels:** heroes mid-strike, never posing; wind-up → strike → impact → reaction; extreme angles.
- **Cover image as costume reference:** the video's cover / locked costume sheet defines the costume for that video;
  pass it as a reference on every character panel so outfits match.
- **Recurring cast Aura / Uno sheets:** use the locked `refs/uno-*` and `refs/aura-*` sheets (front/side/back/face) on every
  panel they appear in, and only the sheets of characters actually in the panel (pick references by act).

## Comic mode (comic-book music video, not a game)

A song becomes a sequence of comic **pages**. Panels land one at a time on beats, separated by
paper gutters with black ink borders. Each panel holds as still art, then its short Grok Imagine
clip plays *inside the frame*, then it freezes on the clip's last frame. A zoom into a panel
(landing on a downbeat) hands over to a full-frame **splash** for the big hit. Paper grain and a
light halftone sit over everything so 480p clips blend with the 720p+ art; lettering is Bangers
(SIL OFL; `fc-match Bangers`, else downloaded to `~/.cache/webshots/fonts`).

Files: `scripts/comic_lib.py` (layouts, registration, texture, lettering, frame builder),
`scripts/comic_render.py` (MP4s + contact sheet), `scripts/comic_qa.py` (QA). Example scene:
`shots/neon-dojo-comic/neon-dojo-comic.comic.json`.

```bash
npm run comic -- neon-dojo-comic [--out /path/to/out] [--only landscape|vertical] [--short full|cut]   # cut = spec.short {start,end}
npm run check -- neon-dojo-comic      # comic QA (no stage needed)
```

Outputs never overwrite (`-v2`, `-v3` …): `comic-scene-1080p.mp4` (1920x1080), `comic-scene-short.mp4`
(1080x1920; the same spec re-flows into three stacked 16:9 slots + a 1000x1120 splash),
`comic-scene-sheet.png`. Audio is the spec's song section, 30 ms fade in / 0.6 s fade out,
two-pass loudnorm to `song.loudness` (-14 LUFS, TP -1.5).

### Full-song workflow

1. **Timeline.** Use the song's `stage/timeline.json` (`scripts/analyze_music.py`: beats, downbeats,
   sections, timed lyric lines). One comic scene = one section or 8–12 bars (~12–15 s); 3–4 panels per
   page, the last one goes splash on the section's hit.
2. **Panels** (image model, one fixed style prompt for the whole song, 16:9, **no text in the art**;
   all lettering is added by the renderer so it stays sharp and editable). Style prompt template:

   ```
   {SHOT} of {CHARACTERS + ACTION}, {SETTING}. 1990s American superhero comic book panel,
   bold black ink outlines, heavy spot blacks, cel-shaded flat colour with halftone dot shading,
   dynamic foreshortening, speed lines, dramatic {LIGHT, e.g. neon magenta and cyan rim light},
   early-90s comic energy, 16:9 panel, full bleed.
   NO text, no lettering, no speech balloons, no sound effects, no logos, no signatures, no panel borders.
   Characters: {CHARACTER SHEET LINES, identical every panel}.
   ```
   Keep `{CHARACTER SHEET LINES}` byte-identical across the song (costume, colours, helmet, props).
3. **Clips**: Grok Imagine image-to-video from each panel, **480p, 6 s**. Small,
   readable motion only; the camera mostly locked so the clip lines up with the panel. Motion prompt template:

   ```
   Animate this comic panel. {ONE ACTION, e.g. "the fist drives forward and the impact burst flares"}.
   Subtle secondary motion: {hair / cape / rain / sparks / neon flicker}. Camera: locked off
   (or a slow push-in). Keep the exact comic art style, ink lines and colours, keep faces and hands
   unchanged, same number of arms and fingers, no new characters, no morphing, no text, no cuts.
   ```
4. **Review each clip** (`ffmpeg -i c.mp4 -vf "fps=2,scale=368:-1,tile=4x3" -frames:v 1 sheet.png`): the
   Score every clip frame by frame (frame-to-frame NCC: a drop < 0.75 is a jump/reframe; drift from frame 0)
   and look at a 1 fps sheet of all 6 s. **Let clips play: 3.5–4.5 s typical, the full ~6 s when clean**
   (`in`/`out`, QA max 6 s). Cut only where real breakage starts (melting faces, extra heads/limbs, things
   vanishing or multiplying, hard reframes) and say why in `clip.trimNote` (QA warns on < 3.5 s without one).
   Give clips room: land the last panel / splash early enough that its clip finishes before the page turns
   (QA warns when a page turn cuts a clip); several clips playing on one page at once is fine. If no window
   is clean, leave the panel static.
   **Hold rule (Jason):** a clip starts almost immediately after its panel lands: hold the still for at most
   one beat (~0.3–0.5 s), then the motion plays. Leave `clip.at` out and the renderer starts the clip
   `defaults.holdBeats` (default 1) beats after the landing; QA fails if clip start − panel land > 0.6 s or < 0.25 s (keep the anticipation beat).
   **Every panel is a different scene:** vary the location, camera angle and moment for each panel; never
   reuse a composition. Keep it playful and kid-friendly with small humour beats.
5. **Spec** (`shots/<name>/<name>.comic.json`); all `at` values are song seconds on the beat grid:

   ```jsonc
   {
     "assetsDir": "/path/to/panels-and-clips",          // or env COMIC_ASSETS
     "fps": 30,
     "song": { "audio": "shots/x/stage/assets/song.m4a", "timeline": "shots/x/stage/timeline.json",
               "start": 108.042, "end": 122.137, "loudness": -14 },
     "panels": [{
       "id": "p1", "image": "panels/p1.jpg", "slot": "top-left",   // top-left | top-right | bottom
       "at": 108.042,                                               // beat the panel lands on
       "focus": [0.5, 0.5],                                         // crop centre when the slot aspect differs
       "clip": { "src": "clips/c1.mp4", "in": 0.0, "out": 2.0 },  // optional; "at" defaults to 1 beat after landing
       "lyric": "(Woman) Count it out, one by one",
       "captions": [ { "text": "COUNT IT OUT, ONE BY ONE", "anchor": "br", "at": 109.738, "lyric": true } ],
       "sfx": [ { "text": "SHIIING!", "at": 110.179, "pos": [0.52, 0.32], "rot": -8, "size": 0.17, "color": [255,70,60] } ]
     }],
     "transition": { "type": "zoom", "panel": "p3", "at": 118.306, "dur": 0.418 },  // at = landing downbeat
     "splash": { "image": "panels/p3.jpg", "clip": { … }, "captions": [ … ], "sfx": [ … ] }
   }
   ```
   **Layout library** (`LAYOUTS` in `scripts/comic_lib.py`; `"layout"` per page, slots `a`, `b`, `c` in
   reading order; `"splashStyle"` per page with a splash). Geometry is normalised; vertical either reuses it
   (`same`), transposes it (`T`: left/right splits become top/bottom) or stacks (`three`).

   | panels | layout | look |
   |---|---|---|
   | 2 | `two-up` | two full-width tiers |
   | 2 | `slant-two` | one diagonal gutter |
   | 2 | `inset-two` | big panel + rotated inset laid over its corner (white keyline) |
   | 2 | `tilt-two` | two panels overlapping at opposite angles |
   | 3 | `three` | grid: two on top, one wide below (stacked in vertical) |
   | 3 | `diagonal-three` | three bands with slanted gutters |
   | 3 | `mixed-three` | big panel + two small with a slanted gutter (mixed sizes) |
   | 3 | `inset-three` | two tiers + a tilted inset straddling the gutter |
   | 3 | `tilt-three` | big tilted panel + two angled panels overlapping it |
   | 2 | `side-two` | two near-square columns (two full-width tiers in vertical); fits wide focus spreads |
   | 4 | `four-grid` | slanted 2x2 (four full-width tiers in vertical via `vslots`) |
   | splash | `full` / `tilt` / `breakout` | full frame / slightly rotated with paper corners / an impact burst breaking out over the border |

   Slot primitives: `rect`, `poly` (slanted, with a lettering-safe inner rect), `rot` (angle, z-order,
   keyline). Captions/SFX are placed in each slot's inner rect. Crops that change the art's aspect a lot keep
   the upper-middle band (focus 0.5, 0.42); set `"focus": [x, y]` on a panel to override.
   **Rules:** never the same layout (or splash style) on consecutive pages; use the full library across a
   song (QA flags low variety); save `breakout` for the biggest hits (chorus drop, boss).
   A whole song uses `"pages": [{ "id", "start", "end", "panels": [...], "transition"?, "splash"? }]` with the
   same panel fields (one page per section; a page may skip the splash). Add `"location"`, `"camera"`,
   `"moment"`, `"scene"`, `"prompt"`, `"refs"`, `"motionPrompt"` per panel at planning time; `"draft": true`
   marks a plan whose art isn't generated yet (QA checks timing/text/uniqueness and reports missing media;
   the renderer refuses drafts). `"outName"` sets the output file prefix. Example:
   `shots/kingdom-come-comic/kingdom-come-comic.comic.json`.
   Lyric lines go in caption boxes (one per panel; an optional narration box like "NEO-TOKYO. MIDNIGHT."
   on the opening panel). One SFX per panel at most, on the beat of the action.
6. **Render + check**: `npm run check -- <name>`, then `npm run comic -- <name>`; look at the contact sheet.
   For a whole song, render each scene and concatenate (each scene's audio is its own song slice, so cut
   scenes edge to edge on the section boundaries).

### How it renders (restraint rules)

- Static hold: one beat, then the clip. Panel entrance: 0.14 s fade + 16 px drop. SFX: a 3-frame stamp (1.25x → 1x), then still. Static →
  clip: 3-frame crossfade. One zoom per page. Nothing shakes, flashes or stacks.
- Clip → panel alignment: Grok re-frames to 736x400, so each clip's first frame is registered onto its
  panel (scale + offset search, NCC). The slot crop is kept inside the clip's coverage and the same crop
  is used for still and clip, so the hand-off doesn't jump.
- Clips: lanczos upscale + light unsharp (r 1.6, 55%), then halftone (45°, 7 px cell, dots grow in
  shadows, 22% strength) + paper grain. Ink borders are drawn after, lettering last.

### Comic corrections checklist (Jason's feedback, check every comic video)

- Clip starts one beat after the panel lands (0.3–0.5 s anticipation, never > 0.6 s).
- Every panel a different scene (location, camera, moment); playful, kid-friendly humour beats.
- Let clips play 3.5–4.5 s (full ~6 s when clean); cut only at real breakage, with a trimNote. Regenerate
  clips with extra heads/limbs, melting faces or camera jumps early on.
- Pages fill the paper (no empty bottom row): pick a layout for the panel count.
- Layouts vary: slanted/diagonal gutters, insets over bigger panels, angled overlaps, breakouts, mixed sizes;
  never the same layout on consecutive pages.
- End card on every comic video and Short (~3 s held final frame: BROUGHT TO YOU BY PROGRESSIVE SLOP /
  LIKE AND SUBSCRIBE FOR MORE!, comic lettering); the song tail fades naturally under it.
- No clipping: lettering never past its panel or the safe area, lyric captions stay up until the line is
  sung (carry them onto the splash / next page) and never overlap; no audio cut mid-word at either end.

### Comic QA (`scripts/comic_qa.py`, part of `npm run check`)

- clip `in`/`out` inside the source duration, `out > in`, length ≤ 6 s; warns on < 3.5 s without a
  `trimNote` and on clips cut off by the page turn;
- 0.25 s ≤ clip start − panel land ≤ 0.6 s (the one-beat anticipation hold);
- layouts: fails the same layout or splash style on consecutive pages and an unknown layout; flags low
  variety (fails < pages/3 distinct layouts, warns < pages/2);
- no page with > 30% bare paper (layout must fit the panel count), every slot exists in the page layout;
- every panel a different scene: fails on two panels with near-identical prompts (content-word Jaccard
  ≥ 0.6 on `scene`/`prompt`), the same `location` + `camera` pair, or near-identical images
  (64-bit DCT pHash, Hamming ≤ 10; a splash reusing its own panel art is allowed);
- every landing / clip / caption / SFX / transition time within 60 ms of a beat;
- captions + SFX inside the frame and not overlapping while on screen (landscape and vertical);
- no black or empty slot at sampled frames (std, mean and % near-black per visible slot);
- each clip registers on its panel (NCC ≥ 0.75, scale 0.9–1.1) and the first used frame is not re-framed
  (> 3% shift fails); large content change in the used frames is a warning (expected for impact bursts).
- no clipping: every caption / SFX box inside its panel's lettering rect and the page safe area
  (`C.TEXT_SAFE`), measured ink (`getbbox`) of every caption line inside its box; a lyric caption must stay
  on screen until its sung line ends (timeline lyrics/words; follows a repeat on the splash) and never
  overlap the next caption;
- angled / slanted panels: every caption and SFX box (SFX measured at its 125% stamp-in peak, rotation and
  stroke included in the measured tile) must sit inside the panel's real clip path (slanted gutters, tilted
  and breakout panels) eroded by `C.LETTER_INSET` (16 px) - not just its bounding rect. The renderer
  auto-fits: it moves the box inward by the smallest step, keeps SFX clear of the panel's captions, and
  shrinks the type when it cannot fit. Pixel check: each panel's lettering is rendered alone at its peak
  frame and no lettering pixel may fall outside the clip path (4 px inside the ink) or the safe area;
  the end card's text corners are rotated with its box before the safe-area test;
- audio: song / Short start and end never cut a word (timeline words), stay inside the source audio, and
  the tail fades over ≥ `C.TAIL_FADE` (2.5 s) under the end card;
- end card: present (`spec.endCard`, default on), ~3 s, and its measured text fits the title-safe area
  (`C.SAFE`, 5%) in landscape and vertical.

### Dramatic story workflow (v3+; worked example: `shots/neon-dojo-comic/v3/`)

Every comic video should level up beyond Kingdom Come: real story, real hits. Example files:
`make_v3.py` (the beat sheet as data; writes `plan.md`, `prompts.json`, `motion.txt`), `generate_jobs.json`
(one image job per new panel with its reference images). Art is not committed.

1. **Story first.** Write the full story beat by beat, synced to the lyrics and sections from
   `timeline.json`, before making a single panel. Three acts:
   - **Act 1, early days:** a montage of Uno and Aura learning to pair up under the Sensei. They clash,
     fail (a botched tag) and train, until the tag finally clicks.
   - **Act 2, tournament:** rivals with real stakes. A loss: one hero goes down and Uno carries Aura out.
   - **Act 3, final boss:** a blade lock, the tag-team combo, both super cut-ins, a kid-safe double finisher
     (armour bursts into sparkles), and a resolution (Sensei, belt, sunrise).

   Every page has a **need** line saying what the heroes want or are losing. No page without stakes.
2. **Art direction.** Dramatic, iconic panels; heroes mid-strike, never posing.
   - Cut each fight on the beat as wind-up → strike → impact → reaction.
   - Use extreme angles (worm's-eye, Dutch, top-down, extreme close-up), impact flashes, speed lines,
     screen shake and big SFX lettering.
   - No static standoffs.
3. **Image references.**
   - **Pick references by act.** A reference image that shows the boss leaks the boss into scenes he isn't
     in, so use the Uno/Aura/Sensei sheet for the early acts. Pass only the characters actually in the
     panel (see `generate_jobs.json`).
   - **Spell out every character description in every prompt:** Uno has a round smooth chrome dome, a purple
     fur coat and a gold "1" chain. Aura has a grey robot face, red eyes, dark crimson hair, a modest crimson
     bodysuit and cyan magic. All robots are chrome with red eyes and headphone ears.
   - **Review every panel and regenerate on any of:**
     - a human, or Aura with human skin;
     - an off-model character;
     - a duplicated character or extra limbs;
     - an immodest outfit;
     - low energy or a static pose;
     - text beyond tiny signage.
4. **Grok Imagine.**
   - One clear, fast action per motion prompt (a strike is fine), at 480p and 6 s.
   - Locked or gentle camera; nobody walks toward the camera; no morphing.
   - Review at 8 fps (contact strip plus frame-step spikes). Trim each clip before morphing starts, keep
     3.5–6 s, end before the page turn, and record the reason in a `trimNote`. Regenerate clips that break
     early.
5. **QA gates (`comic_qa.py`, must PASS before rendering):**
   - **Layouts:** no repeats on consecutive pages, and enough variety.
   - **No clipping:** caption and SFX outlines (at their peak, with rotation) must sit inside the panel's
     real clip path and the safe area, and a pixel-level check of each panel's lettering must pass.
   - **End card:** present, and its text fits the title-safe area.
   - **Lyric timing:** captions stay up until the line is sung and never overlap; no audio cut lands
     mid-word.

#### Lessons from the Neon Dojo v3 build

- **Spec builder.** `v3/make_v3_spec.py` turns the beat sheet into `neon-dojo-comic-v3.comic.json`. It
  maps reused panels to their earlier clips (`REUSE_CLIP`) and keeps the 8 fps review verdicts in `TRIMS`.
  Art that has no clip stays a static panel.
- **Clip review.** Look for a big frame-step at 0.1 s or 1–2 s: that is usually a hard cut or camera jump,
  not motion. Trim before it. Also flag the clip if the "finisher" undoes itself (the armour re-forms).
- **Page turns.** A page never turns while a lyric line is still being sung; a short overrun pushes the
  turn one beat later instead of carrying the caption. Carried captions can collide with the next
  page's own lines.
- **Impact SFX.** Set `"impact": true` on a hit's SFX. The panel art flashes white (0.18 s decay) and the
  frame shakes (0.28 s, ±0.8% of width, zoomed 2% so no edge shows). Lettering is drawn after the flash,
  so it stays readable.
- **Short cut points.** Pick Short start and end in word gaps from timeline `words`, after the lyric
  line's `end`. QA warns when an end lands inside a line.

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

### Deadstars lessons (2026-10-13)
- **A sky-fight back half works well for escalation.** The first half stays on the ground (arena brawls); from the "lights out" beat on, the fight moves to robot jets in the sky (dogfight, core break, crown descent). That makes a natural climax, and its back half is the right window for the Short. Its risk: video models love to turn jets into standing robots or spawn extra pilots. In Deadstars, 6 of the 14 sky-fight shots grew extra robots in both takes.
- **An explicit "only these characters in shot" clause stops extras.** In every image and motion prompt, name the exact cast and add, for example: "Only Uno and Aura in the shot (plus their two jets); no other robots, no crowd, no pilots, nothing appears." The anchor (`ANCHOR_TAIL`) alone does not stop new characters from fading in; listing who is allowed in the shot does.
- **Edits drift with references, so regenerate from the full text.** Repeated image edits on a reference (an "edit this panel" chain) slowly drift faces, colours and proportions (Aura reading human, Uno getting short). Regenerating from the full prompt text plus the character reference was more reliable than another edit pass.
- **Use a local HSV recolor for costume swaps.** For a colour-only change (for example NULLSTAR purple to black), mask the costume hue range and shift or desaturate it in HSV on the panel. That keeps the art identical and avoids the drift a regeneration brings.
- **Picking takes:** generate 2-3 takes per id, review them all at 8 fps with 0/2/4/5.9 s detail sheets, and pick per id by checking for morphing, extra characters, Aura reading as human, Uno looking short, and text artifacts. Play the pick at near-full length. Flag remaining problems in `FLAG`/`trimNote` instead of trimming them away.
- **Short pages cannot carry a splash zoom.** A page under about 9 s with a zoom-transition splash caps its clips at 2-4 s, or even below zero. Make that panel a regular slot, so every clip still gets about 5.3-6 s.
- **Short cut points:** whisper word boundaries can be back to back, with no gap. When they are, cut exactly on a word boundary (QA allows ±0.03 s).
- **Render audit CLI:** `python3 scripts/comic_render_audit.py SPEC LANDSCAPE.mp4 SHORT.mp4 --out DIR` exits 1 if any caption or SFX is sliced by the frame edge.

### Impact bursts are solid (rule, 2026-10-13)
- **Bursts are never hollow.** The breakout impact burst (the star that breaks out over a splash border behind "BAM!"-style SFX) used to be a cutout of the panel art. Video showed through a black-outlined star, which looked strange. `paint_burst` now fills it solid: an opaque radial white-yellow-orange gradient with halftone dots that grow toward the rim, an ink outline, and the SFX lettering on top.
- **QA (`burst_see_through`)** paints every burst over a black base and over a magenta base and compares the interior (eroded 6 px). If any interior pixel changes, the check fails. It runs for landscape and vertical on every page whose splash uses `breakout`.
- **One lyric per page:** the Deadstars builder letters each lyric line only once per page. Early-landing panels had overlapping lyric windows, so the same line was showing on two panels at once.

### Concrete Jungle Cold lessons (2026-10-14)
- **Stills before clips: `stillMotion`.** When Grok Imagine clips are not ready, give each clip-less panel
  `"stillMotion": {"type": "push_in"|"pull_out"|"pan_left"|"pan_right"|"drift_up", "amount": 0.05, "dur": 6}`.
  The renderer (`still_motion_frame`) eases the finished still inside its cell, starting on the beat a clip would
  (one-beat hold), zoomed about the required focus regions. The builder (`shots/concrete-jungle-cold-comic/make_spec.py`)
  switches a panel to `clip` automatically once `clips/fNN.mp4` exists (`clipPending` records the expected path).
- **4-panel pages and 2-col pages:** `four-grid` (layouts may carry explicit vertical geometry in `vslots`) and
  `side-two` were added for focus spreads that a 3.8:1 strip (`two-up`) cannot hold.
- **Slow tempos and zoom splashes:** at 86 BPM a one-beat zoom is 0.7 s. Land the splash one beat after a line that
  would otherwise be cut, so the line starts on the zoom target and is carried onto the splash; the zoom target's
  lettering now counts as visible until the splash lands (`text_items`), matching the renderer.
- **Caption hand-off:** each lyric caption stays up until the first beat after its sung end (`until`), alternating
  tl/bl anchors, so beat-snapped starts never cut a line short or stack two captions in one spot.
- **Gold deco title / end card:** `intro.lines` forces the stacked lines, `intro.sunburst` / `endCard.sunburst`
  draw a gold deco sunburst behind the logo / end card, `endCard.fills` sets the box colours.
- **Layout pass weighting:** score vertical misses only for panels visible inside the Short window (others ×0.3),
  so a panel after the Short does not force a worse 16:9 layout.

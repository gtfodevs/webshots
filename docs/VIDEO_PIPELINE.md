# Video pipeline: general rules for every video

This is the main flow shared by **all** webshots videos: narrated explainers (e.g. `shots/why-farts-stink`),
music videos (`docs/MUSIC_MODE.md`) and comic-style videos (`docs/COMIC_MODE.md`). Read this first, then the
mode doc for the video you are making. Mode docs only add rules; they never relax the ones here.

| Video type | Read after this doc | Renderer |
| --- | --- | --- |
| Narrated explainer | `AGENTS.md` (steps 1-6) | `lib/stage-kit.js` + `lib/runner.ts` (Argo, voice) |
| Music video (2D / rigged actors / pixel / fighter) | `docs/MUSIC_MODE.md`, `skills/music-video/SKILL.md` | `lib/music-kit.js` + `lib/frame-runner.mjs` |
| Comic-style video (music or story) | `docs/COMIC_MODE.md` | `scripts/comic_render.py` |

## Order of work (every video)

1. **Plan** the story / beats (narration lines, song sections, or comic pages) before any art.
2. **Lock references** for every recurring character and setting (see *Reference-first generation*).
3. **Generate stills from references**, run the **panel/frame QA prompt** on each, regenerate failures.
4. **Animate** (GSAP stage, rigged actors, or Grok Imagine clips from references) and run the **drift check** on clips.
   **Comic videos: every panel must have a QA-passed animated clip, with no still-only panels. This is a hard gate
   (`comic_qa.py` fails it); see [COMIC_MODE.md, HARD GATE: every panel animated](COMIC_MODE.md#hard-gate-every-panel-animated-jason-2026-10-14).
   Each video must beat the last one.**
5. **Lay out** with **focus regions** so faces and key moments survive both 16:9 and the 9:16 Short.
6. **Assemble** with a **title intro**, **varied transitions**, a **seamless looping themed background** where
   the frame shows one, and an **end card**.
7. **QA** (`npm run check -- <name>`, plus the mode's QA) → render 16:9 and the Short → **render gate**
   (`scripts/static_check.py`, run automatically by the renderer: no near-static stretch > 0.4 s) → upload as
   *Not made for kids*.
0. **Logotype first (REQUIRED STEP, Jason 2026-10-14):** every video opens with a custom logotype designed for
   that song's world and era (not a caption font), animated in over a moving background. See *Logotype intro*.

## Reference-first generation (HARD REQUIRED STEP, Jason's rule)

Any shot that needs consistency (recurring characters or recurring settings) MUST be generated from locked
reference images, never from text alone: stills by image-editing from the locked sheets / setting plates, clips by
reference-to-video (or image-to-video from such a still plus the sheets). **Text-only prompts are allowed ONLY for
vehicle or effects shots** (see *Vehicle- and FX-only shots*). Record what each still was made from (in comic specs:
`"refs": [...]`, or `"shotKind": "vehicle" | "fx"`; `comic_qa.py check_refs` enforces it there).
Order: plan -> lock reference sheets/plates -> stills from refs -> clips from refs -> drift check -> spec/stage -> QA.

## Panel / frame QA (every generated image, before accepting)

Run **`docs/panel-check-prompt.md`** on every generated image (panel, still, background with characters, cut-in)
with the locked reference sheets open side by side. It covers: identity vs the locked sheet (face, head gear,
proportions, outfit, instantly nameable), anatomy (every hand attached to an arm and shoulder, correct limb/finger/eye/head
counts, no fused limbs), scene (only the named characters, no humans, no stray text/logos/brands, kid-safe props) and
crop safety (faces and key action away from the edges so 16:9 and 9:16 both keep them). **Any FAIL = regenerate with
an adjusted prompt; never animate a failed image.** Log failures and the prompt fix.

## Clip consistency (Grok Imagine)

- Use **reference-to-video** (several reference images) rather than plain single-image animate for any clip with
  characters; pin the still as the first frame.
- Every image and motion prompt names the exact cast and adds an explicit **"only these characters"** clause, e.g.
  "Only Uno and Aura in the shot; no other robots, no crowd, no people, nothing appears." Listing who is allowed in
  the shot is what stops extras fading in.
- Run **`python3 scripts/clip_drift_check.py SPEC --clips 'clips/{id}_*.mp4' [--refs refs/]`** on every take; pick only
  unflagged takes, and still review at 8 fps (the check is a pixel heuristic).

### Details: character consistency in Grok Imagine (standing rule, 2026-10-13)
Why: drift in Grok Imagine clips (Aura reading as human, Uno's dome turning into a visor, extra characters) ruined
otherwise good FRIGHT NIGHT shots. Here is what the public docs say (checked 2026-10-13):
- **Image-to-video locks the first frame** to the single start image and animates from it. The more the clip moves
  away from that frame, the more it can drift ([xAI docs: Image-to-Video](https://docs.x.ai/developers/model-capabilities/video/image-to-video)).
- **Reference-to-video** (`grok-imagine-video-1.5`): up to 14 reference images through the API (7 in the app and on the
  older model), tagged in the prompt as `<IMAGE_0>`, `<IMAGE_1>`, ... References carry a character, outfit or location
  *without* locking the first frame. Pin frames with `image` (first frame; it then takes `<IMAGE_0>`), `last_frame`, and up
  to 4 `keyframes` inside the clip. Up to 15 s at 720p. The docs advise: "give each [reference] a single role and a fixed
  place in the scene, keep the cast small, and keep props static". They also say pins work best when generated as one
  still and then edited ([xAI docs: Reference-to-Video](https://docs.x.ai/developers/model-capabilities/video/reference-to-video),
  [announcement](https://x.ai/news/grok-imagine-video-1-5-references): "Each reference image locks one thing in place - a
  face, a product, a location ... Up to seven references per generation"; launched on grok.com/imagine and iOS).
- **App UI** (community report, not official): Imagine -> Video -> "Animate Photos" -> pick up to 7 images. Insert
  each one into the prompt where it belongs (on desktop, type `@`). Using the same character image twice starts the
  clip directly in the prompted scene instead of morphing out of the photo. Several images of one character improve
  likeness ([r/grok](https://www.reddit.com/r/grok/comments/1rujbi3/demonstration_of_using_multiple_reference_images/)).
- **Image editing**: `grok-imagine-image-2.0` edits from a base image, takes up to 5 input images per edit, supports
  multi-turn editing (chain outputs), and the app has a magic-wand region edit
  ([Image Editing](https://docs.x.ai/developers/model-capabilities/images/editing),
  [Multi-Image Editing](https://docs.x.ai/developers/model-capabilities/images/multi-image-editing),
  [Image 2.0](https://x.ai/news/grok-imagine-image-2)).
- I found no dedicated "character mode" or saved-character feature. Multi-reference is the official mechanism.

Workflow (B = browser step, run by the browser worker on grok.com/imagine; the rest runs on the box):
1. **Lock reference sheets** (`refs/<name>-front.png`, `-side.png`, `-back.png`, plus `-face.png`, a tight head crop).
   For Aura and Uno, start from the best on-model panels (Aura face: f05/f25; Uno face: f19/f22; backs: f10/f13).
   **B:** image-edit each into a clean turnaround on plain dark grey, one view per edit, with the character panel as the
   base plus one more on-model panel as a second input. Keep the views. They are locked: never regenerate them per song.
2. **Panels**: **B:** make each new panel by image-editing with that character's sheet images attached ("the robot from
   image 1 ..."), not from text alone. Check every face with `clip_drift_check.py`'s still checks before animating.
3. **Clips**: **B:** use Video with references (Animate Photos with several images), not plain single-image animate.
   Attach the panel as the pinned first frame, then `<name>-face` and `<name>-front` (and `-side` when the shot turns)
   for each character on screen. For loops or holds, also pin `last_frame`. At most 2 characters per clip, and props static.
4. **Prompt template** (one role per reference, the cast named and counted, the negatives said plainly):
   `Start exactly on <IMAGE_0>. The chrome robot from <IMAGE_1>/<IMAGE_2> (Uno: smooth mirror-chrome dome head, two round
   red glowing eyes, NO visor, NO face plate, purple fur coat, gold "1" chain) [action]. The robot woman from <IMAGE_3>/<IMAGE_4>
   (Aura: grey metal robot face with panel seams, red glowing eyes, crimson hair, NOT human skin) [action]. Only these
   two characters; no other people or figures appear. Camera: [one simple move]. Keep the faces exactly as in the references.`
5. **Drift check** (`python3 scripts/clip_drift_check.py SPEC --clips 'clips/{id}_*.mp4' [--refs refs/]`): samples each clip
   at 4 fps and tracks every face region from frame 0. It FLAGS a clip for regeneration when a face changes (NCC against the
   frame-0 face < 0.35 for 3+ samples), turns human (skin-tone share rising >18 pts or >35%), or its eyes become a
   wide red visor band. It lists *possible extra characters* (sustained extra glowing eye pairs) for a human look.
   With `--refs`, it also scores each face against the locked sheet. It writes `out/<shot>/drift/drift-report.json`
   plus a sheet per clip. Regenerate flagged takes (**B**), then re-run. Pick takes only from unflagged clips.
   These are pixel heuristics. They catch morphs and skin-tone faces but miss subtle off-model detail, so still review takes at 8 fps.

## Vehicle- and FX-only shots (rule, 2026-10-13)
- **For vehicle- or FX-only clips (jets, ships, explosions, beams, crowns), never name characters and never say "robot" in the motion prompt.** Use a short prompt of vehicles, action and camera that ends with "one continuous shot, no people". Example: "Red jet streaks toward a black spiked jet, blue and red energy beams colliding, sparks and speed lines streaming. Locked camera. One continuous shot, no people."
- **Why:** in Deadstars, the no-new-characters clause alone (anchor plus "only these characters in shot") failed 2 of 2 retries; the model kept growing standing robots out of the jets. The vehicle-only prompt fixed 5 of 5 on the first try (d20, d25, d26, d28, s23; d22 and s29 also came out clean). The character anchor only belongs in shots where characters are actually visible.

## Scene-aware focus regions (faces and key moments in 16:9 AND the Short)

Every shot declares where its faces and key action are, and layout + QA verify they stay visible in both the 16:9
frame and the 9:16 Short crop. Explainer/music stages: keep faces and the key action inside the Short's visible band
(see the format notes in `docs/MUSIC_MODE.md`) and check both `npm run check` sheets. Comic videos implement this in
the renderer and QA:

### Scene-aware cropping in the comic renderer (standing rule, 2026-10-13; renderer default)
Why: in the FRIGHT NIGHT Short, f25's red-to-green eye change was cropped out, and the p01 diagonal cell hid Uno's face.
- **Every panel has focus regions**: `panels[i].focusRegions = [{"label": "Uno face", "box": [x0, y0, x1, y1], "required": true}]`
  in normalised panel-image coords, covering every face and the key action (the beat the shot is about: an eye change,
  a fist, a blast, a ghost). Manual regions win. Without them the renderer auto-detects glowing robot-eye pairs
  (`auto_focus_regions`) and boxes the head; this misses small or dim eyes, so author regions for real videos
  (make a 10%-grid sheet of the panels and read the boxes off it). `required: false` = nice to have (crowds, moons).
- **The cropper fits them** (`fit_crop`): the cover crop slides inside the clip's registered area until every required
  region sits inside the cell's clip path, `FOCUS_INSET` px clear of the ink. Same code in landscape and vertical.
- **Builders pick a wider cell when it cannot**: run a layout pass (`fix_layouts` in `shots/fright-night-comic/make_spec.py`)
  that tries every layout with the same panel count and every slot order, keeps the fewest misses, and never repeats
  a neighbour's layout. `big-three` (one 60% cell + two halves) and `wide-three` (full-width top + two halves) exist
  for this. If nothing fits, split the page, or reframe/regenerate the art. A region at the panel's own edge cannot be
  saved by cropping.
- **QA** (`check_focus`, part of `comic_qa.py`): FAILS any page where a required region is clipped by its cell, cut by
  the frame or occluded by a panel drawn above it, in 16:9 and in the Short (vertical pages outside the Short window
  only warn). It also warns on panels with no regions. Debug crops go to `out/<shot>/qa/focus/<page>-<id>-<orient>.jpg`:
  the source panel with the crop (cyan), the cell path mapped back (white) and the regions (green fits, red misses).
- Limitation: regions are checked against the panel still and the clip's registered area, not tracked through the
  clip. Keep camera moves gentle, or give the region headroom for a push-in.

## Varied transitions (every entrance and scene change; no back-to-back repeats)

No hard cuts and no single repeated crossfade: every scene change (and, where the renderer has cells, every panel
entrance) gets a transition, and two consecutive changes never share a type. This is the renderer default:

- **Explainers and other `/kit.js` stages** (`lib/stage-kit.js`): every scene change picks from
  `Webshot.TRANSITIONS` = `slide_left`, `iris`, `zoom_pop`, `wipe`, `slide_up`, `whip`, `fade`, `slide_right` in a fixed
  rotation (deterministic, so `check` and `render` match; never the same type twice in a row; the first scene has no
  transition). Override one scene with `Webshot.scene('name', build, { transition: 'iris' })`, or the whole stage with
  `Webshot.transitions('varied' | 'fade' | 'none' | ['wipe', 'iris'])`. Stages that build their own timelines (like
  `shots/why-farts-stink`) load `/kit.js` and call `Webshot.transition(tl, fromEl, toEl)` from their `show()` helper.
  Only whole scene sections move; entrances are added after the transition, so text is never sliced mid-animation.
- **Music stages** (`/music.js` loaded) keep the plain 0.35 s fade unless they opt in with `Webshot.transitions('varied')`
  (scene changes there are usually on bar lines, so check that the 0.45 s transition fits the beat).
- **Comic videos**: two levels, panel entrances + page transitions, with QA (`check_entrances`, `check_transitions`):

### Two-level transitions in the comic renderer (standing rule, 2026-10-13; renderer default)
1. **Panel entrances.** Every panel/cell animates in when it lands. The types are `fade`, `slide_left`, `slide_right`, `slide_up`, `slide_down`, `wipe`, `iris`, `zoom_pop`, `whip` (slide with motion blur) and `glitch` (scares/impacts).
   - Duration is 0.2-0.4 s.
   - No two consecutive panels in the whole video share an entrance.
   - The picker is auto by page mood: eerie gets fades, irises, wipes and slow slides; action gets whips, pops and fast slides; a panel with an impact SFX gets glitch, pop or whip. Override with `panels[i].entrance = {"type", "dur"}`.
   - Only the panel's own pixels move, revealing it over the background (e.g. the looping eyes).
   - The entrance finishes before the clip starts, so the anticipation beat is kept.
   - **Captions and SFX appear only after their panel's entrance has finished** and are never moved, so they cannot be clipped.
   - Exits are handled by the page transition. There are no per-panel exit animations yet.
2. **Page transitions.** Every page change gets its own transition (see "Page transitions" above). It always differs from the previous page's.
- **QA:** `check_entrances` covers level 1 (types, durations, no back-to-back repeats, done before the clip). `check_transitions` covers level 2.

### Page transitions in the comic renderer (rule, 2026-10-13, FRIGHT NIGHT)
- **No hard cuts between pages.** `C.page_transitions(spec)` gives every page boundary a 0.3-0.8 s transition centred on the turn: `crossfade`, `fade_black`, `slide_left` / `slide_right` / `slide_up` (push), `wipe_linear`, `wipe_diag`, `iris`, `whip` (push with motion blur), `flash`, `glitch` (`cut` only when asked for).
- **Spec:** `pages[i].pageTransition = {"type": ..., "dur": ...}` (the transition INTO page i), or leave it out for the mood auto-picker. Mood comes from `pages[i].mood`, else a page that opens on an impact SFX counts as `scare`, else `spec.mood`. `eerie` picks slower fades, dissolves to black, iris and diagonal wipes; `action` picks whips, flashes, slides and linear wipes; `scare` picks glitch or flash.
- **Never the same type twice in a row.** The picker also avoids the last 3 types and the previous family. A transition is never longer than 40% of either neighbouring page.
- **Only the art transitions.** The outgoing page keeps playing (clips freeze) and the incoming page shows its landed panels. Lettering is laid back on top unmoved and unmasked: the outgoing page's lettering until the boundary, the incoming page's from the boundary, just like a hard cut. So a caption can never be slid, wiped or cut, and clip timing is unchanged.
- **QA (`check_transitions`):**
  - valid types, 0.3-0.8 s, no consecutive repeats
  - a line sung across a page turn must be carried onto the new page
  - a warning when >15% of a clip sits under a transition
  - `--deep`: mid-transition frames' lettering must be pixel-identical to the plain frame
- **Test stills:** `comic_render.py SPEC --transition-test` writes a sheet of every type at 25/50/75%, plus the TO BE CONTINUED card.
- **TO BE CONTINUED card:** `spec.tbc = {"enabled": true, "text": "TO BE CONTINUED...", "seconds": 2.5}`. It hard-cuts to black after the last page, then the end card follows. Its seconds are added to the audio pad. QA checks ink loss and title-safe.
- **Spooky intro:** `intro.style: "drip"` hangs ink drips off the glyphs. `intro.lightning: true` replaces the sparkles with a lightning double-flicker and a forked bolt. Presets are in `C.INTRO_DRIP`.

## Seamless looping themed backgrounds (required step, 2026-10-13)
- **Pick a background theme per song in the plan.** `scripts/make_loop_bg.py --theme <blinking_eyes|starfield|neon_rain|embers|deco_gold> --orient landscape|vertical --out <assets>/bg/<theme>-<orient>.mp4` (default 9.6 s).
- **Generate both orientations.** Every motion is periodic in the loop, and a seam check (last->first frame diff vs the median frame diff) fails with exit 1 on a jump.
- **Theme guide:**
  - horror: `blinking_eyes`
  - space: `starfield`
  - cyber / dojo: `neon_rain`
  - fantasy: `embers` (embers + smoke)
  - 1920s / crime / luxury: `deco_gold` (black, art-deco gold sunburst fan + arcs + chevrons, a diagonal shimmer
    sweeping once per loop, per-ray glints, gold dust rising one screen per loop; CONCRETE JUNGLE COLD)
- **Spec:** `"bg_video": {"landscape": "bg/x-landscape.mp4", "vertical": "bg/x-vertical.mp4"}, "loop": true`. It plays full-frame behind every page on the song clock (seamless across page turns), and panels simply cover it, so no placement logic is needed. Media stays out of git.
- **QA's empty-slot check measures inside the panel clip path only**, so a black gutter is not flagged as empty art.

## Title intro and end card (every video and Short)

- **Title intro:** every video and Short opens on a title (explainers: a title scene; comic videos: the title logo
  intro below, on by default).
- **End card:** every video and Short ends on an end card (~3 s; channel credit + "LIKE AND SUBSCRIBE FOR MORE!" for
  Progressive Slop); music fades naturally under it. Comic renderer: `spec.endCard` (default on), `--endcard-test`.

### Title logo intro (comic renderer) (standing rule, 2026-10-13)
- **Every Progressive Slop video and Short opens with a title logo intro.** It is on by default in `comic_render.py` (`spec.intro`, defaults in `C.INTRO_DEFAULT`). It shows a bold logo of the song title in chunky Bangers lettering, with a chrome bevel gradient on each line, a heavy ink outline, a white keyline and a two-colour neon glow, plus an optional subtitle ("PROGRESSIVE SLOP PRESENTS").
- **Timing:** the logo drops in over 4 frames, from 118% down to 100%, and slams on the first beat at least 0.15 s into the video. The slam brings a white impact flash (0.16 s), a small screen shake (0.32 s, ±0.6% of width, 2% zoom) and star sparkles. The logo holds for `seconds` (default 2.6 s), then fades out over 0.35 s. It is overlaid on the opening panel with a 45% dim; if a song has a long silent lead-in, the slam still waits for that first beat. The Short gets its own intro, slamming on the first beat of the Short window.
- **Config:** `{"intro": {"title": "NEON DOJO", "subtitle": "...", "seconds": 2.6, "glow": [r,g,b], "glow2": [r,g,b], "chrome": [[r,g,b] x6], "subColor": [r,g,b], "rot": -4}}`. If the title is omitted, it is taken from `spec.title` (the part before " - "). In vertical, titles of two or more words split onto two lines.
- **`--intro-test`** writes only `OUT/intro_test_landscape.png` and `OUT/intro_test_vertical.png`; check these before every full render.
- **QA (`check_intro`)** fails if the intro is missing or disabled. It also fails if the logo tile loses any ink against a reference drawn on an oversized canvas (the same padded-canvas, expand=True rotate, crop-to-ink recipe as SFX tiles), or if the logo leaves the title-safe area or is sliced by the frame edge at any frame of the drop-in, shake or hold, in either landscape or vertical.

## No clipping, no cut-short text

- No title, caption, lyric, label or SFX past its box, panel, the frame edge or the title-safe area, in 16:9 or the Short.
- Captions and lyric lines show the **full** line and stay up until it is spoken/sung; never cut a line short, never
  cut audio mid-word at either end of the video or the Short (pick cut points in word gaps).
- Explainers: check the `npm run check` contact sheet for clipped text; comic videos: `comic_qa.py` and
  `scripts/comic_render_audit.py` enforce it.

## Kid-safe and publishing

- Kid-safe content: no gore, no alcohol, no guns aimed at anyone, modest outfits, kid-safe finishers.
- Channel brand rules (`channels/<channel>/style.json`) are hard constraints; for Progressive Slop everything is a
  robot (**no humans**, no living creatures).
- Upload to YouTube as **"No, it's not made for kids"** (audience setting), for both the video and the Short.
- Never commit media (images, video, audio); commit specs, code and docs only.


## Logotype intro (required on every video and Short, rule 2026-10-14)

- Design a per-song **logotype** image (badge/wordmark in the song's world and era: e.g. Art Deco gold for a 1920s
  crime story). Get Jason's approval, then set `intro.logotype` (path relative to assetsDir). QA **fails** a
  spec whose intro has no logotype asset, or whose file is missing.
- Build-in (`comic_lib.logotype_intro_frame`, starts on the first downbeat): gold sunburst rays sweep round
  (0-0.55 s) → the badge draws on clockwise (0.12-0.8 s) → a shine band sweeps across the letters (0.55-1.15 s)
  → a light glint pops (1.2 s) → slow 3 % push through the hold → fade. The flat outer background of the art is
  keyed out (flood fill from the border); the badge's own dark interior stays.
- The background is always moving: the logotype sits over the live opening page (its first panel is a clip, e.g.
  rain + searchlights over the city), dimmed ~45 %.
- Hold no longer than the beat needs: `intro.seconds` = a whole number of beats (4 beats ≈ 2.8 s at 86 BPM).

## Nothing on screen is ever static (rule 2026-10-14, delivery gate)

v3 felt like "it stops, then jumps": panels froze on their last clip frame for up to 15 s, splashes held one beat
on a still, and the end card was a frozen frame. Rules (shared renderer, `scripts/comic_lib.py` + `camera.py`):

- **Before a clip starts** the panel already moves: the per-cut camera move runs over the still from the moment it
  lands (the anticipation beat is a camera beat, not a freeze).
- **After a clip ends** it never freezes: its last 2 s ping-pong at half speed (slow-mo breathing tail,
  `TAIL_LOOP`/`TAIL_SPEED`) while the camera move continues.
- **Panels overlap in time**: the next panel lands while the current one is still moving; there is no dead
  wait because every landed panel keeps moving until the page leaves.
- **Page transitions flow**: the outgoing page keeps rendering live (clips looping, camera moving) until the
  incoming page covers it.
- **TO BE CONTINUED / end card** sit over the **live** last page (dimmed), never a frozen frame; the end-card boxes
  bob and the sunburst breathes. QA fails an end card / TBC configured with a still background.
- **No stills, ever**: every panel, splash, intro and end card has moving footage under it. Ken Burns on a still
  does not count (QA `check_all_clips` fails still-only panels).
- **Render gate** (`scripts/static_check.py VIDEO --max 0.4`): frame differencing (mean |Δluma| at 192 px wide,
  threshold 0.35) on the FINAL render; any stretch > 0.4 s **fails** and the renderer exits non-zero
  (`DELIVERY GATE FAIL`, details in `<video>-static.json`). Never deliver a render that fails it.
- The Short gets the same engine; cut denser (more, shorter panels) if the window still has slow stretches.

## Camera moves per cut (pan-in-place, shared: `scripts/camera.py`)

When a clip's aspect does not match its cell (e.g. a 16:9 clip in a tall half-screen cell) a fixed crop cuts
faces. Every cut instead gets ONE eased camera move: a crop window at the cell's aspect that moves over the
footage for the whole time the panel is on screen, steered by the **tracked** focus regions (faces / key action
are followed through the clip at ~1 fps with an NCC template search and interpolated in between). The same
window is applied to the still before the clip and to every clip frame, so the hand-off never jumps.
Explainers and any other renderer that crops footage into a cell use the same module (`camera.plan_move`,
`camera.track_regions`).

Move selection (per cut, from its faces, its cell, and the transitions on either side):

| situation | move |
|---|---|
| one face, a splash, or an outgoing zoom / iris | **push_in** (slow push toward the face, never tighter than the faces need: no extreme face close-ups) |
| 2+ faces that fill the cell with < 10 % slack | **pull_back** reveal (tight on the lead face → all faces) |
| faces fit with slack, outgoing whip | **whip** hand-off (pan accelerating into the whip's direction) |
| faces fit with slack | **drift** pan along the slack, ending in the outgoing transition's direction |
| faces fit together at every moment but travel further than the cell allows | **follow** (window tracks them) |
| faces spread side to side wider than the cell | **pan_h** face A → face B (hold, move, hold) |
| faces stacked / action up-down taller than the cell | **tilt_v** face A → face B |
| a single face is larger than the cell at some moment | **needs_bigger_cell**: the layout engine must give the panel a bigger cell (QA fails it as clipped; the builder's layout search scores it as a hard miss and picks another layout) |

- Direction flows into the outgoing transition (next panel's entrance on the page, else the page transition):
  `slide_left`/`wipe_left` → the move ends travelling left, `whip`/`wipe`/`slide_right` → right, `slide_up` → up.
- Every move eases in and out with a 25 % linear floor, so its speed is never zero (no static frames).
- Face margin: the planner widens its pad (6 → 20 %) until the cell's real (slanted, inset) shape holds the faces.
- **QA** (`camera_misses`, inside the focus check of `npm run check`): samples the move over the panel's whole
  screen time and fails when a face the move promises at that moment leaves the cell window (> 5 %).

## Clip prompt design (what Grok Imagine does well, rule 2026-10-14)

- **One simple action per clip.** At most 2 characters doing anything; anyone else is static / background.
- **The camera carries the drama**: push-ins, orbits, crane moves, rack focus, rain, smoke, light. Characters
  move little: a turn, a head tilt, a coat flare, a walk.
- **No contact or complex physics**: no grabbing, lassoing, grappling, handing objects over, hair used as a tool.
  Show the result (pose / aftermath) or keep it off-screen.
- **Faces medium-sized and stable**: no extreme push-in to a face close-up (that is where Uno turns into a
  skull); prefer 3/4 or profile, mouth closed. Lock wording: "smooth gunmetal face, closed full lips, no exposed
  teeth, no skull, no bone".
- **Start from a panel that already shows the end pose**: the clip only adds motion and atmosphere.
- **Too hard? Simplify the panel** and redraw it to what the generator can do, or split the beat into a
  comic sequence strip of simple sub-panels (COMIC_MODE.md, *Sequence strips*).

---
name: Progressive Slop character bible
description: >-
  Use before generating ANY panel, still, clip prompt or QA check featuring Uno,
  Aura, Ferro, Nickel or other Progressive Slop recurring characters, so looks
  never drift.
---
# Progressive Slop character bible

The locked masters are the single source of truth. Never rebuild a master that already exists. Always pass the master as a reference image AND name every signature item in the prompt text, because the reference alone is not enough. Re-read this before every batch.

## Locked masters (box: `/workspace/crime-comic/refs/`)
Each file is a multi-view sheet with face closeups and front, side and back views.
- Uno: `uno-1920s-MASTER-v2.jpg`
- Aura: `aura-1920s-MASTER-v3.jpg`
- Ferro: `ferro-locked.jpg`
- Nickel: `nickel-locked.jpg`

The originals are `uno-ORIGINAL-sheet.jpg` and `aura-ORIGINAL-sheet.jpg`. Rejected refs go in `refs/bad/`; never use them.

## Uno (hero)
- **Signature items (never drop):**
  - long PURPLE FUR COAT, worn open
  - thick gold chain with a large gold "1" pendant
- **Outfit:**
  - black pinstripe vest and suit with a black shirt and gold tie
  - gold pocket-watch chain
  - full-length black pinstripe trousers covering both legs
  - black-and-white wingtip shoes
  - black fedora over round chrome headphones
- **Face:**
  - entire head bright mirror-silver chrome, no skin
  - sculpted like a young Black American man in his 20s: full lips, broad nose, rounded cheeks
  - glowing red eyes
  - calm closed-lip smile
  - NOT a skull, NOT a Joker, no toothy grin, never the word "grin"
- **Build:** muscular, with chrome arms.

## Aura (heroine)
- **Signature items:**
  - long hair of black cables with glowing RED fiber strands
  - black fedora with a crimson band
  - round chrome headphones
- **Outfit:**
  - long black pinstripe coat over a black pinstripe vest and trousers
  - crimson shirt and crimson tie
  - black-and-white wingtip shoes
- **Face:** entire head mirror-silver chrome, no skin, modeled on a young Black woman in her 20s, glowing red eyes, soft closed-lip smile.
- Always modest and fully covered.

## Ferro (boss / antagonist)
- **Build:** big, heavy, square-jawed robot.
- **Face:** angular gunmetal-chrome armored face with a stern frown and red eyes.
- **Signature items:**
  - a gold MONOCLE with a chain over his right eye
  - a black cane with a gold top
- **Outfit:**
  - black double-breasted pinstripe suit with a dark red tie and red pocket square
  - black fedora over chrome headphones
  - black shoes

## Nickel (sidekick / informant)
- **Build:** lanky.
- **Face:** smooth narrow chrome face with a sly closed smile, red eyes, and a toothpick in the corner of his mouth.
- **Signature items:**
  - grey-brown bowler hat
  - long tan trench coat
- **Outfit:**
  - grey vest, black shirt and black bow tie
  - grey pinstripe trousers and black shoes
  - chrome headphones

## Universal rules
- Kid-safe, no humans. Background figures are silver red-eyed robots.
- One simple action and at most 2 characters per clip.
- Use a locked static camera for character clips; camera moves make the generator strip clothes.
- No face push-ins, reversed footage or replays.
- Filler shots are scenery with no people.

## Pre-flight checklist (before generating)
1. Is each character's master attached as a reference?
2. Is every signature item and outfit piece above named in the prompt?
3. Is the camera locked?

## QA checklist (every panel and clip, every frame sampled)
- All signature items are present (Uno's coat and "1" chain, Aura's red-strand hair, Ferro's monocle, Nickel's bowler and trench coat).
- Fully clothed, with no exposed legs or bare metal limbs.
- Faces are chrome, never human or Caucasian-looking, and the red eyes are visible.
- Smiles are closed-lip.
- SFX and lettering never cover a face, and every SFX is motivated by on-screen action. Use the yellow BAM at most once per video.
- Any failure gets regenerated before it's shown to Jason.

## Fix workflow (lessons from Jason, Oct 15 2026)
- **Only fix what Jason names.** The audit list is a suggestion; confirm with him which shots to redo. Never redo scenes that already work.
- **Never redraw a whole shot to fix a detail.** Use Grok Imagine's selective edit: mask only the broken region on the ORIGINAL frame. If that's impossible, do a minimal edit of the original frame and never a fresh generation.
- **Keep the slick glossy rendering of the original clips.** Fresh generations come out flatter and lose it.
- **Check physical logic.** Example: a door peephole slit shows only eyes, never a head poking through.
- **Show the fixed still before animating.**

- Uno build: always broad, powerful shoulders filling the coat. A skinny frame reads as "Joker". If a frame looks narrow, widen it with a Precise Edit painted on the shoulder band (Oct 15 2026).
- Hard shots: if Grok Imagine drifts or zooms, split the shot into 2-3 short clips from the same still, each with one simple action (blink, smoke, breath), and cut them together. Strict tripod wording helps; Quick Animate ignores prompts and moves the camera, so avoid it (Oct 15 2026).
- Keep the pass tight: only redo shots Jason named. Never widen into walking, cards, cheers, or other working scenes. One fix at a time with Precise Edit; split hard animations into short clips rather than regenerating whole masters (Oct 15 2026).
- Keep the pass tight: only redo shots Jason named; never widen into working scenes. One Precise Edit at a time (Oct 15 2026).
- Be efficient: script every deterministic step (frame grabs, contact sheets, stabilization, renders, QA gates, chunked Mac transfers with md5) instead of doing it by hand; reserve manual/agent judgment for creative calls (Oct 15 2026).

## Fix list gate (Oct 15 2026)
- Every shot Jason flags goes into `fixlist.md` in the project folder immediately (shot id, issue, his words, status).
- Scope changes ("only the door") never silently drop earlier flags; ask or keep them on the list.
- Before calling any render final: walk the fixlist, grab a frame of each item from the rendered video, and confirm it is fixed. Report the checklist with the delivery.
- A render with an open fixlist item is a preview, not a final.
- Clothing rule for EVERY clip prompt: start with "The robot humanoid is fully clothed at all times: full-length suit trousers, shoes, coat and sleeves always cover every limb; no bare metal legs or arms ever visible." QA: crop the legs on walking shots and step through at 4fps; any bare chrome limb fails (Oct 15 2026).
- Walking shots: Grok keeps drawing chrome knees even with explicit clothing prompts. Check knees with a 2fps bottom-half crop at full size, never tiny strips. Fastest fix: reframe thigh-up (crop) so legs are out of frame; plan new walking shots as waist-up from the start (Oct 15 2026).
- Walking shots: Grok keeps drawing chrome knees even with explicit clothing prompts. Check knees with a 2fps bottom-half crop at full size, never tiny strips. Fix: reframe thigh-up so knees stay out of frame (Jason: "keep the knee out"); plan new walking shots waist-up from the start (Oct 15 2026).
- Headphones: slim, close-fitting, small silver headphones (about half the size models default to). Never massive cans (Jason, Oct 15 2026).

## Start-frame gate (Oct 15 2026)
- The video model only sees the start frame + prompt, never the character sheets. So every start frame must match the master sheets BEFORE animating.
- Build a side-by-side (start frame | master sheet) and check: headphone size (slim), mouth (closed-lip, no teeth), coat + gold "1", hat, build (broad), clothing covers all limbs.
- Fix any mismatch with Precise Edit on the start frame, never by hoping the prompt overrides it.

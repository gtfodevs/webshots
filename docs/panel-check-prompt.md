# Panel QA check prompt (run on EVERY generated panel before accepting)

Open the panel and each locked reference for every character in it, side by side. Answer each line PASS/FAIL with a reason. Any FAIL = regenerate (adjust prompt), never animate.

## 1. Identity (per character, vs locked sheet)
- Face shape matches sheet? (Uno: broad dark gunmetal face, wide nose, full lips, gold grill visible or implied; NOT a skull, NOT Joker, NOT slim/feminine. Aura: smooth dark chrome face, glowing red eyes, softer features.)
- Head gear matches? (Uno: his cap/fedora per the video's sheet + his own headphones. Aura: headphones, long hair as on sheet.)
- Body proportions match? Tall and slim like the sheet, not stocky or squat, in every pose including sitting.
- Outfit matches the video's locked costume (colors, chain, coat, tie). Aura modestly dressed.
- Would a viewer instantly name this character from the thumbnail alone?

## 2. Anatomy / weirdo renders
- Every hand connects to a visible arm and shoulder; nothing sprouting from neck/torso.
- Correct count of arms, legs, fingers (5), eyes (2), heads (1).
- No melted, fused or doubled limbs; no limbs merging into props or other characters.
- Joints bend plausibly; feet on the ground or clearly mid-jump.

## 3. Scene
- Only the characters named for this panel; no extra robots, no humans.
- No stray text, logos, or trademarked items (e.g., UNO cards); kid-safe props (no alcohol, no guns aimed at anyone).
- Faces and key action sit away from edges so 16:9 and the 9:16 Short crop both keep them.

## 4. Verdict
PASS only if every line passes. Log failures and the prompt fix used.

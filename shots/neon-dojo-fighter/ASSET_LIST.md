# Neon Dojo fighter — asset generation list (lean)

## Rules for every image
- One pose per image; side view, facing right; full body; flat **#00FF00** background.
- No shadows, no text. Same character sheet prompt prefix every time, for a consistent design.
- Robots: silver chrome, red eyes, headphone ears. 32-bit SF2/CPS-2 pixel art detail.
- Method: THE sprite method.
  - The master upper body comes from idle A.
  - Limbs are swapped per pose.
  - Shared palette per character.
  - BOB table for the walk; pinned foot.
- Output: assets/fighter/<char>/<pose>.png

## Per-fighter pose set (17 images)
| # | Pose | Use |
|---|---|---|
| 1–2 | idle_a (exhale), idle_b (inhale, chest +1px) | 4-frame breathing loop, A/B with holds |
| 3–6 | walk_contact_L, walk_pass_L, walk_contact_R, walk_pass_R | walk cycle |
| 7–8 | punch_windup, punch_extend | jab / strong |
| 9–10 | kick_chamber, kick_extend | kick |
| 11–12 | special_charge, special_release | special; the effect is a separate sprite |
| 13 | block (standing guard) | block |
| 14 | hit (head snapped back) | hit reaction |
| 15–16 | ko_fall (airborne back), ko_down (lying flat) | KO |
| 17 | victory | win screen / ending |

**APPROVED LEAN PLAN (Jason, 2026-10-12):**
- **Full set, 17 images each:** uno, aura, tekko, lotus, shogun = **85**.
  - SHOGUN.EXE (processed): 16 sources incl. bonus `thrust_extra` (used as a boss `thrust` move); no ko_fall (synthesised from hit, tilted back), breath from idle_a. Scaled to 228 px (1.15x Uno). Red katana glow, slash arcs (punch_extend, special_release), charge aura (special_charge) and KO smoke (ko_down) are additive fx layers; cape, armour trim and blade steel stay on the body. kick_chamber is a copy of walk_pass (regen candidate). Walk _R = legs mirrored about the hip inside a leg window (cape tail and blade stay put). No shared master core: the cape breaks the paste seam.
- **Montage-only, 4 images each:** kaze9, raijin = **8**.
  - `idle_a` (stance; it is also the master upper body, and the engine adds a ±1 px breath bob so the idle never freezes)
  - `attack` (their signature strike, extended)
  - `hit`
  - `ko_down`

  The engine maps punch/kick/special to `attack`, and ko_fall to a tilted `hit`. walk, block and victory are never used for these two (QA enforces this through `FIGHT.MOVESET.montage`).
- **Fighter poses total: 93.**

## Special effects (#00FF00, 5 effects × 2–3 frames = 12 images: Uno slash 3, Aura orb 3, piston 2, lotus 2, katana 2; KAZE-9 / RAIJIN effects are dropped: their `attack` pose carries the effect)
- Uno: purple sword-slash arc
- Aura: cyan magic orb
- Piston palm blur
- Lotus petal swirl
- Red katana wave

## Hit sparks: 3 images
- small hit
- big hit
- block spark (blue)

## Portraits: 7 bust portraits + 4 beaten variants = 11
One bust per fighter for select and VS, facing right (mirrored in-engine). Beaten variants (cracked, eyes dim) only for the four rivals in the "Count it out" beat: tekko, kaze9, raijin, lotus.

## Cutscene close-ups: 13 images (2-frame loops are made in-engine with a palette or offset)
1. Neo-Kyoto rain skyline (wide)
2. Uno's eyes powering on, red (extreme close-up)
3. Uno's pendant "1" glint
4. Flashback: young Uno bows to Sensei Gearhart in the dojo
5. Dojo in flames
6. SHOGUN silhouette in the fire, red visor
7. Uno's fist clenched with sparks
8. Aura close-up: hair blowing, cyan palm magic
9. Aura chained in server cables, breaking free
10. Uno + Aura rooftop backs, blimp
11. SHOGUN's helmet rise / eye ignite
12. SHOGUN holding the dojo belt
13. Ending: belt returned, Sensei nods at the rebuilt dojo, sunrise

## Super cut-in panels: 3 images
- Uno eyes band
- Aura eyes band
- SHOGUN eyes band (speed lines are drawn in-engine)

## Stage backgrounds: 5 stages × 2 images + 1 map = 11
For each stage: (a) a far/mid background with no floor; (b) a floor strip with a clear ground line, for grounding.
- **Neon Rooftop Dojo:** night, lanterns, city.
- **Rain Alley Night Market:** noodle stalls, a cheering crowd.
- **Neo Train Yard:** power station, sparking cables.
- **Pagoda Hologram Garden:** cherry blossom holograms.
- **Server Temple Throne:** red, pillars, data waterfalls.
- **Character-select world map:** neon Asia map. Single image.

## UI / misc: 4 images
- NEON DOJO logo
- VS emblem
- K.O. emblem
- Sensei Gearhart NPC: 1 standing pose for cutscenes

## Grand total (approved lean plan)
| Group | Images |
|---|---|
| Fighter poses (5 × 17 + 2 × 4) | 93 |
| Special effects | 12 |
| Hit sparks | 3 |
| Portraits | 11 |
| Cutscene close-ups | 13 |
| Super cut-in panels | 3 |
| Stage backgrounds | 11 |
| UI / misc | 4 |
| **Total** | **150** |

Drop-in: put each pose as `channels/progressiveslop/assets/neon-dojo-fighter/source/<char>/<pose>.png`. The pose names are exactly as listed above (`idle_a`, `idle_b`, `walk_contact_L`, …).

## Engine work (parallel, placeholder boxes OK)
- Health bars with a damage trail; timer; round pips
- Hit-stop, sparks, screen shake
- VS screen slide; banners
- Combo counter
- Beat-snapped choreo for: moves, cut-ins, montage cuts
- Freeze-frame palette invert
- Vertical HUD layout for the Short

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

**Total: 7 fighters × 17 = 119 images.**
- Fighters: uno, aura, tekko, kaze9, raijin, lotus, shogun.
- Leaner fallback: opponents TEKKO, KAZE-9, RAIJIN and LOTUS appear only in the montage, so they can skip walk_pass_L/R and victory. That makes 14 each, for a total of **107**.

## Special effects (#00FF00, 2–3 frames each = 14 images)
- Uno: purple sword-slash arc
- Aura: cyan magic orb
- Piston palm blur
- Wind afterimage streak
- Thunder bolt
- Lotus petal swirl
- Red katana wave

## Hit sparks: 3 images
- small hit
- big hit
- block spark (blue)

## Portraits: 7 images, plus 7 KO'd variants
One bust portrait per fighter for select and VS, facing right (mirrored in-engine). Each also has a "beaten" variant: cracked, eyes dim. **Total: 14.**

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

## Stage backgrounds: 6 stages × 2 images = 12
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

## Grand total
| Version | Count |
|---|---|
| Full | **≈188 images** |
| Lean fallback | ≈176 images |

## Engine work (parallel, placeholder boxes OK)
- Health bars with a damage trail; timer; round pips
- Hit-stop, sparks, screen shake
- VS screen slide; banners
- Combo counter
- Beat-snapped choreo for: moves, cut-ins, montage cuts
- Freeze-frame palette invert
- Vertical HUD layout for the Short

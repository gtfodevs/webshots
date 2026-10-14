# CONCRETE JUNGLE COLD — storyboard (draft v1)
Song: "Concrete Jungle Cold - Hip Hop Classic" (Progressive Slop), 198.0 s, 86.1 BPM, 71 bars. Boom-bap with piano lead, smoky female alto hooks (Aura) and smooth male rap (Uno).
World: an original Progressive Slop 1920s Prohibition city called **Chromopolis**. It has art-deco towers, speakeasies (they serve glowing oil sodas, no alcohol), vintage chrome getaway cars, and rain on brass and marble. It is a story of rising to the top: two nobodies from the block take the city from the rival boss **Don Ferro**. Ferro is a hulking gunmetal-chrome mob boss robot in a white pinstripe suit with a monocle over one red eye and a cigar-shaped exhaust that puffs steam. His lieutenant **Slick Nickel** is a thin chrome robot with a bowler hat. He looks loyal but is the betrayer.
Rules: no humans, and every robot is chrome with red eyes and headphone ears. The tone is kid-safe: heists, rivalry and wits, no gore, no drugs, no drinking. Tommy guns and pistols are props only. They stay holstered, sit in violin cases or point at the sky or the floor, and never point at anyone. Every panel is a mid-action moment with an extreme angle and SFX lettering. No static posing.
Costumes (locked faces from /workspace/progressive-slop-refs/uno-locked.jpg and aura-locked.jpg):
- UNO: same sculpted chrome face, lips, gold grill, red eyes, headphones. He wears a black fedora instead of the cap, a purple pinstripe three-piece suit, a purple fur-collared overcoat and the iced gold "1" chain.
- AURA: same smooth dark chrome face, glowing red eyes, headphones, and long wire hair with glowing red strands. She wears a modest crimson knee-length beaded flapper dress with a high neckline and long sleeves (or a crimson tailored coat for the heist), with a beaded headband or cloche over her headphones.
Palette: midnight blue and black, art-deco gold, crimson, purple, and wet neon reflections.

## Title intro (0.0 – ~3.0 s; slams on the first beat ≥0.15 s)
The logo reads "CONCRETE JUNGLE COLD" in an art-deco gold logo. Bangers lettering is stacked on 3 lines, each with a polished gold bevel gradient, a heavy black ink outline and a white keyline. The glow is two-tone, warm gold and crimson. Behind it is a sunburst deco fan with gold rays. Subtitle: "PROGRESSIVE SLOP PRESENTS". The logo slams with a white flash, shake and gold sparkles over panel 1 dimmed by 45%. Alternative look: a gold-leaf marquee sign with chasing bulbs.

## Looping background
- **New preset `deco_gold` (proposed for scripts/make_loop_bg.py):** thin art-deco gold lines (chevrons and sunburst fans) on midnight blue. A slow gold shimmer sweeps diagonally, with drifting gold dust and a faint cigar-smoke wisp layer (soft noise that scrolls up). It loops seamlessly at 4 s. Landscape and vertical.
- **Fallback with existing presets:** `neon_rain` (rainy skyline mood, tinted gold/crimson in post) for street pages. `embers` recoloured gold works as "gold dust" on penthouse and jazz-club pages.
- Commands: `python3 scripts/make_loop_bg.py --theme neon_rain --orient landscape --seconds 4 --out bg/rain_land.mp4` (plus vertical). After `deco_gold` is added: `--theme deco_gold`.

## Beats (time = lyric/section anchor; chars = refs needed; shotKind vehicle/fx = no characters named)
| # | Time | Lyric | Panel (action, angle, SFX) | Chars / shotKind | Focus | Transition |
|---|------|-------|----------------------------|------------------|-------|-----------|
| 1 | 0.0–9.4 | (intro piano) | Extreme high angle down onto rainy deco Chromopolis at night, with searchlights criss-crossing. Lightning: KRAKOOM | fx (city) | skyline spire | Page 1 fades in from black under the logo |
| 2 | 9.46 | "Concrete jungle, cold, stories untold" | Low worm's-eye shot: Uno and Aura step out of a rain-soaked alley as nobodies, Uno's overcoat whipping in the wind, puddle SPLASH | Uno, Aura | both faces, red eyes | Slide in from left on the beat |
| 3 | 16.06 | "Diamonds in the rough, souls bought and sold" | Through a jeweller's window: Don Ferro's goons haul diamond crates past them. Aura's eyes narrow in the glass reflection. CLINK | Aura, Don Ferro | Aura's reflection | Iris wipe |
| 4 | 29.98 | "Heart made of gold" | Close-up: Uno flips his gold "1" chain in his fist like a vow, gold flare. SHING | Uno | chain + grill | Punch-in zoom |
| 5 | 33.66 | "Peep the script… ain't no actor" | Speakeasy door slot SNAPS open. Dutch angle as Uno rap-talks the password, and Aura already slips past the bouncer bot | Uno, Aura | Uno lips / slot eyes | Page turn (word gap 31.55) |
| 6 | 38.78 | "City lights flicker, souls get sicker" | Smoky jazz club splash: Aura sings on stage mid-twirl, beads flying. Don Ferro in the booth tips his monocle. Jazz notes, WAH-WAH | Aura, Don Ferro | Aura face, Ferro monocle | Smoke dissolve |
| 7 | 41.82 | "Hustle every minute, make it quicker" | Overhead shot: Uno slaps the cards down and wins Ferro's bet, gold coins EXPLODE upward. CHA-CHING | Uno, Don Ferro | coin burst | Whip pan |
| 8 | 44.26 | "Concrete jungle, cold, stories untold" (chorus) | Ferro grabs Uno's shoulder from a towering low angle, cigar exhaust puffing, and recruits them. Slick Nickel smirks behind. HMPH | Uno, Ferro, Slick Nickel | Ferro grin | Page turn |
| 9 | 49.84 | "Diamonds in the rough…" | Montage strip: Uno and Aura on runs, crates swinging off cranes at the docks, deco tower climbing. THUNK | Uno, Aura | crate swing | Slide up |
| 10 | 60.90 | "Survival of the fittest, heart made of gold" | Vintage chrome getaway car drifting a rainy corner, tyres spraying sparks, gold bags in the rumble seat. SKREEEE | vehicle | car grille | Speed-line wipe |
| 11 | 66.76 | "Block to the booth, undeniable proof" | The heist plan: Uno slams a blueprint of the FIRST CHROME BANK vault onto the table, extreme close on his gold grill grin. WHAM | Uno, Aura | blueprint + grin | Page turn |
| 12 | 72.42 | "Lost in the maze, caught in a daze" | Aura, in her crimson coat, cartwheels through a red laser grid in the bank's marble corridor, mid-flip. ZZT-ZZT | Aura | Aura face in lasers | Diagonal slash |
| 13 | 75.86 | "Paper dreams, urban haze" | Vault door cracked: Uno spins the giant brass dial, his headphones listening to the tumblers, gold light blasting out. KA-CHUNK | Uno | dial + ear | Vault-door iris |
| 14 | 78.36 | "Concrete jungle, cold, watchin' it unfold" | Interior splash: the vault, mountains of gold bars and bonds. Aura tosses a stack and paper flutters. FWOOSH | Uno, Aura | both, gold glow | Zoom splash |
| 15 | 82.68 | "Heart made of gold… in the cold" | BETRAYAL: the vault door SLAMS behind them, and through the bars Slick Nickel tips his bowler and pockets the key. KLANG | Slick Nickel (Uno, Aura bg) | Nickel smirk | Hard flash (beat) |
| 16 | 89.32 | "Wisdom in the streets, deeper than the beats" | Aura's glowing red wire hair snakes into the lock and picks it. Extreme macro, sparks. TIK-TIK-CLAK | Aura | hair strands in lock | Page turn |
| 17 | 94.66 | "Pen is a weapon, words connectin'" | Uno at a payphone, coat flaring, calling the whole city's crews, with phone lines lighting up across the deco map. RRRING | Uno | Uno face | Line-trace wipe |
| 18 | 100.66 | "Concrete jungle, cold, stories untold" (chorus) | Police-bot sirens swarm the bank. Uno and Aura burst out of the vault roof on a chrome cable, mid-air. WHOOOM | Uno, Aura | silhouettes vs searchlight | Page turn |
| 19 | 111.70–121.6 | "…watchin' it unfold / Survival of the fittest" (low-energy breakdown) | Rooftop chase in the rain: the getaway car leaps a gap between deco towers, and the moon cuts off the wheels. VROOOM | vehicle | car mid-leap | Slow push, rain smear |
| 20 | 124.42 | "flame burns bright… we still fight" | DOUBLE-CROSS: at Ferro's warehouse Nickel hands Ferro the stolen gold, then swaps the crates. They are filled with Uno's purple confetti. Ferro roars. POOF! | Don Ferro, Slick Nickel | Ferro's furious face | Page turn |
| 21 | 128.32 | "No surrender, break the fetter" | Uno kicks the warehouse doors in, Aura at his side, prop tommy-gun case slung and closed. Dramatic backlight. BOOM | Uno, Aura | both faces | Shockwave wipe |
| 22 | 134.28 | "Concrete jungle, cold…" (final chorus begins) | Showdown: Uno and Ferro grapple chest to chest, coats flaring, and Uno flips Ferro onto the confetti pile. KRAK! | Uno, Don Ferro | locked eyes | Beat-cut |
| 23 | 145.54 | "Concrete jungle, cold, stories untold" | Aura lassos Slick Nickel's bowler hat with her glowing wire hair and yanks him off his feet as he runs. YOINK | Aura, Slick Nickel | Aura's smile | Whip pan |
| 24 | 150.98 | "Survival of the fittest, heart made of gold" | Newsboy-bot newspaper spinning in, extreme dutch: "UNO & AURA RULE CHROMOPOLIS!" Gold flare. SPIN-SPIN | fx (newspaper) | headline | Spinning newspaper |
| 25 | 156.68–177.9 | "Concrete jungle, cold… heart made of gold" | TRIUMPH PENTHOUSE splash: Uno and Aura on a deco penthouse balcony, gold dust raining, the city lit below. Uno raises his "1" chain and Aura's beads glitter. FLASH | Uno, Aura | both faces, chain | Zoom splash, page turn |
| 26 | 179.94 | "concrete cold… spirit bold" | Quiet beat: Aura sets the gold crown-shaped hat on Uno, and the clinking oil-soda glasses spark. TING | Uno, Aura | hands + glasses | Smoke dissolve |
| 27 | 184.80 | "Heart made of gold, in the cold" | TWIST: an envelope slides under the penthouse door with a black wax seal shaped like a monocle. Aura picks it up and her eyes flare | Aura | envelope seal | Slow push |
| 28 | 189.40–194.9 | "concrete cold, but the spirit bold" | CLIFFHANGER: far below in the rain, Don Ferro stands outside a jail-bot truck with the cell door open and empty. He tips his hat up at the penthouse and his monocle glints. "TO BE CONTINUED…" | Don Ferro | monocle glint | Iris close to black |

## End card (last ~3 s, 195–198 s; also on the Short)
The final frame holds under the gold deco logo, with "Uno and Aura — hip-hop fun, dressed up." and "PROGRESSIVE SLOP" on a gold sunburst. Gold dust drifts.

## Short window (vertical)
**128.30 → 177.95 s (49.6 s).** It starts in the word gap after "we still fight" (128.27/128.32) and ends after the final "heart made of gold" (177.93/177.98). It covers the double-cross payoff, the warehouse showdown, the final chorus and the penthouse triumph (beats 21–25). The intro logo slams on the first beat after 128.3.

## Page plan
P1 beats 1–4 (city/vow) · P2 5–8 (speakeasy & recruitment) · P3 9–10 (rise montage) · P4 11–15 (heist + betrayal) · P5 16–17 (escape plan) · P6 18–19 (chase) · P7 20–21 (double-cross) · P8 22–24 (showdown) · P9 25–26 (penthouse) · P10 27–28 (cliffhanger). No hard cuts between pages; every turn lands in a lyric gap.

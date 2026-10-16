#!/usr/bin/env python3
"""Deadstars story plan -> plan.md, generate_jobs.json, motion.txt, villain_brief.md. No images generated."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'neon-dojo-comic', 'v3'))
import make_v3_spec as NDS   # reuse the builder's character anchor (ANCHOR_HEAD / ANCHOR_CAST / ANCHOR_TAIL)
TL = json.load(open(os.path.join(HERE, 'timeline.json')))
B = TL['beats']
def snap(t): return round(min(B, key=lambda b: abs(b - t)), 3)
def lyric_at(t):
    c = [l for l in TL['lyrics'] if l['t'] - 0.6 <= t < l['end']]
    return c[0]['text'] if c else '(instrumental / vocal chops)'
REF_CREW = '/home/box/agent-data/agents/7ab6020d-de13-47d8-8ee8-1d6ca8bc0c89/assets/1a70147613238d45a1d50100c327a4beaf976b8a58dab1b1971802446bbc5cbb.jpg'
ASSETS = '/workspace/deadstars-comic'   # media lives on the box, not in git
REF_VILLAIN = os.path.join(ASSETS, 'refs', 'deadstar-court.jpg')   # generate first from villain_brief.md

CAST = {
 'Uno': 'Uno (chrome robot, round smooth chrome dome head, red eyes, headphone ears, purple fur coat, gold "1" chain)',
 'Aura': 'Aura (beautiful grey chrome robot face, red eyes, headphone ears, flowing dark crimson hair, modest crimson bodysuit, cyan light magic)',
 'NULLSTAR': 'NULLSTAR (very tall thin chrome ringmaster robot, red eyes, headphone ears, chest core of a dead star - a black sphere ringed by a dim red corona, jagged crown of broken black star-shards, long violet-black tailcoat, cane topped with a small dead-star orb)',
 'GRAVEL': 'GRAVEL (hulking chrome brute robot, red eyes, headphone ears, huge fists crusted with grey asteroid rock, dented shoulder plates)',
 'HECKLE': 'HECKLE (twin small round flying chrome drones, red eyes, headphone ears, megaphone-shaped mouths, tiny hover jets)',
}
ANCHOR_EXTRA = {
 'NULLSTAR': 'NULLSTAR: very tall thin chrome ringmaster robot, black dead-star chest core with a dim red ring, jagged black shard crown, violet-black tailcoat, dead-star cane.',
 'GRAVEL': 'GRAVEL: hulking chrome brute robot, grey asteroid-rock fists, dented shoulder plates.',
 'HECKLE': 'HECKLE: twin small round flying chrome drones with megaphone mouths.',
}
ANCHOR_CAST = dict(NDS.ANCHOR_CAST, **ANCHOR_EXTRA)
def anchor(chars):
    return ' '.join([NDS.ANCHOR_HEAD] + [ANCHOR_CAST[n] for n in ANCHOR_CAST if n in chars] + [NDS.ANCHOR_TAIL])

STYLE = ("{shot}: {scene}. {chars}. All robots chrome with red eyes and headphone ears, no humans, kid-friendly. "
         "Setting: the Deadstar Arena, a floating colosseum built on the cold husk of a dead star, black space full of burnt-out grey stars, "
         "violet nebula, red warning lights, a crowd of robot spectators. 1990s superhero comic panel, bold ink, heavy blacks, halftone, "
         "speed lines, impact flash, neon magenta, cyan and gold, 16:9, no text.")
MOTION = "{action}. {cam}. Single continuous shot, slow subtle motion, every character stays fully in frame."

P = []
def page(pid, layout, splash, section, stakes, panels): P.append(dict(id=pid, layout=layout, splash=splash, section=section, stakes=stakes, panels=panels))
# panels: (id, slot, time, beat, shot, scene, chars, action, cam, sfx)

page('p01', 'slant-two', None, 'intro (0-8.7 s, instrumental + "na na" chops)',
 'The Crown of Light hangs over the Deadstar Arena; whoever loses tonight is made the arena clown forever.', [
 ('d01', 'a', 0.19, 'The Deadstar Arena floats on a burnt-out star; a single gold crown of light spins above it.', 'Extreme wide establishing shot',
  'the floating Deadstar Arena colosseum on the grey husk of a dead star, a glowing gold crown of light spinning high above it, dead grey stars all around',
  [], 'the crown of light slowly spins, dust drifts past the dead stars', 'locked camera', None),
 ('d02', 'b', 4.4, 'NULLSTAR, the ringmaster, lifts his dead-star cane: the show (and the clown hunt) begins.', "Worm's-eye view",
  'NULLSTAR standing on the arena balcony raising his dead-star cane, red spotlights sweeping, the robot crowd roaring behind him',
  ['NULLSTAR'], 'NULLSTAR slowly raises the cane, spotlights sweep', 'locked low camera', None),
])
page('p02', 'tilt-three', None, 'intro (8.7-17.1 s, instrumental build)',
 'Uno walks in as the underdog; the Deadstar Court has already picked him as tonight\'s clown.', [
 ('d03', 'a', 8.71, 'Uno and Aura step out of the launch tunnel into the blinding arena lights.', 'Low tracking-angle medium shot',
  'Uno and Aura walking side by side out of a dark launch tunnel into blinding arena floodlights, confetti of grey stardust',
  ['Uno', 'Aura'], 'both robots take one slow step forward, lights flicker', 'locked camera', None),
 ('d04', 'b', 12.1, 'The HECKLE drones swoop down and project a giant holographic clown nose onto Uno\'s face.', 'Dutch angle close-up',
  'the twin HECKLE drones hovering in front of Uno, beaming a big red holographic clown nose onto his chrome face, Uno frowning, Aura glaring at the drones',
  ['Uno', 'Aura', 'HECKLE'], 'the drones bob in place and the hologram flickers', 'locked camera', 'HONK!'),
 ('s05', 'c', 15.6, 'Title-page splash: the whole Deadstar Court lines up against Uno and Aura across the arena floor.', 'Splash, extreme wide low angle',
  'Uno and Aura on one side of a cracked arena floor facing NULLSTAR, GRAVEL and the twin HECKLE drones on the other side, dead star glowing dim red behind them',
  ['Uno', 'Aura', 'NULLSTAR', 'GRAVEL', 'HECKLE'], 'capes and hair sway, the dead star pulses dimly', 'locked camera', None),
])
page('p03', 'diagonal-three', None, 'verse 1 - man (17.1-24 s): "They tried to bring me down and make me play the clown"',
 'GRAVEL tries to flatten Uno in front of everyone; if Uno stays down, the clown nose becomes permanent.', [
 ('d06', 'a', 17.12, 'Wind-up: GRAVEL rears back a boulder-sized fist over Uno.', 'Extreme low angle',
  'GRAVEL towering over Uno, rearing back a huge asteroid-rock fist, the dead star behind his head like a halo',
  ['GRAVEL', 'Uno'], 'GRAVEL pulls the fist back slowly', 'locked low camera', None),
 ('d07', 'b', 19.4, 'Impact: the fist slams Uno into the arena floor.', 'High overhead angle',
  'GRAVEL\'s rock fist slamming Uno flat onto the cracked arena floor, a ring-shaped shockwave of dust and sparks',
  ['GRAVEL', 'Uno'], 'the dust ring spreads outward slowly', 'locked overhead camera, slight shake', 'KRUNCH!'),
 ('d08', 'c', 21.9, 'Reaction: the robot crowd laughs; HECKLE drones blare "CLOWN!" while holographic tomatoes rain down.', 'Wide crowd shot',
  'the robot crowd pointing and laughing, the twin HECKLE drones blaring from their megaphone mouths, glowing hologram tomatoes falling toward Uno lying in a crater',
  ['HECKLE', 'Uno'], 'the hologram tomatoes drift down, the drones bob', 'locked camera', 'HA-HA-HA!'),
])
page('p04', 'inset-two', 'full', 'verse 1 - man (24-34.5 s): "But I just flipped the script" / "She held me down through it all, and now we take the crown"',
 'Aura stands over him and holds the line; Uno flips the script with the first counter of the night.', [
 ('d09', 'a', 23.98, 'Aura\'s cyan shield dome slams down over Uno; the next rock fist cracks against it.', 'Over-the-shoulder Dutch angle',
  'Aura kneeling over fallen Uno with one arm raised, a cyan light shield dome blocking GRAVEL\'s rock fist, sparks flying off the shield',
  ['Aura', 'Uno', 'GRAVEL'], 'the cyan shield ripples where the fist hits', 'locked camera', 'KLANNG!'),
 ('d10', 'b', 27.9, 'Uno grabs Aura\'s offered hand - she pulls him up.', 'Extreme close-up',
  'Aura\'s hand gripping Uno\'s chrome hand, cyan light glowing between their fingers, gold "1" chain swinging',
  ['Aura', 'Uno'], 'the cyan glow pulses between the hands', 'locked camera', None),
 ('s11', 'splash', 30.9, 'Flip the script: Uno back-flips over GRAVEL and kicks the clown hologram right back at him.', 'Splash, upside-down extreme angle',
  'Uno mid back-flip upside down over GRAVEL, kicking the red holographic clown nose onto GRAVEL\'s face, Aura below with cyan light trailing, purple fur coat flaring',
  ['Uno', 'GRAVEL', 'Aura'], 'Uno hangs at the top of the flip, the coat ripples', 'locked camera', 'FLIP!'),
])
page('p05', 'tilt-three', None, 'verse 2 - woman/man (34.5-47.9 s): "They used to look so tough, but I\'m a diamond in the rough" / "calling every bluff"',
 'Round two against GRAVEL: if Uno can\'t crack the rock, the Court keeps its tough-guy act and the crowd stays against him.', [
 ('d12', 'a', 37.08, 'Wind-up: Uno plants his feet, fist glowing diamond-white.', 'Low three-quarter angle',
  'Uno in a deep stance pulling back a fist that glows bright diamond-white, purple fur coat whipping, GRAVEL charging in the background',
  ['Uno', 'GRAVEL'], 'the diamond glow brightens slowly on the fist', 'locked camera', None),
 ('d13', 'b', 40.4, 'Strike + impact: the diamond fist meets the rock fist - the rock shatters.', 'Extreme close-up side view',
  'Uno\'s diamond-white glowing fist meeting GRAVEL\'s rock fist, grey asteroid rock shattering into pieces, white impact flash',
  ['Uno', 'GRAVEL'], 'rock fragments drift outward slowly', 'locked camera, slight shake', 'KRAK-KOOM!'),
 ('d14', 'c', 43.78, 'Reaction: GRAVEL skids back, shocked; Uno calls the bluff with a point.', 'Dutch angle wide shot',
  'GRAVEL skidding backward with bare cracked chrome fists and a shocked face, Uno pointing at him, Aura folding her arms beside Uno',
  ['GRAVEL', 'Uno', 'Aura'], 'GRAVEL slides back a little, dust trails', 'locked camera', 'SKRRRT!'),
])
page('p06', 'two-up', None, 'hook - woman (47.9-54.1 s): "From the get go, they blew it / They couldn\'t hang, they knew it"',
 'The HECKLE drones spring a trap; Aura must protect Uno from the blind side.', [
 ('d15', 'a', 47.9, 'The HECKLE drones dive at Uno\'s back with megaphone sonic blasts.', 'Extreme high angle',
  'the twin HECKLE drones diving from above toward Uno\'s back, magenta sonic rings blasting from their megaphone mouths',
  ['HECKLE', 'Uno'], 'the sonic rings pulse outward', 'locked camera', 'WUB-WUB!'),
 ('s16', 'b', 51.18, 'Aura spins and swats both drones into each other with a ribbon of cyan light.', 'Splash, low spinning angle',
  'Aura mid-spin swinging a ribbon of cyan light that knocks the two HECKLE drones into each other in a burst of sparks, her crimson hair flying',
  ['Aura', 'HECKLE'], 'the light ribbon curls slowly, sparks drift', 'locked camera', 'BONK-BONK!'),
])
page('p07', 'three', None, 'verse 3 - man (54.1-64.1 s): "She helped me see the light" / "we own the night" / "Lifting me up so high"',
 'NULLSTAR kills the arena lights to blind them; only Aura\'s light can carry Uno up to the crown platform.', [
 ('d17', 'a', 54.08, 'NULLSTAR snaps his fingers - the dead star swallows every light.', 'Medium close-up',
  'NULLSTAR snapping his chrome fingers, his dead-star chest core pulling all the arena light into it, the arena going dark',
  ['NULLSTAR'], 'the light streams slowly into the chest core', 'locked camera', 'SNAP!'),
 ('d18', 'b', 57.24, 'In the dark, Aura glows cyan and lights the way.', 'Wide shot',
  'Aura glowing bright cyan in a pitch-dark arena, lighting a path of floating platforms for Uno, dead stars faintly visible',
  ['Aura', 'Uno'], 'the cyan glow breathes, platforms bob gently', 'locked camera', None),
 ('d19', 'c', 60.66, 'Aura launches Uno skyward from her cupped hands toward the crown platform.', "Worm's-eye view",
  'Aura boosting Uno upward from her cupped hands, Uno rising toward the glowing crown platform high above, cyan light trail',
  ['Aura', 'Uno'], 'Uno rises slowly, the light trail stretches', 'locked camera', 'FWOOSH!'),
])
page('p08', 'inset-three', 'tilt', 'hook - woman (64.1-80.8 s): "na na na na" / "I got you, I have you" / "From the get go, they blew it"',
 'NULLSTAR steps in himself: his dead-star gravity drags Uno out of the sky - Aura has to catch him or it\'s over.', [
 ('d20', 'a', 64.06, 'Wind-up: NULLSTAR opens his coat; the dead-star core begins to pull.', 'Extreme low angle',
  'NULLSTAR throwing open his violet-black tailcoat, his dead-star chest core glowing a dim red, gravity rings rippling outward',
  ['NULLSTAR'], 'the gravity rings ripple outward slowly', 'locked low camera', 'VWOOOM!'),
 ('d21', 'b', 67.42, 'Impact: the gravity well yanks Uno down out of the air.', 'High angle Dutch shot',
  'Uno being pulled down out of the air by red gravity rings toward NULLSTAR, coat and chain flailing, debris spiraling',
  ['Uno', 'NULLSTAR'], 'Uno drifts downward slowly, debris spirals', 'locked camera', 'KRRZZT!'),
 ('d22', 'c', 70.6, '"I got you": Aura catches Uno\'s wrist at the edge of the gravity well.', 'Extreme close-up',
  'Aura gripping Uno\'s wrist at the edge of a swirling red gravity well, her cyan light pushing back the red',
  ['Aura', 'Uno'], 'the cyan and red light push against each other', 'locked camera', None),
 ('s23', 'splash', 74.16, 'Together they pull free and turn to face NULLSTAR, back to back.', 'Splash, circling low angle',
  'Uno and Aura standing back to back in fighting stances, cyan and diamond-white glow around them, NULLSTAR looming in the dark behind with his cane raised',
  ['Uno', 'Aura', 'NULLSTAR'], 'hair, coat and light glow sway gently', 'locked camera', 'SHING!'),
])
page('p09', 'mixed-three', None, 'verse 4 - man (80.8-90.9 s): "Now the skill is breaking through" / "lock into the groove" / "flying way too high"',
 'The climactic fight: the tag combo has to break NULLSTAR\'s core before the dead star collapses the arena.', [
 ('d24', 'a', 80.84, 'Wind-up: Aura spins up a cyan light spiral; Uno charges a diamond fist inside it.', 'Low three-quarter angle',
  'Aura spinning a cyan light spiral around Uno while he charges a diamond-white glowing fist inside it, sparks swirling',
  ['Aura', 'Uno'], 'the spiral turns slowly, the glow brightens', 'locked camera', None),
 ('d25', 'b', 84.1, 'Strike: the combined punch rockets into NULLSTAR\'s chest core.', 'Extreme foreshortened angle',
  'Uno\'s diamond-and-cyan glowing fist rushing toward the viewer and NULLSTAR\'s dead-star chest core, speed lines, NULLSTAR raising his cane too late',
  ['Uno', 'NULLSTAR'], 'speed lines stream, the fist holds steady', 'locked camera', 'KA-BLAM!'),
 ('d26', 'c', 87.38, 'Impact: the core cracks with blinding white light; NULLSTAR\'s shard crown flies off.', 'Dutch angle close-up',
  'NULLSTAR\'s dead-star chest core cracking with beams of white light, his black shard crown flying off his head, his red eyes wide in shock',
  ['NULLSTAR'], 'light beams widen slowly, the crown tumbles', 'locked camera, slight shake', 'KRA-KOOOM!'),
])
page('p10', 'tilt-two', 'breakout', 'hook - woman/man (90.9-104.4 s): "They couldn\'t hang" / "Yeah they done, yeah they through / Nothing left for them to do"',
 'Reaction: the Deadstar Court falls apart - the old dead star relights and the crowd turns on the bullies.', [
 ('d27', 'a', 90.88, 'NULLSTAR, GRAVEL and the HECKLE drones are knocked into a heap wearing the clown nose hologram.', 'High angle wide shot',
  'NULLSTAR, GRAVEL and the twin HECKLE drones dazed in a pile on the arena floor, the red holographic clown nose now on NULLSTAR, cartoon stars circling their heads',
  ['NULLSTAR', 'GRAVEL', 'HECKLE'], 'cartoon stars circle slowly over their heads', 'locked camera', 'BOINK!'),
 ('d28', 'b', 97.72, 'The dead star reignites gold behind Uno and Aura; the robot crowd cheers.', 'Extreme wide low angle',
  'the dead star behind the arena reigniting in brilliant gold light, the robot crowd on its feet cheering, Uno and Aura silhouetted center',
  ['Uno', 'Aura'], 'golden light swells slowly, the crowd waves', 'locked camera', None),
 ('s29', 'splash', 100.82, 'The Crown of Light floats down toward them.', 'Splash, worm\'s-eye view',
  'the glowing gold crown of light descending from the sky between Uno and Aura, both looking up, golden stardust falling',
  ['Uno', 'Aura'], 'the crown descends slowly, stardust falls', 'locked camera', 'WHOOOM!'),
])
page('p11', 'two-up', None, 'outro - woman (104.4-116 s): "no more to do, no more to do" (+ end card)',
 'They take the crown - together; the Deadstar Arena is theirs.', [
 ('d30', 'a', 104.48, 'Aura places the Crown of Light on Uno\'s dome; he lifts her hand high.', 'Low medium shot',
  'Aura placing the glowing gold crown of light on Uno\'s round chrome dome while Uno raises her hand high in victory, golden light behind them',
  ['Aura', 'Uno'], 'the crown glows, the raised hands hold steady', 'locked camera', None),
 ('d31', 'b', 108.2, 'Final shot: the reborn golden star burns over the arena, Uno and Aura on the balcony.', 'Extreme wide shot',
  'Uno with the crown and Aura standing together on the arena balcony, the reborn golden star blazing behind them over the floating colosseum',
  ['Uno', 'Aura'], 'the golden star pulses, the coat and hair sway', 'locked camera', None),
])

def main():
    jobs, motion, md = [], [], []
    md += ['# DEADSTARS - comic music video plan', '',
           f"Song: Deadstars (Suno 2b485ca1-0de6-4575-8bb1-47cda2c9a273), rage trap, male + female duet, {TL['duration']:.1f} s, {TL['tempo']:.1f} BPM. "
           'Audio: song.m4a (from Suno\'s public mp4; the .mp3 URL is 403). Timeline: timeline.json (analyze_music.py, faster-whisper word alignment).', '',
           '**Universe:** the Deadstar Arena - a floating colosseum on the husk of a dead star where the Deadstar Court decides who gets crowned and who becomes the clown. No humans; every character is a chrome robot with red eyes and headphone ears. Kid-safe: no blood, no weapons used on anyone (light magic, rock fists, gravity, cartoon dazes).', '',
           '**Arc:** the doubters (the Deadstar Court) try to bring Uno down and make him the clown -> Aura holds him down through it all -> they flip the script -> climactic fight vs NULLSTAR -> they take the crown.', '',
           '**Intro:** title logo DEADSTARS slams in on the first downbeat (0.19 s). **Ending:** end card BROUGHT TO YOU BY PROGRESSIVE SLOP / LIKE AND SUBSCRIBE FOR MORE!', '',
           '**Cast:**', *[f'- {v}' for v in CAST.values()], '',
           f'**Refs:** Uno/Aura panels -> `{REF_CREW}`; any Deadstar Court panel -> `{REF_VILLAIN}` (generate it first from villain_brief.md); panels with both use both.', '']
    n = 0
    for pg in P:
        md += [f"## {pg['id']} - {pg['section']}", f"layout `{pg['layout']}`" + (f" + splash `{pg['splash']}`" if pg['splash'] else ''), '',
               f"**Stakes:** {pg['stakes']}", '']
        for (pid, slot, t, beat, shot, scene, chars, action, cam, sfx) in pg['panels']:
            n += 1
            t = snap(t)
            refs = ([REF_CREW] if {'Uno', 'Aura'} & set(chars) else []) + ([REF_VILLAIN] if {'NULLSTAR', 'GRAVEL', 'HECKLE'} & set(chars) else [])
            prompt = STYLE.format(shot=shot, scene=scene, chars='; '.join(CAST[c] for c in chars) if chars else 'No characters')
            mot = anchor(chars) + ' ' + MOTION.format(action=action[0].upper() + action[1:], cam=cam[0].upper() + cam[1:])
            md.append(f"- **{pid}** ({slot}, {t:.2f}s, lyric: \"{lyric_at(t)}\") {beat}" + (f" SFX **{sfx}**" if sfx else ''))
            jobs.append({'id': pid, 'page': pg['id'], 'slot': slot, 'time': t, 'aspect': '16:9', 'beat': beat, 'sfx': sfx,
                         'characters': chars, 'prompt': prompt, 'reference_image_paths': refs,
                         'out': os.path.join(ASSETS, 'panels', f'{pid}.jpg')})
            motion.append(f'{pid} | {mot}')
        md.append('')
    md.insert(4, f'**{n} panels over {len(P)} pages.**')
    open(os.path.join(HERE, 'plan.md'), 'w').write('\n'.join(md) + '\n')
    json.dump(jobs, open(os.path.join(HERE, 'generate_jobs.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'motion.txt'), 'w').write('\n'.join(motion) + '\n')
    print(n, 'panels', len(P), 'pages')

if __name__ == '__main__':
    main()

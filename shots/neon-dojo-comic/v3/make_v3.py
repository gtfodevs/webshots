#!/usr/bin/env python3
"""Neon Dojo v3 story plan (beat sheet) -> plan.md, prompts.json, motion.txt in this folder. No images generated."""
import json, bisect, os
HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../neon-dojo-fighter/stage/timeline.json')))
B = TL['beats']
LYR = {round(l['t'], 2): l['text'] for l in TL['lyrics']}
def snap(t): return round(min(B, key=lambda b: abs(b - t)), 3)
ASSETS = '/home/box/agent-data/agents/7ab6020d-de13-47d8-8ee8-1d6ca8bc0c89/assets/'
V1 = '/workspace/neon-dojo-comic/panels/'

CAST = {
 'Uno': 'Uno (chrome robot, round smooth chrome head, red eyes, headphone ears, purple fur coat, gold "1" chain)',
 'Aura': 'Aura (robot, grey face, red eyes, headphone ears, dark crimson hair, modest crimson bodysuit, cyan magic)',
 'Sensei': 'Sensei (elderly chrome robot, grey robe, white cable beard, cane)',
 'KAZE-9': 'KAZE-9 (lean ninja robot, red scarf, twin blades)',
 'RAIJIN': 'RAIJIN (bulky boxer robot, lightning gauntlets)',
 'TEKKO': 'TEKKO (squat sumo robot, piston arms)',
 'LOTUS': 'LOTUS (long-legged crane-kick robot)',
 'SHOGUN': 'SHOGUN (red samurai robot, horned helmet, glowing red katana)',
}
STYLE = ("{shot}: {scene}. {chars}. All robots chrome with red eyes and headphone ears, no humans, kid-friendly. "
         "1990s superhero comic panel, bold ink, heavy blacks, halftone, speed lines, impact flash, neon magenta and cyan, 16:9, no text.")
MOTION = "{action}. {cam}. Keep every robot's shape, face and limb count; no morphing, no new characters, nobody walks toward the camera."

# (page, layout, splashStyle, act, section, need) ; panels: (id, slot, lyric_time, beat, shot, scene, chars, action, cam, sfx, reuse)
P = []
def page(pid, layout, splash, act, section, need, panels): P.append(dict(id=pid, layout=layout, splash=splash, act=act, section=section, need=need, panels=panels))

page('p01', 'slant-two', None, 1, 'intro', 'The old dojo is fading; the Neo-Kyoto tournament is the only way to save it.', [
 ('v01', 'a', 0.19, 'Neo-Kyoto at night, the tournament blimp glides over the city - the stakes are announced.', 'Extreme wide establishing shot',
  'rainy neon city, pagoda towers, tournament blimp with a glowing fist emblem', [], 'the blimp glides slowly left, rain falls', 'locked camera', None, V1 + 'n01.jpg'),
 ('v02', 'b', 4.08, 'Sensei, alone in his leaking dojo, holds up an empty belt hook: win it back or lose the dojo.', "Worm's-eye view",
  'the old robot sensei standing in a leaking wooden dojo at night, pointing his cane at an empty golden belt hook on the wall, rain dripping through the roof, lantern glow', ['Sensei'],
  'Sensei slowly raises his cane toward the empty hook, rain drips', 'locked low camera', None, None),
])
page('p02', 'two-up', 'tilt', 1, 'verse 1', 'Uno and Aura want to be champions but refuse to fight as a pair.', [
 ('v03', 'a', 13.909, 'First drill: Uno and Aura bump shoulders and bicker mid-kata - two stars, no team.', 'Dutch angle medium shot',
  'Uno and Aura bumping shoulders mid-kata in the dojo, glaring at each other, sparks between their heads, Sensei facepalming behind', ['Uno', 'Aura', 'Sensei'],
  'Uno and Aura turn their heads and glare at each other, a spark pops', 'slow push-in', 'BONK!', None),
 ('v04', 'b', 20.759, "Their attacks collide: Uno's punch meets Aura's cyan blast and blows them both across the mat.", 'Extreme low side angle',
  "Uno's punch and Aura's cyan magic blast colliding in a huge impact flash between them, both robots blown backward off their feet, dojo mats flying", ['Uno', 'Aura'],
  'the impact flash bursts and both robots fly backward', 'locked camera, slight shake', 'KA-POW!', None),
 ('s05', 'splash', 24.828, 'The botched tag: their hand-off misses and they crash into a puddle while Sensei watches.', 'Splash, existing art',
  'botched training tag in the rain, Uno and Aura tangled and crashing, Sensei watching', ['Uno', 'Aura', 'Sensei'],
  'Uno and Aura stumble and splash down into the puddle', 'locked camera', 'SPLOOSH!', ASSETS + '1a70147613238d45a1d50100c327a4beaf976b8a58dab1b1971802446bbc5cbb.jpg'),
])
page('p03', 'tilt-two', None, 1, 'verse 1', 'They must learn to move as one or wash out before the tournament.', [
 ('v06', 'a', 27.609, 'Sensei ties their wrists together with a glowing cable: fight as one.', 'High angle overhead shot',
  "Sensei looping a glowing cable around Uno's and Aura's wrists, both robots sulking, rain-soaked dojo floor reflecting lanterns", ['Uno', 'Aura', 'Sensei'],
  'Sensei pulls the glowing cable tight around their wrists', 'locked overhead camera', None, None),
 ('v07', 'b', 34.3, '"One-two in a clean sweep": still tied, they land a perfectly synced double sweep kick.', 'Extreme low wide shot',
  'Uno and Aura, wrists still tied, spinning in sync and sweeping a training dummy off its base, circular speed lines, water spray', ['Uno', 'Aura'],
  'both robots spin once in sync and the dummy topples', 'locked camera', 'SWOOSH!', None),
])
page('p04', 'inset-two', 'full', 1, 'verse 1', 'The tag finally clicks - they are a team.', [
 ('v08', 'a', 42.48, 'A heavy training mech swings at Aura; she blocks and reaches back for Uno.', 'Over-the-shoulder Dutch angle',
  "Aura blocking a giant training mech's swinging arm with a cyan shield, reaching her free hand back toward Uno, sparks", ['Aura', 'Uno'],
  "Aura's cyan shield flares as the mech arm hits it", 'locked camera', 'KLANG!', None),
 ('v09', 'b', 46.4, '"Short swing, like a clock hand": the tag slap lands - clean.', 'Extreme close-up',
  "Uno's chrome hand slapping Aura's gloved hand in a tag, a starburst of cyan and purple sparks, speed lines", ['Uno', 'Aura'],
  'the two hands meet and a bright spark bursts', 'locked macro camera', 'TAG!', None),
 ('s10', 'splash', 54.27, 'Tag-in finisher: Uno flies over Aura and smashes the mech; Sensei finally smiles.', 'Splash, worm\'s-eye view',
  "Uno vaulting over Aura's shoulders, fist-first into the training mech which bursts into harmless bolts and confetti sparks, Sensei smiling in the background", ['Uno', 'Aura', 'Sensei'],
  "Uno's fist connects and the mech bursts into sparks", 'locked camera', 'KRA-KOOM!', None),
])
page('p05', 'slant-two', None, 2, 'pre-chorus', 'The tournament: four rivals stand between them and the belt.', [
 ('v12', 'a', 61.04, '"Say my name": the arena roars as the rivals are introduced under spotlights.', "Worm's-eye wide shot",
  'tournament arena floor under crossing spotlights, rivals posing in a line: KAZE-9, RAIJIN, TEKKO and LOTUS, huge cheering robot crowd', ['KAZE-9', 'RAIJIN', 'TEKKO', 'LOTUS'],
  'the spotlights sweep across the four rivals', 'slow tilt up', None, None),
 ('v13', 'b', 64.5, "KAZE-9 picks his rival: he points a blade at Aura. It's personal.", 'Extreme close-up, Dutch angle',
  "KAZE-9's masked face and red scarf whipping in the wind, one blade pointed at the viewer, Aura's reflection in the steel", ['KAZE-9', 'Aura'],
  'the red scarf whips and the blade glints', 'locked camera', 'SHING!', None),
])
page('p06', 'diagonal-three', 'breakout', 2, 'chorus', 'Round one: they must win every bout to stay in.', [
 ('v14', 'a', 68.685, 'Wind-up: RAIJIN cocks a crackling lightning hook at Uno.', 'Low Dutch angle',
  'RAIJIN winding up a giant crackling lightning gauntlet, Uno raising his guard, ring ropes and flashbulbs', ['RAIJIN', 'Uno'],
  'RAIJIN pulls his fist back and lightning crackles', 'locked camera', 'BZZZT!', None),
 ('v15', 'b', 71.94, '"Knuckle talk": strike and impact - Uno ducks and lands the uppercut.', 'Existing art',
  'Uno uppercutting RAIJIN, lightning burst', ['Uno', 'RAIJIN'],
  "Uno's uppercut snaps up and RAIJIN's head rocks back", 'locked camera', 'POW!', ASSETS + '525a9cb723f54bafe8f25c99d2bf1a8d2ea498ceb87ac9abbb898e73d14508a8.jpg'),
 ('v16', 'c', 73.66, '"Hands up, then it all falls": Aura tags in and pushes TEKKO out of the ring.', 'Wide side angle',
  "Aura's cyan wave pushing TEKKO off the edge of the ring, TEKKO tumbling harmlessly onto a pile of cushions, crowd jumping", ['Aura', 'TEKKO'],
  'TEKKO tips backward off the ring edge', 'locked camera', 'WHUMP!', None),
 ('s17', 'splash', 77.0, 'Reaction: LOTUS strikes from above; Aura blocks the crane kick mid-air.', "Splash, worm's-eye view",
  "LOTUS diving down with a crane kick against Aura's crossed cyan-glowing forearms, giant impact ring, cherry petals and spotlights", ['LOTUS', 'Aura'],
  "LOTUS's kick lands on Aura's guard and the impact ring flashes", 'locked camera', 'WHAM!', None),
])
page('p07', 'inset-three', 'tilt', 2, 'verse 2', 'The dark moment: the team is broken - can Uno carry them alone?', [
 ('v18', 'a', 82.1, 'The rivalry match: Aura vs KAZE-9, blade against cyan shield.', 'Extreme close-up, Dutch angle',
  "KAZE-9's twin blades grinding against Aura's cyan shield, sparks spraying, their red eyes locked", ['Aura', 'KAZE-9'],
  'sparks spray as the blades grind on the shield', 'locked camera', 'SKRRRK!', None),
 ('v19', 'b', 88.5, '"Duck low, then I cut through": KAZE-9 feints and drops Aura to the mat.', 'High angle top-down',
  'Aura falling flat onto the arena mat with an impact flash, KAZE-9 landing behind her in a crouch, red scarf trailing', ['Aura', 'KAZE-9'],
  'Aura hits the mat and the impact flash pops', 'locked overhead camera', 'THOOM!', None),
 ('v20', 'c', 95.38, "Uno kneels over Aura; her cyan glow flickers out. The crowd goes quiet.", 'Low angle close shot, dim light',
  "Uno kneeling over fallen Aura, one hand on her shoulder, her cyan magic flickering weakly, single spotlight, silent crowd in shadow", ['Uno', 'Aura'],
  "Aura's cyan glow flickers once", 'very slow push-in', None, None),
 ('s21', 'splash', 102.911, '"If the room start to get loud... I make room with a clean step": Uno carries Aura out of the ring; KAZE-9 lowers his blades in respect.', 'Splash, wide side-on shot',
  'Uno carrying Aura on his back across the arena, side-on, crowd parting, KAZE-9 in the background lowering his blades and bowing', ['Uno', 'Aura', 'KAZE-9'],
  'Uno steps slowly left to right across the frame carrying Aura', 'locked side camera', None, None),
])
page('p08', 'two-up', 'full', 3, 'pre-chorus', 'SHOGUN holds the belt; they have one last chance to win it back.', [
 ('v22', 'a', 108.042, '"Count it out, one by one": SHOGUN rises from the arena throne and ignites his red katana.', "Extreme worm's-eye view",
  'SHOGUN rising from a throne of server racks, red katana igniting, glowing red smoke rolling down the steps', ['SHOGUN'],
  'SHOGUN draws the katana and it ignites red', 'slow tilt up', 'VMMMM!', None),
 ('v23', 'b', 115.18, '"Say my name": the prize - SHOGUN grips the golden belt.', 'Extreme close-up, existing v1 art',
  "SHOGUN's armored hands holding the golden dojo belt", ['SHOGUN'],
  'the armored hands tighten on the belt, red glint', 'locked camera', None, V1 + 'n18.jpg'),
 ('s24', 'splash', 118.306, '"When it pops": Uno, alone, meets SHOGUN in a blade lock.', 'Splash, existing art',
  "Uno's forearm guard locked against SHOGUN's red katana, sparks", ['Uno', 'SHOGUN'],
  'sparks spray from the blade lock as they push', 'locked camera', 'KZZZANG!', ASSETS + '0284aa8eafe96aebecf0ee0edb9b36d3ed5995fce00285ed6693716e23056eac.jpg'),
])
page('p09', 'tilt-two', None, 3, 'chorus', 'Aura is back - together they turn the fight.', [
 ('v25', 'a', 124.92, '"Keep it close": Aura, recovered and blazing cyan, dives in and slaps the tag.', 'Dutch angle mid-air shot',
  "Aura diving in over the arena, cyan aura blazing, slapping Uno's outstretched hand mid-air, starburst of sparks", ['Aura', 'Uno'],
  'their hands slap and the starburst flares', 'locked camera', 'TAG!', None),
 ('v26', 'b', 128.34, '"Hands up, then it all falls": tag combo - Uno launches SHOGUN, Aura blasts him in the air.', "Worm's-eye wide shot",
  "Uno's rising kick launching SHOGUN into the air while Aura's cyan beam hits him from the side, double impact flash, speed lines", ['Uno', 'Aura', 'SHOGUN'],
  'SHOGUN is knocked upward by the kick', 'locked camera', 'KA-BLAM!', None),
])
page('p10', 'slant-two', 'breakout', 3, 'bridge', 'SHOGUN stands back up - they need both supers at once.', [
 ('v28', 'a', 137.091, '"They talking tough... I just grin": SUPER cut-in - Uno\'s eyes flare.', 'Extreme close-up cut-in, existing v1 art',
  "Uno's face, red eyes flaring, purple speed lines", ['Uno'],
  "Uno's red eyes flare brighter", 'locked camera', None, V1 + 'n09.jpg'),
 ('v29', 'b', 144.2, '"One sharp move": SUPER cut-in - Aura charges a cyan orb.', 'Close-up cut-in, existing v1 art',
  'Aura charging a bright cyan orb between her hands', ['Aura'],
  'the cyan orb swells and crackles', 'locked camera', None, V1 + 'n23.jpg'),
 ('s30', 'splash', 149.049, 'Double finisher: punch plus orb - SHOGUN\'s armour bursts into harmless sparkles.', 'Splash, centred low angle',
  "Uno's glowing punch and Aura's cyan orb hitting SHOGUN together, his red armour bursting apart into harmless sparkles and stars, a small plain robot left dizzy inside", ['Uno', 'Aura', 'SHOGUN'],
  'the armour bursts outward into sparkles', 'locked camera', 'KA-BOOOOM!', None),
])
page('p11', 'inset-two', None, 3, 'final chorus', 'Resolution: the dojo is saved and the team is real.', [
 ('v31', 'a', 157.44, 'Uno and Aura hand the golden belt to Sensei; un-armoured SHOGUN and the rivals bow.', 'High angle wide shot in the repaired dojo',
  'Uno and Aura presenting the golden belt to the smiling Sensei in the repaired sunny dojo, small un-armoured SHOGUN, KAZE-9 and RAIJIN bowing', ['Uno', 'Aura', 'Sensei', 'KAZE-9', 'RAIJIN'],
  'Sensei lifts the belt and the rivals bow', 'locked camera', None, None),
 ('v32', 'b', 160.984, '"I don\'t argue, I just walk": Uno and Aura, from behind, facing the sunrise.', 'Wide shot from behind, existing v1 art',
  'Uno and Aura from behind facing a pink sunrise over Neo-Kyoto', ['Uno', 'Aura'],
  'the sun rises slowly, their coat and hair stir in the wind', 'locked camera', None, V1 + 'n26.jpg'),
])

def main():
    prompts, motion, md = [], [], []
    md.append('# Neon Dojo - v3 story plan (beat sheet)\n')
    md.append('Song: 166.8 s, 143.6 BPM. Times are song seconds snapped to the beat, landing on the lyric line quoted in each beat. '
              'Each fight runs wind-up -> strike -> impact -> reaction. Clips start one beat (~0.42 s) after the panel lands. '
              'Existing art is marked REUSE.\n')
    lay = None; n = 0
    for pg in P:
        assert pg['layout'] != lay, pg['id']; lay = pg['layout']
        md.append(f"\n## {pg['id']} - Act {pg['act']} - {pg['section']} - layout `{pg['layout']}`" + (f" + `{pg['splash']}` splash" if pg['splash'] else '') + '\n')
        md.append(f"**Need:** {pg['need']}\n")
        md.append('| id | slot | time | lyric | beat | SFX | art |\n|---|---|---|---|---|---|---|')
        for (pid, slot, t, beat, shot, scene, chars, action, cam, sfx, reuse) in pg['panels']:
            n += 1
            ts = snap(t)
            inside = [l for l in TL['lyrics'] if l['t'] - 1.0 <= t < l['end']]
            lyr_s = min(inside, key=lambda l: abs(l['t'] - t))['text'] if inside else '(instrumental)'
            refs = [c for c in chars if c in ('Uno', 'Aura', 'SHOGUN', 'KAZE-9', 'RAIJIN')] or ['none']
            if reuse:
                prompt = None
            else:
                prompt = STYLE.format(shot=shot, scene=scene, chars='; '.join(CAST[c] for c in chars) or 'no characters')
            mot = MOTION.format(action=action[0].upper() + action[1:], cam=cam[0].upper() + cam[1:])
            prompts.append({'id': pid, 'page': pg['id'], 'slot': slot, 'time': ts, 'lyric': lyr_s, 'beat': beat,
                            'refs': refs, 'sfx': sfx, 'reuse': reuse, 'prompt': prompt, 'motion': mot})
            motion.append(f'{pid} | {mot}')
            md.append(f"| {pid} | {slot} | {ts:.2f} | {lyr_s} | {beat} | {sfx or ''} | {'REUSE `' + os.path.basename(reuse) + '`' if reuse else 'new'} |")
    md.append('\n## Prompts\nFull image prompts (new panels) and motion prompts are in `prompts.json` and `motion.txt`.\n')
    md.append('\n## Reused art\n' + '\n'.join(f"- {p['id']}: `{p['reuse']}`" for p in prompts if p['reuse']) + '\n')
    for name, data in (('plan.md', '\n'.join(md) + '\n'), ('prompts.json', json.dumps(prompts, indent=1)), ('motion.txt', '\n'.join(motion) + '\n')):
        path = os.path.join(HERE, name)
        if os.path.exists(path) and open(path).read() != data:
            stem, ext = os.path.splitext(path); k = 2
            while os.path.exists(f'{stem}-v{k}{ext}'): k += 1
            path = f'{stem}-v{k}{ext}'
        open(path, 'w').write(data)
    print(n, 'panels;', sum(1 for p in prompts if p['reuse']), 'reused; max prompt words',
          max(len(p['prompt'].split()) for p in prompts if p['prompt']))
if __name__ == "__main__":
    main()

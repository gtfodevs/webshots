#!/usr/bin/env python3
"""FRIGHT NIGHT: panel prompts (generate_jobs.json), motion.txt, contact.jpg. No images are generated here."""
import json, os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
REF = '/home/box/agent-data/agents/7ab6020d-de13-47d8-8ee8-1d6ca8bc0c89/assets/c542333dd5429d16c251957261c84b0f945e0a93051079b666fc07878bbfe94d.jpg'
STYLE_REF = os.path.join(HERE, 'panels', 'f02.jpg')
C = {
 'Uno': 'Uno (tall robot, round smooth chrome dome head, glowing red eyes, headphone ears, long purple fur coat, gold "1" chain)',
 'Aura': 'Aura (clearly a robot, same height as Uno: grey chrome face, glowing red eyes, headphone ears, chrome arms and legs with visible joints, flowing dark crimson hair, modest long-sleeved crimson pantsuit, cyan magic)',
 'Leaners': 'the Leaners (tall thin shadow robots, matte black bodies, hollow faces with glowing red eyes)',
 'wolves': 'chrome robot wolves (sleek chrome bodies, glowing red eyes)',
 'ghost': 'the mirror-ghost (a pale, cold-green glowing translucent robot copy of Aura: same crimson-hair silhouette and pantsuit but all ghostly green)',
 'cat': 'a small chrome robot black cat with glowing red eyes',
}
STYLE = ('{shot}: {scene}. {chars}. Haunted mansion at 3 AM, kid-safe eerie Halloween mood, no humans, no gore, no blood. '
         'Characters are the same height. Hands apart and clearly drawn, no clasped hands. '
         '1990s superhero comic panel, bold ink, heavy blacks, halftone, deep teal and black, sickly green glow, candle orange highlights, '
         'rain, fog, lightning, 16:9, no text, no letters, no logos.')
ANCHOR_HEAD = 'Handsome, sleek, well-designed chrome robots.'
ANCHOR = {
 'Uno': 'Uno: tall robot, round smooth chrome dome head, red eyes, headphone ears, purple fur coat, gold 1 chain.',
 'Aura': 'Aura: clearly a robot, same height as Uno, grey chrome face, red eyes, headphone ears, chrome jointed limbs, dark crimson hair, modest crimson pantsuit.',
 'Leaners': 'The Leaners: tall thin matte-black shadow robots with red eyes.',
 'wolves': 'Chrome robot wolves with red eyes.',
 'ghost': 'The mirror-ghost: pale cold-green translucent robot copy of Aura.',
 'cat': 'A small chrome robot black cat with red eyes.',
}
ANCHOR_TAIL = ('Each character keeps the exact same face, body, outfit and size for the entire shot; one continuous shot; '
               'the opening frame matches the image exactly; nothing melts, morphs, transforms, appears or vanishes. Only these characters in shot.')
NOPEOPLE = 'one continuous shot, no people.'
# id, splash?, lyric, shot, scene, chars, motion (env-only shots: chars == [] -> no-names prompt)
P = [
 ('f01', False, 'Fright night, fright night', 'existing', '', [], 'Lightning flickers behind the mansion on the hill, rain falls, fog drifts across the dead trees, slow push-in toward the glowing windows. Locked camera, ' + NOPEOPLE),
 ('f02', False, "It ain't my kind of night", 'existing', '', ['Uno', 'Aura'], 'The heavy door swings shut behind them with one hard slam, dust puffs up, the lantern flame flickers. Slow push-in.'),
 ('f03', False, 'Deadbolt shaking', 'Extreme close-up', 'a heavy brass deadbolt on an old wooden door rattling, fresh claw scratch marks raking across the green-wallpapered hall wall beside it, candle light flickering', [],
  'The brass deadbolt rattles, dust shakes loose, candle light flickers over the scratch marks. Locked camera, ' + NOPEOPLE),
 ('f04', False, 'Mud on the carpet', 'Low angle', 'Uno kneeling on a long red hallway carpet, examining muddy clawed footprints that lead straight into the wall, his red eyes flaring, Aura standing behind him holding a candle lantern', ['Uno', 'Aura'],
  'Uno leans closer to the footprints and his red eyes flare brighter, the lantern flame flickers. Slow push-in.'),
 ('f05', False, "I don't like what I just saw", 'Tight close-up', 'Aura holding up a shaking candle lantern, her red robot eyes wide with fear, crimson hair framing her grey chrome face, darkness behind her', ['Aura'],
  'The lantern trembles slightly and the flame flickers across her chrome face, her hair stirs in a cold draft. Slow push-in.'),
 ('f06', False, 'Figures in the hallway, and they\'re leaning in', 'existing', '', ['Uno', 'Aura', 'Leaners'], 'The Leaners lean slowly out of the doorways toward the pair, candles flicker, fog drifts along the floor. Slow push-in.'),
 ('f07', False, '(strike)', 'Low dynamic angle', 'Uno stepping in front of Aura with one arm thrown out to shield her, Aura raising her other hand with a burst of cyan magic, tall thin shadow robots recoiling backward into doorways', ['Uno', 'Aura', 'Leaners'],
  'One strike: the cyan magic burst flares and the Leaners recoil back into the doorways, then hold. Locked camera.'),
 ('f08', False, "I'm looking for the door", 'Extreme Dutch angle wide shot', 'Uno and Aura standing small in a dizzying maze of identical tall wooden doors stretching in every direction, sickly green glow, fog on the floor', ['Uno', 'Aura'],
  'Fog drifts between the doors, the green light pulses slowly, the pair glance around. Slow push-in.'),
 ('f09', False, 'Black cat screaming, clock stuck on three', 'Medium shot', 'a chrome robot black cat hissing with its back arched on top of a tall grandfather clock whose hands are frozen at three o\'clock, lightning flashing through a window', ['cat'],
  'The cat hisses once, lightning flickers through the window, the frozen clock pendulum hangs still. Locked camera.'),
 ('f10', False, 'Every little shadow got a name for me', 'Wide shot', 'long jagged shadows on the wall stretching into the giant silhouettes of Uno and Aura, the real Uno and Aura small in the foreground looking up at them, candle light from below', ['Uno', 'Aura'],
  'The giant shadows sway as the candle flickers, the pair stay still and look up. Slow push-in.'),
 ('f11', False, 'This whole house feels wrong', 'Extreme high angle', 'an impossible twisting staircase that loops upside down like an Escher drawing, Uno and Aura climbing it with Aura upside down above Uno, fog and teal light', ['Uno', 'Aura'],
  'Fog drifts through the staircase, the pair climb one slow step, candle light flickers. Locked camera.'),
 ('f12', True, 'Wolves on the roof', 'Splash, low angle', 'chrome robot wolves silhouetted on the mansion roof ridge howling against a huge sickly green full moon, storm clouds, lightning', ['wolves'],
  'The wolves lift their heads in a slow howl, storm clouds roll past the moon, lightning flickers. Locked camera.'),
 ('f13', False, "and the graveyard's gone", 'Over-the-shoulder shot', 'Uno and Aura at a tall rain-streaked window looking out at a graveyard sinking into thick green fog until only the tips of the tombstones remain', ['Uno', 'Aura'],
  'The fog slowly swallows the tombstones outside, rain streaks down the glass. Slow push-in.'),
 ('f14', False, 'Storm at the window', 'Extreme low angle, mid-strike', 'a chrome robot wolf crashing in through a shattering window and Uno catching it mid-leap with a rising uppercut, glass shards and rain spraying, lightning behind', ['Uno', 'wolves'],
  'One strike: Uno\'s uppercut connects and the wolf is knocked upward, glass shards hang and drift. Locked camera, slight shake.'),
 ('f15', False, 'doom keeps coming on', 'Wide action shot, mid-strike', 'Aura thrusting both palms forward firing a huge cyan magic blast that throws two chrome robot wolves backward through the air, wind whipping her crimson hair', ['Aura', 'wolves'],
  'One strike: the cyan blast fires and the two wolves fly back, sparks drift. Locked camera.'),
 ('f16', False, 'I need out tonight', 'Low tracking angle', 'Uno and Aura sprinting side by side down a long corridor toward the camera, a row of candles behind them going out one by one into darkness', ['Uno', 'Aura'],
  'The candles behind them go out one by one, coats and hair stream back. Locked camera.'),
 ('f17', False, 'Ghost in the mirror, and it just moved twice', 'Medium shot', 'Aura standing still in front of a tall ornate mirror while her reflection, the pale cold-green mirror-ghost, turns its head and raises a hand on its own', ['Aura', 'ghost'],
  'Aura stays still while the green reflection slowly tilts its head, candle light flickers. Slow push-in.'),
 ('f18', True, '(strike) SMASH', 'Splash, mid-strike', 'the cold-green mirror-ghost reaching out of the mirror glass and Aura smashing the mirror with a cyan-glowing fist, the glass bursting into glittering shards', ['Aura', 'ghost'],
  'One strike: Aura\'s fist hits and the mirror bursts, shards drift outward slowly, the ghost fades back into the frame. Locked camera, slight shake.'),
 ('f19', False, 'No sleep till dawn', 'Low angle', 'Uno looking up as the ceiling bulges downward and plaster dust falls, Aura beside him lifting the lantern, cracks spreading overhead', ['Uno', 'Aura'],
  'Dust trickles down from the bulging ceiling, the lantern flickers. Slow push-in.'),
 ('f20', False, "I hear 'em at the ceiling", 'Worm\'s-eye view', 'dozens of glowing red eyes peering down through cracks in a dark wooden ceiling, dust drifting in thin beams of green light', [],
  'Red eyes blink slowly in the cracks overhead, dust drifts through the light beams. Locked camera, ' + NOPEOPLE),
 ('f21', False, 'When the doors start buckling and the candles die', 'Wide shot', 'the grand front door at the end of the hall in sight, all the side doors bowing outward, the last candle snuffing out, only the red eyes of Uno and Aura glowing in the dark', ['Uno', 'Aura'],
  'The last candle flame gutters out and the doors bow slowly, their red eyes glow steady. Locked camera.'),
 ('f22', True, "I'm rapping through the panic", 'Splash, mid-strike', 'Uno and Aura blasting the front double doors open together, Uno punching and Aura firing cyan magic, the doors bursting outward into pale dawn light, splinters and fog flying', ['Uno', 'Aura'],
  'One strike: the doors burst open with the blast and dawn light floods in, splinters drift. Locked camera, slight shake.'),
 ('f23', False, 'till the sky goes shy (final chorus)', 'Wide shot', 'sunrise over the misty hill, Uno and Aura sitting on the grass laughing in relief, the mansion small behind them, warm orange morning light', ['Uno', 'Aura'],
  'Sunlight slowly brightens, mist drifts, the pair laugh and shake with relief. Slow push-in.'),
 ('f24', False, 'Fright night (final chorus)', 'Telephoto shot', 'the mansion in morning mist, one upstairs window where the cold-green mirror-ghost copy of Aura waves goodbye', ['ghost'],
  'Slow push toward the window, the green ghost waves slowly, mist drifts. Locked camera.'),
 ('f25', True, '(cliffhanger) TO BE CONTINUED', 'Extreme close-up', 'Aura\'s face turned toward the viewer, her eyes flickering from red to cold ghostly green, a slight knowing smile on her grey chrome face, crimson hair at the frame edges, headphone ears visible', ['Aura'],
  'Her eyes slowly shift from red to cold green and a slight smile forms, nothing else moves. Very slow push-in.'),
]
def anchor(chars):
    return ' '.join([ANCHOR_HEAD] + [ANCHOR[c] for c in ANCHOR if c in chars] + [ANCHOR_TAIL])
def main():
    jobs, mot = [], []
    for pid, splash, lyr, shot, scene, chars, motion in P:
        mot.append(f'{pid} | ' + ((anchor(chars) + ' ' + motion) if chars else motion[0].upper() + motion[1:]))
        if shot == 'existing':
            continue
        jobs.append({'id': pid, 'splash': splash, 'lyric': lyr, 'aspect': '16:9', 'characters': chars,
                     'prompt': STYLE.format(shot=shot, scene=scene, chars='; '.join(C[c] for c in chars) if chars else 'No characters'),
                     'reference_image_paths': [REF, STYLE_REF], 'out': os.path.join(HERE, 'panels', f'{pid}.jpg')})
    json.dump(jobs, open(os.path.join(HERE, 'generate_jobs.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'motion.txt'), 'w').write('\n'.join(mot) + '\n')
    # contact sheet: existing panels + labelled placeholders for the pending ones
    W, H = 384, 216
    sheet = Image.new('RGB', (5 * (W + 8) + 8, 5 * (H + 30) + 8), (24, 24, 28)); d = ImageDraw.Draw(sheet)
    for i, (pid, splash, *_ ) in enumerate(P):
        x, y = 8 + (i % 5) * (W + 8), 8 + (i // 5) * (H + 30)
        p = os.path.join(HERE, 'panels', f'{pid}.jpg')
        if os.path.exists(p):
            sheet.paste(Image.open(p).convert('RGB').resize((W, H)), (x, y))
        else:
            d.rectangle([x, y, x + W, y + H], fill=(45, 45, 52)); d.text((x + W // 2 - 40, y + H // 2), 'NOT GENERATED', fill=(200, 80, 80))
        d.text((x + 2, y + H + 6), pid + ('  SPLASH' if splash else ''), fill=(255, 220, 0))
    sheet.save(os.path.join(HERE, 'contact.jpg'), quality=90)
    print(len(jobs), 'jobs,', len(mot), 'motion lines')
if __name__ == '__main__':
    main()

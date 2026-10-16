#!/usr/bin/env python3
"""Deterministic shot list builder: shots are authored on BAR indices, times come from audio/analysis.json
(every boundary = a detected downbeat, or a drop where one lands). Writes shotlist.json + shotlist.md."""
import json, os
R = '/workspace/pharaoh'
A = json.load(open(f'{R}/audio/analysis.json')); LT = json.load(open(f'{R}/audio/lyric_timing.json'))
BARS = [b['t'] for b in A['bars']]; DROPS = [d['t'] for d in A['drops']]; DUR = A['duration']
SN, KI = A['snares'], A['kicks']

CLOTH = ("Every robot is fully clothed at all times: long sleeves to the wrists, shirts tucked in, jackets and coats on; "
         "no bare metal arms or torso ever visible. Archaeologist expedition wear only (no suits, no vintage gangster wear).")
EYES = "Faces stay cool polished SILVER chrome with no red or copper tint; only the eyes glow, intensely GLOWING RED with a bright luminous emissive red glow."
LOCK = "Locked static tripod camera: no zoom, no push-in, no pan, no tilt, no camera movement at all; the frame never changes."
WAIST = " Framed from the waist up: legs never in frame."
PHONES = "slim built-in flush headphone ear discs set into the sides of the chrome head (never big over-ear cans)"
UNO = ("Uno: chrome robot archaeologist with an A-list leading-man V-taper build, very broad shoulders and a narrow waist; "
       "entire head bright mirror-silver chrome with no skin, sculpted like a handsome young Black American man in his 20s, "
       "full lips, broad nose, rounded cheeks; a big confident swagger smirk-smile that shows a SHINY GOLD GRILL front and "
       "center; intensely GLOWING RED eyes (bright luminous emissive red glow); tan fedora over " + PHONES + "; khaki long-sleeve archaeologist field shirt "
       "tucked into a leather belt, khaki cargo pants; long PURPLE FUR COAT with full sleeves worn open; thick gold chain with "
       "a large gold \"1\" pendant; leather satchel across the body; chrome hands relaxed and open (never fists). His face is a "
       "handsome chrome face, never a skull and never a Joker grin")
AURA = ("Aura: chrome robot archaeologist, a glamorous movie-star bombshell with an hourglass figure and a cinched waist; "
        "entire head mirror-silver chrome with no skin, modeled on a beautiful young Black woman in her 20s, confident "
        "swagger smile, intensely GLOWING RED eyes (bright luminous emissive red glow); long black hair with glowing RED streaks; tan fedora with a burgundy "
        "band over " + PHONES + "; fitted khaki safari jacket buttoned up to the collar, long sleeves to the wrists, belted at "
        "the waist, burgundy scarf at the neck; fully covered")
PHAR = ("the Pharaoh: skeletal, bony, rotting crypt-horror mummy king, emaciated frame, sunken skull face with long fangs, "
        "glowing GREEN eyes, tattered grey-brown bandages hanging in shreds, cracked gold-and-lapis nemes headdress with a "
        "gold crown cobra, long clawed bony fingers; nothing like Uno (no chrome, no fur coat, no grill)")
MUM = ("two background mummies: skinny bony figures wrapped in tattered dusty grey bandages, glowing GREEN eyes, "
       "no faces visible beyond the eye glow")
CH = {'U': UNO, 'A': AURA, 'P': PHAR, 'M': MUM}
NAMES = {'U': 'Uno', 'A': 'Aura', 'P': 'Pharaoh', 'M': 'Mummies x2'}
REFS = {'U': 'refs/uno-archaeologist-MASTER.jpg', 'A': 'refs/aura-archaeologist-MASTER.jpg', 'P': 'refs/pharaoh-MASTER-v1.jpg', 'M': 'refs/pharaoh-MASTER-v1.jpg (bandage/eye style only)'}
DANCE = ("Every creature in frame (scarabs, mummies, the Pharaoh and his crown cobra) bobs its head and dances on the beat. ")
BEAT = "Motion accents land on the heavy bass hits of a 107.67 BPM beat; the cut punches in on a bass hit."
LOC = {'dunes': ('refs/bg_dunes.jpg', 'moonlit Giza sand dunes with the pyramids under a huge full moon, deep blue night'),
       'entrance': ('refs/bg_dunes.jpg', 'a dark stone tomb entrance cut into a moonlit dune, pyramids behind'),
       'corridor': ('refs/bg_corridor.jpg', 'a narrow torch-lit tomb corridor with hieroglyph walls and green-flame torches'),
       'chamber': ('refs/bg_chamber.jpg', 'the burial chamber with a gold-and-lapis sarcophagus on a stone dais, green torchlight'),
       'hall': ('refs/bg_hall.jpg', 'the great pillared hall of the tomb used as a dance floor, green and gold torchlight')}

# (bar, type, loc, chars, action, framing, overlay preset, text) ; type G = Grok clip, P = still + parallax, S = scenery + overlays
# text: ('cap'|'lyr'|'sfx', words[, cue]) ; G shots use 1-2 bars (<= 4.4 s) so they stay under 6 s
SHOTS = [
 (0,  'S', 'dunes', '', 'Pyramids and moon, sand drifting off the dune crests', 'wide', 'desert_night', ('cap', 'Giza. Halloween night.')),
 (2,  'S', 'dunes', '', 'Closer on the dune ridge, wind lifts sand on the first drop', 'wide', 'desert_night', ('cap', 'Under the sand, something is listening.')),
 (5,  'G', 'dunes', 'UA', 'Uno and Aura walk side by side left to right across the frame, Uno holding a burning torch', 'waist-up walking', 'desert_night', None),
 (7,  'G', 'dunes', 'U', 'Uno stops, turns toward camera with his gold-grill smirk and speaks one short line, torch raised', 'waist-up', 'desert_night', None),
 (9,  'P', 'dunes', 'A', 'Aura looks up at the pyramids, hair strands glowing (still)', 'waist-up', 'desert_night', None),
 (10, 'G', 'dunes', 'A', 'Aura walks forward singing, hair cables swaying in the wind', 'waist-up walking', 'desert_night', None),
 (12, 'S', 'dunes', '', 'Sand rising off a dune toward the moon', 'wide', 'desert_night', None),
 (14, 'G', 'entrance', 'UA', 'Uno and Aura walk toward the tomb entrance, torchlight on their coats', 'waist-up walking', 'desert_night', None),
 (16, 'G', 'entrance', 'UA', 'Uno and Aura dance side by side in front of the entrance: hip-hop shoulder bounce into an Egyptian profile arm pose', 'waist-up', 'desert_night', None),
 (18, 'S', 'entrance', '', 'Tomb entrance; the torches flare green on the drop', 'wide', 'tomb_embers', ('lyr', "The pharaoh's wakin' up")),
 (21, 'P', 'chamber', '', 'First look at the sealed sarcophagus (still, parallax on the dais)', 'wide', 'crypt', ('cap', 'Inside, the tomb was breathing.')),
 (24, 'S', 'corridor', '', 'Corridor mouth, dust motes in torchlight', 'wide', 'crypt', None),
 (26, 'G', 'corridor', 'U', 'Uno walks down the corridor holding the torch', 'waist-up walking', 'crypt', None),
 (28, 'G', 'corridor', 'UA', 'Uno lifts the torch while Aura plays a short gold flute', 'waist-up', 'crypt', None),
 (30, 'G', 'corridor', 'A', 'Aura glances nervously to the side and leans toward the camera-left', 'waist-up', 'crypt', None),
 (32, 'G', 'corridor', 'U', 'Uno bounces his shoulders on the bass and flashes his gold-grill smirk', 'waist-up', 'crypt', None),
 (34, 'S', 'corridor', '', 'Hieroglyph wall, glyphs pulse green on each kick (engine glow layer keyed to kicks)', 'medium', 'crypt', None),
 (36, 'G', 'corridor', '', 'Gold scarabs on a stone ledge bob their heads and shuffle in a little dance line on the beat (no characters)', 'low medium', 'crypt', None),
 (38, 'P', 'chamber', '', 'The gold coffin shining (still, parallax)', 'medium', 'crypt', None),
 (40, 'G', 'chamber', '', 'One bandage end on the coffin lid twitches and bobs in time with the beat (no characters)', 'close on lid', 'crypt', None),
 (42, 'G', 'chamber', 'A', 'Aura sings with one hand raised, green torchlight on her face', 'waist-up', 'crypt', None),
 (44, 'G', 'chamber', 'U', 'Uno nods to the beat, eyes on the coffin', 'waist-up', 'crypt', None),
 (46, 'S', 'chamber', '', 'Sand trickles off the lid, green mist leaks from the seam', 'medium', 'crypt', None),
 (48, 'G', 'chamber', '', 'The sarcophagus lid slowly slides sideways a little (no characters)', 'medium', 'crypt', None),
 (50, 'G', 'chamber', '', 'The lid slams onto the floor, dust bursts up (no characters)', 'medium', 'crypt', ('sfx', 'BAM!', 'lid slams onto the floor exactly on the 1:51.57 drop (the only BAM in the video)')),
 (52, 'S', 'chamber', '', 'Open sarcophagus, green mist pouring over the rim', 'medium', 'crypt', ('cap', 'Three thousand years asleep.')),
 (55, 'P', 'chamber', 'UA', 'Uno and Aura frozen in shock, lit green from below (still)', 'waist-up', 'crypt', ('cap', 'Then something sat up.')),
 (57, 'S', 'chamber', '', 'Chamber wide, mist and embers swirling around the dais', 'wide', 'tomb_embers', ('lyr', "The tomb is breathin'")),
 (59, 'G', 'chamber', 'P', 'RISE 1/3: the lid is already off and the coffin is OPEN; a clawed bony bandaged hand rises up from inside the open coffin and grips its inner rim', 'medium', 'crypt', None),
 (61, 'G', 'chamber', 'P', 'RISE 2/3: the Pharaoh sits up stiffly inside the open sarcophagus, head starting to bob to the beat', 'medium', 'crypt', None),
 (63, 'G', 'chamber', 'P', 'RISE 3/3: standing, the Pharaoh tilts his head side to side on the beat, crown cobra bobbing, green eyes flare', 'waist-up', 'crypt', None),
 (64, 'G', 'hall', 'P', 'The Pharaoh dances: Egyptian sliding-neck head move into a hip-hop shoulder bounce, crown cobra bobbing', 'waist-up, dance', 'crypt', None),
 (65, 'G', 'hall', 'U', 'Uno answers with a hip-hop chest pop into a flat-palm Egyptian arm pose, gold-grill smirk', 'waist-up', 'crypt', None),
 (66, 'G', 'hall', 'P', 'DANCE 1/2: the Pharaoh does a hip-hop arm wave that ends in a stiff Egyptian profile pose', 'waist-up, dance', 'crypt', None),
 (67, 'G', 'hall', 'P', 'DANCE 2/2: he snaps his head side to side on the bass hits and points at camera-left', 'waist-up, dance', 'crypt', None),
 (68, 'G', 'hall', 'UP', 'The Pharaoh plucks a small gold champion crown out of Uno\'s hand', 'waist-up', 'crypt', None),
 (69, 'G', 'hall', 'A', 'Aura sings and shimmies her shoulders, hands framing her face in an Egyptian pose', 'waist-up', 'crypt', None),
 (70, 'G', 'hall', 'P', 'The Pharaoh, now wearing the gold crown, rubs his clawed fingers together', 'waist-up', 'crypt', None),
 (72, 'G', 'hall', 'AP', 'Slow eerie sway: Aura and the Pharaoh face each other and turn slowly', 'waist-up', 'tomb_embers', None),
 (74, 'P', 'hall', 'A', 'Aura in gold-and-green light, hair strands glowing (still)', 'waist-up', 'tomb_embers', ('lyr', 'Ooh-aah')),
 (75, 'G', 'hall', 'P', 'The Pharaoh turns slowly, green mist trailing from his eyes', 'waist-up', 'tomb_embers', None),
 (77, 'S', 'dunes', '', 'The pyramids start to glow green under the moon', 'wide', 'desert_night', None),
 (78, 'G', 'hall', 'U', 'Uno twists the dial of a gold boombox up to max', 'waist-up', 'crypt', None),
 (79, 'G', 'hall', 'M', 'Two mummies line-dance in step, head bobs and Egyptian arm angles mixed with hip-hop arm swings (engine tiles the clip into 3 receding rows)', 'waist-up, dance', 'crypt', None),
 (81, 'G', 'hall', 'UP', 'Uno and the Pharaoh side by side do the same hip-hop arm wave into an Egyptian arm pose, heads bobbing', 'waist-up', 'crypt', None),
 (82, 'G', 'hall', 'A', 'Aura dances, arms up in a snake-arm Egyptian move with hip-hop hip sway, under the glowing ceiling', 'waist-up', 'crypt', None),
 (83, 'S', 'hall', '', 'Ceiling crack opens to the moon, dust falls', 'wide', 'crypt', None),
 (84, 'G', 'hall', 'P', 'Curse breaks: the Pharaoh\'s eyes flash from green to gold and the mist blows away', 'waist-up', 'tomb_embers', None),
 (86, 'G', 'hall', 'A', 'Aura sings the last hook, swaying', 'waist-up', 'tomb_embers', None),
 (88, 'G', 'hall', 'UA', 'Uno and Aura dance side by side: Egyptian sliding-neck head move and hip-hop shoulder bounce', 'waist-up', 'tomb_embers', None),
 (90, 'G', 'hall', 'M', 'Two mummies line-dance with head bobs and Egyptian arm angles (tiled into rows, reuse grid from shot 79)', 'waist-up, dance', 'tomb_embers', None),
 (92, 'G', 'hall', 'P', 'The Pharaoh crosses his arms, proud, crown on, head bobbing to the beat', 'waist-up', 'tomb_embers', None),
 (94, 'S', 'hall', '', 'Empty dance floor, torches flare on the drop, gold embers', 'wide', 'tomb_embers', ('lyr', 'Dance, dance')),
 (96, 'P', 'hall', 'P', 'The Pharaoh in gold light (still, parallax)', 'waist-up', 'tomb_embers', ('cap', "The curse was broken. The party wasn't.")),
 (98, 'S', 'dunes', '', 'Pyramids glowing gold, sand drifting', 'wide', 'desert_night', None),
 (100, 'G', 'hall', 'UA', 'Uno and Aura strike a pose and wave', 'waist-up', 'tomb_embers', ('lyr', 'Happy Halloween...')),
 (101, 'G', 'hall', 'P', 'The Pharaoh strikes an Egyptian profile pose on the bass hit', 'waist-up', 'tomb_embers', ('lyr', '...from the tomb')),
 (102, 'S', 'hall', '', 'Dance floor after the party, embers drifting (tail drop)', 'wide', 'tomb_embers', None),
 (105, 'P', 'chamber', '', 'Empty open sarcophagus, crown resting on the rim (still)', 'medium', 'crypt', ('cap', 'Some kings just need a dance floor.')),
 (108, 'S', 'dunes', '', 'Pyramids under the moon', 'wide', 'desert_night', None),
 (111, 'S', 'dunes', '', 'Sand drifts over the tomb entrance', 'wide', 'desert_night', ('cap', 'Happy Halloween from Progressive Slop.')),
 (114, 'E', 'card', '', 'End card fades in over the tail and holds to the end', 'card', 'desert_night', ('cap', 'See the whole story @progressiveslop')),
]

def t_of(bar):
    if bar == 0: return 0.0, 'song start'
    t = BARS[bar]; d = min(DROPS, key=lambda x: abs(x - t))
    return (round(d, 3), 'drop') if abs(d - t) < 0.05 else (round(t, 3), 'downbeat')

def lyric_at(t0, t1):
    return [l['text'] for l in LT['lines'] if t0 - 0.3 <= l['t'] < t1 - 0.3]

def section_at(t):
    s = [x for x in LT['sections'] if x['t'] <= t + 0.01]; return s[-1]['label'] if s else 'Intro'

def start_prompt(chars, loc, framing, action):
    who = '; '.join(CH[c] for c in chars) if chars else 'No characters in frame'
    rb = set(chars) & {'U', 'A'}
    clothes = (CLOTH + ' ') if rb else ''
    eyes = (EYES + ' ') if rb else ''
    pe = "The Pharaoh's eyes glow green. " if 'P' in chars else ''
    refs = ', '.join(REFS[c] for c in chars) + (', ' if chars else '') + LOC[loc][0]
    note = ' Do NOT attach the Uno or Aura sheets for the Pharaoh; he must never resemble Uno.' if 'P' in chars else ''
    return (f"Attach master sheet(s): {refs}. {clothes}Match the reference sheets exactly.{note} {framing} shot,{' framed from the waist up (no legs in frame),' if chars else ''} locked static camera, at most 2 characters, {LOC[loc][1]}. {who}. Pose: {action}, "
            f"captured at the first moment of the action. {eyes}{pe}"
            "Glossy cinematic comic-book rendering, high contrast, Egyptian tomb lighting, 16:9.").replace('  ', ' ')

def motion_prompt(chars, action):
    rb = set(chars) & {'U', 'A'}
    clothes = (CLOTH + ' ') if rb else ''
    eyes = (EYES + ' ') if rb else ''
    smile = ''
    if 'U' in chars: smile += "Uno keeps his big swagger smirk-smile showing the shiny gold grill; hands relaxed and open, never fists. "
    if 'A' in chars: smile += "Aura moves with confident movie-star swagger. "
    pe = "The Pharaoh's green eyes keep glowing; his tattered bandage strips swing with the beat. " if 'P' in chars else ''
    dance = DANCE if (set(chars) & {'P', 'M'} or any(w in action.lower() for w in ('scarab', 'bandage', 'cobra'))) else ''
    return f"{clothes}{LOCK}{WAIST if chars else ''} One simple action only: {action}. {smile}{eyes}{pe}{dance}No new characters enter. No sound-effect lettering. {BEAT}"

out = []
for i, (bar, typ, loc, chars, action, framing, ov, text) in enumerate(SHOTS):
    t0, kind = t_of(bar)
    if i + 1 < len(SHOTS): t1, _ = t_of(SHOTS[i + 1][0])
    else: t1 = DUR
    hits = [d for d in DROPS if t0 < d < t1]
    if typ in 'SP':
        sn = [s for s in SN if t0 + 0.6 < s < t1 - 0.3]
        hits += sn[:1] + (sn[-1:] if len(sn) > 2 else [])
    sh = {'id': f's{i + 1:02d}', 'bar': bar, 't': t0, 'end': round(t1, 3), 'dur': round(t1 - t0, 2), 'snap_start': kind,
          'section': section_at(t0), 'location': loc, 'bg': LOC[loc][0] if loc in LOC else 'engine end card',
          'characters': [NAMES[c] for c in chars], 'type': {'G': 'grok_clip', 'P': 'still_parallax', 'S': 'scenery_overlays', 'E': 'end_card'}[typ],
          'action': action, 'framing': framing, 'overlay': ov, 'punch_hits': sorted(round(h, 3) for h in hits),
          'lyrics_sung': lyric_at(t0, t1)}
    if text:
        sh['text'] = {'kind': {'cap': 'caption', 'lyr': 'lyric', 'sfx': 'sfx'}[text[0]], 'text': text[1],
                      'preset': {'cap': 'comic_caption', 'lyr': 'lyric_gold', 'sfx': 'sfx'}[text[0]]}
        if len(text) > 2: sh['text']['cue'] = text[2]
    if typ == 'G':
        assert t1 - t0 <= 6.0, sh['id']
        sh['grok'] = {'refs': [REFS[c] for c in chars] + [LOC[loc][0]], 'start_frame_prompt': start_prompt(chars, loc, framing, action),
                      'motion_prompt': motion_prompt(chars, action), 'clip_len': 6 if t1 - t0 > 4.5 else 5,
                      'note': 'Never attach Uno\'s master when generating the Pharaoh.' if 'P' in chars and 'U' not in chars else
                              ('Generate the Pharaoh start frame separately (no Uno master), then composite with Uno before the start-frame gate.' if 'P' in chars else '')}
    if typ == 'P': sh['parallax'] = 'locked_subtle'
    out.append(sh)

assert sum(1 for s in out if s.get('text', {}).get('text', '').upper().startswith('BAM')) == 1
TR0, TR1 = 111.572, out[[s['id'] for s in out].index('s39')]['t']   # bars 50-72: lid slam -> end of the dance battle
short = {'format': '1080x1920 (9:16)', 'audio': [TR0, TR1], 'shots': [s['id'] for s in out if TR0 <= s['t'] < TR1],
         'end_card': {'text': 'See the whole story @progressiveslop', 'dur': 5.0, 'audio': 'song continues under the card, 0.6 s fade'},
         'dur': round(TR1 - TR0 + 5.0, 2),
         'reframe': 'centre-crop each 16:9 shot to 9:16 on the character/face box (camera.py plan, no push); scenery crops on the sarcophagus; captions re-placed inside the Short safe band'}
json.dump({'song': "The Pharaoh's Waking Up", 'tempo': A['tempo'], 'duration': DUR, 'snap_rule': 'every boundary is a detected downbeat; drops where one lands; in-shot punch-ins snap via music_fx SNAP_PRESETS["hard"]',
           'shots': out, 'short_trailer': short}, open(f'{R}/shotlist.json', 'w'), indent=1)

f = lambda t: f'{int(t // 60)}:{t % 60:05.2f}'
cnt = {k: sum(1 for s in out if s['type'] == k) for k in ('grok_clip', 'still_parallax', 'scenery_overlays', 'end_card')}
md = ["# The Pharaoh's Waking Up - shot list", '',
      f"{len(out)} shots, {f(DUR)}, {A['tempo']} BPM. Generated by `specs/build_shotlist.py` from `audio/analysis.json` and `audio/lyric_timing.json`; every boundary is a detected downbeat (drops where one lands). Grok clips are all <= 4.4 s (1-2 bars).", '',
      f"Counts: {cnt['grok_clip']} Grok clips, {cnt['still_parallax']} stills with parallax, {cnt['scenery_overlays']} scenery + overlays, {cnt['end_card']} end card. The single BAM is s{[s['id'] for s in out if s.get('text', {}).get('preset') == 'sfx'][0][1:]} (lid slam on the 1:51.57 drop).", '',
      '## Rules applied to every shot', '- At most 2 characters, locked static camera, one simple action, clips <= 6 s; walking is waist-up.',
      "- Archaeologist looks (locked masters refs/uno-archaeologist-MASTER.jpg, refs/aura-archaeologist-MASTER.jpg): Uno V-taper, khaki shirt, cargo pants, purple fur coat, gold \"1\", satchel, gold grill smirk; Aura hourglass, buttoned khaki safari jacket, burgundy scarf. Slim built-in headphones, fully clothed, waist-up only. Every start prompt names its master sheets.",
      "- All creatures (scarabs, mummies, crown cobra, Pharaoh) bob heads and dance on the beat; dance shots mix Egyptian moves with hip hop; cuts punch on bass hits.",
      '- Start-frame gate: generate start frames in Grok Imagine with the masters attached, check side by side before animating. Never attach Uno\'s master when generating the Pharaoh.',
      '- Lettering never covers a face (music_fx TypeLayer); SFX only on a motivated cue.', '',
      '## Overview', '', '| id | time | dur | section | type | location | characters | action | text | snap |', '|---|---|---|---|---|---|---|---|---|---|']
for s in out:
    tx = f"{s['text']['preset']}: {s['text']['text']}" if 'text' in s else ''
    md.append(f"| {s['id']} | {f(s['t'])}-{f(s['end'])} | {s['dur']} | {s['section']} | {s['type']} | {s['location']} | {', '.join(s['characters']) or '-'} | {s['action']} | {tx} | {s['snap_start']}{'; hits ' + ', '.join(map(str, s['punch_hits'])) if s['punch_hits'] else ''} |")
md += ['', '## Short trailer (9:16)', '', f"- Audio {f(short['audio'][0])}-{f(short['audio'][1])} (lid slam BAM, rise, dance battle) + {short['end_card']['dur']} s end card \"{short['end_card']['text']}\" = **{short['dur']} s**.",
       f"- Shots: {', '.join(short['shots'])}, then the end card.", f"- {short['reframe']}.", '', '## Shot details', '']
for s in out:
    md += [f"### {s['id']}  {f(s['t'])}-{f(s['end'])} ({s['dur']} s), {s['section']}, {s['type']}", '',
           f"- Location: {s['location']} (`{s['bg']}`), characters: {', '.join(s['characters']) or 'none'}, framing: {s['framing']}",
           f"- Action: {s['action']}", f"- Overlay preset: `{s['overlay']}`" + (f", parallax `{s['parallax']}`" if 'parallax' in s else ''),
           f"- Snap: start on {s['snap_start']}" + (f"; punch-ins at {', '.join(map(str, s['punch_hits']))}" if s['punch_hits'] else '')]
    if s['lyrics_sung']: md.append(f"- Sung: " + ' / '.join(s['lyrics_sung']))
    if 'text' in s: md.append(f"- Lettering: `{s['text']['preset']}` \"{s['text']['text']}\"" + (f" (cue: {s['text']['cue']})" if 'cue' in s['text'] else ''))
    if 'grok' in s:
        g = s['grok']; md += [f"- Grok refs: {', '.join(g['refs'])}; clip length {g['clip_len']} s, trim to {s['dur']} s" + (f"; {g['note']}" if g['note'] else ''),
                              f"- **Start frame prompt:** {g['start_frame_prompt']}", f"- **Motion prompt:** {g['motion_prompt']}"]
    md.append('')
open(f'{R}/shotlist.md', 'w').write('\n'.join(md))
os.makedirs(f'{R}/prompts', exist_ok=True)
for s_ in out:
    if 'grok' in s_:
        open(f"{R}/prompts/{s_['id']}_start.txt", 'w').write(s_['grok']['start_frame_prompt'])
        open(f"{R}/prompts/{s_['id']}_motion.txt", 'w').write(s_['grok']['motion_prompt'])
print(cnt, 'short', short['dur'], short['shots'])

# Optional Jev sanity check of the authored shots against the rules (text-only judgment; numeric asserts above stay
# authoritative). Opt in with JEV_SHOTLIST_CHECK=1; skipped silently when Jev is unavailable.
if os.environ.get('JEV_SHOTLIST_CHECK') == '1':
    import sys; sys.path.insert(0, '/workspace/webshots-upstream/scripts')
    try:
        from jev_qa import check_shotlist
        res = check_shotlist({'shots': out}); bad = [r['id'] for r in res if r['flag']]
        esc = [r['id'] for r in res if r['action'] == 'escalate']
        print('jev shotlist check: flagged', bad or 'none', '| escalate', esc or 'none')
    except Exception as e:
        print('jev shotlist check skipped:', e)

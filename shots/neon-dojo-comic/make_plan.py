"""Neon Dojo comic mode, full song: draft spec + plan.md + prompts.json + motion.txt (planning only, no art).
The single-page proof scene is shots/neon-dojo-comic/neon-dojo-comic.comic.json; the full song is
shots/neon-dojo-comic/neon-dojo-comic-full.comic.json."""
import json, bisect, os
REPO = '/workspace/webshots-upstream'
OUT = '/workspace/neon-dojo-comic'
TL = json.load(open(f'{REPO}/shots/neon-dojo-fighter/stage/timeline.json'))
B, DB, END = TL['beats'], TL['downbeats'], TL['duration']

def snap(t): return min(B, key=lambda b: abs(b - t))
def next_beat(t): return B[bisect.bisect_right(B, t + 0.05)]

# Brand: every robot chrome, red eyes, headphone ears. Kid-safe: nobody gets hurt, knockouts are comic.
CAST = {
 'Uno': 'Uno (round smooth chrome head, purple fur coat, gold "1" chain)',
 'Aura': 'Aura (crimson-streaked dark hair, modest crimson bodysuit, cyan magic)',
 'SHOGUN': 'SHOGUN.EXE (horned samurai mecha, black-red armor)',
 'KAZE-9': 'KAZE-9 (scarf ninja, twin blades)',
 'RAIJIN': 'RAIJIN (boxer, lightning gauntlets)',
 'TEKKO': 'TEKKO (squat sumo robot, piston arms)',
 'LOTUS': 'LOTUS (long-legged crane kicker)',
 'Sensei': 'Sensei Gearhart (old robot, cable beard, cane)',
}
REFNAMES = {'Uno', 'Aura', 'SHOGUN', 'KAZE-9', 'RAIJIN'}   # reference images exist for these
STYLE = ("{scene}. {chars}. All robots chrome, red eyes, headphone ears. "
         "1990s superhero comic, bold ink, halftone, neon magenta-cyan, 16:9, no text.")
MOTION = ("{move}. {sec}. Camera: {cam}. Slow, simple, clean motion; nobody walks toward the camera. "
          "Keep the comic style, faces, hands and limb count; no morphing, no text, no cuts.")

LYR = [(4.08, "YEAH, YOU KNOW THE VIBE"), (8.12, "QUICK FEET ON THE CONCRETE, MOVE SMOOTH, NEVER MESSY"),
 (34.3, "ONE-TWO IN A CLEAN SWEEP, LIKE A WHISPER IN THE BREEZE"), (42.48, "I MOVE CALM WITH THE JAW GAME"),
 (46.4, "SHORT SWING, LIKE A CLOCK HAND, PRECISE AND TO THE POINT"), (50.34, "HIT HARD, THEN I STOP"),
 (61.04, "SAY MY NAME, THEN BITE THE TONGUE"), (64.5, "WHEN IT POPS, IT'S ALREADY DONE"),
 (68.64, "KNUCKLE TALK, KNUCKLE TALK"), (73.66, "HANDS UP, THEN IT ALL FALLS"), (77.0, "KNUCKLE TALK, KNUCKLE TALK"),
 (80.48, "I DON'T ARGUE, I JUST WALK"), (82.1, "TOE-TO-TOE, NAH, I DON'T OVERDO"), (85.2, "LITTLE WORK, LET THE MOVES SPEAK TRUE"),
 (88.5, "DUCK LOW, THEN I CUT THROUGH"), (91.58, "TURN A FRONT LIKE A BACKDOOR VIEW"),
 (95.38, "NO CHESS, JUST A SLICK CHECK"), (98.64, "NO FLEX, BUT A QUICK NECK"),
 (102.1, "IF THE ROOM START TO GET LOUD"), (105.62, "I MAKE ROOM WITH A CLEAN STEP"),
 (107.98, "COUNT IT OUT, ONE BY ONE"), (115.18, "SAY MY NAME, THEN BITE THE TONGUE"), (117.96, "WHEN IT POPS, IT'S ALREADY DONE"),
 (124.92, "KEEP IT CLOSE, KEEP IT SMALL"), (128.34, "HANDS UP, THEN IT ALL FALLS"), (131.7, "TAP THE CHIN, MAKE 'EM CRAWL"),
 (135.2, "I DON'T ARGUE, I JUST WALK"), (136.98, "THEY TALKING TOUGH, THEIR WORDS ARE TALKING THIN"),
 (140.76, "I JUST GRIN, THEN I SPIN"), (144.2, "ONE SHARP MOVE, WHOLE ROOM STILL, LIKE A FREEZE FRAME"),
 (147.76, "THAT'S THE WAY I SAY WHAT I SAY"), (151.1, "KNUCKLE TALK, KNUCKLE TALK"), (155.84, "HANDS UP, THEN IT ALL FALLS"),
 (160.7, "KNUCKLE TALK, KNUCKLE TALK"), (162.18, "I DON'T ARGUE, I JUST WALK")]

Y, C, M, W = [255, 214, 0], [90, 230, 255], [255, 90, 200], [255, 255, 255]
P = lambda **k: k
# pages: (id, start downbeat, end downbeat|None, note, [(downbeat, 'a'|'b'|'c'|'splash', panel)])
PAGES = [
 ('page01', 0, 8, 'intro - Neo-Kyoto wakes up', [
  (0, 'a', P(id='n01', loc='neo-kyoto skyline', cam='extreme wide', moment='city at night',
     scene='Extreme wide shot of a rainy neon city at night, pagoda towers and a tournament blimp with a glowing fist logo shape', refs=[],
     move='Rain falls and the blimp drifts slowly left', sec='Neon signs flicker softly', cam_m='locked off', exp=5.5)),
  (4, 'b', P(id='n02', loc='rain-soaked rooftop', cam='extreme close-up', moment='eyes power on',
     scene='Extreme close-up of Uno in the rain, his red eyes powering on, gold chain glinting', refs=['Uno'],
     move="Uno's red eyes slowly light up", sec='Raindrops run down the chrome', cam_m='very slow push-in', exp=5.0,
     sfx=('VMMM', [0.78, 0.5], -6, M))),
 ]),
 ('page02', 8, 16, 'backstory - the dojo falls', [
  (8, 'a', P(id='n03', loc='old wooden dojo', cam='warm medium shot', moment='bow to the master',
     scene='Sepia-purple flashback: small young Uno bowing to Sensei Gearhart in a cosy wooden dojo, golden belt on the wall', refs=['Uno'], extra=['Sensei'],
     move='Young Uno bows slowly and the Sensei nods', sec='Dust motes float in the light', cam_m='locked off', exp=5.5)),
  (12, 'b', P(id='n04', loc='dojo gate at night', cam='low-angle silhouette', moment='the belt is taken',
     scene='Low-angle silhouette of SHOGUN.EXE carrying the golden dojo belt away through the gate, lanterns glowing red behind him', refs=['SHOGUN'],
     move='SHOGUN turns his head slowly, visor lighting red', sec='His cape ripples, lanterns sway', cam_m='locked off', exp=5.5,
     sfx=('SHHHK', [0.2, 0.5], 5, M))),
 ]),
 ('page03', 16, 24, 'Aura breaks free, the team forms', [
  (16, 'a', P(id='n05', loc='server cable cavern', cam='medium shot from below', moment='chains of light',
     scene='Aura breaking glowing server-cable chains with a burst of cyan magic inside a dark cable cavern', refs=['Aura'],
     move='The cables snap apart in a slow cyan pulse', sec='Her crimson-streaked hair lifts', cam_m='locked off', exp=5.0,
     sfx=('SNAP!', [0.78, 0.25], 6, C))),
  (20, 'b', P(id='n06', loc='rooftop water tower', cam='behind-the-back wide', moment='together',
     scene="Uno and Aura sitting side by side on a rooftop water tower, seen from behind, watching the tournament blimp pass", refs=['Uno', 'Aura'],
     move='The blimp drifts past and Aura nudges Uno', sec="Uno's fur coat ruffles in the wind", cam_m='locked off', exp=5.5)),
 ]),
 ('page04', 24, 40, 'fight 1 - Uno vs TEKKO, rooftop dojo', [
  (24, 'a', P(id='n07', loc='neon rooftop dojo', cam='side-on wide', moment='bow before the bout',
     scene='Side-on wide shot of Uno and TEKKO bowing to each other on a neon rooftop dojo ring, crowd of chrome robot fans behind', refs=['Uno'], extra=['TEKKO'],
     move='Both fighters bow and straighten up', sec='Fans wave glow sticks', cam_m='locked off', exp=5.5)),
  (29, 'b', P(id='n08', loc='rooftop dojo ring', cam='over-the-shoulder close', moment='block the piston slap',
     scene="Over TEKKO's shoulder: Uno blocking a piston palm slap with crossed forearms, sparks flying", refs=['Uno'], extra=['TEKKO'],
     move='The palm presses in and Uno holds the block', sec='Small sparks drift', cam_m='locked off', exp=5.0,
     sfx=('KLAK!', [0.78, 0.3], -6, Y))),
  (34, 'c', P(id='n09', loc='speed-line void', cam='eye-level close-up', moment='super cut-in: Uno',
     scene='Super-move cut-in: close-up of Uno, red eyes flaring bright, purple speed lines behind him', refs=['Uno'],
     move="Uno's eyes flare brighter and the speed lines stream", sec='Fur coat trembles with power', cam_m='locked off', exp=4.0,
     sfx=('FWOOM!', [0.78, 0.5], -6, M))),
  (37, 'splash', P(id='s10', loc='rooftop dojo edge', cam='wide action splash', moment='TEKKO on the cushions',
     scene='Uno finishing a spinning kick while TEKKO tumbles harmlessly onto a giant pile of dojo cushions, stars circling his head', refs=['Uno'], extra=['TEKKO'],
     move='TEKKO bounces gently on the cushions', sec='Stars circle his head, cushions puff', cam_m='slow push-in', exp=4.5,
     sfx=('POMF!', [0.7, 0.3], 7, Y))),
 ]),
 ('page05', 40, 47, 'chorus 1 - rival montage', [
  (40, 'a', P(id='n11', loc='rain alley night market', cam='dutch angle', moment='Aura vs KAZE-9',
     scene='Dutch angle in a rainy night-market alley: Aura facing KAZE-9, his twin blades crossed, paper lanterns overhead', refs=['Aura', 'KAZE-9'],
     move="KAZE-9's scarf streams as Aura's palm glows cyan", sec='Lanterns sway, rain falls', cam_m='locked off', exp=5.0,
     sfx=('SHING!', [0.78, 0.25], 6, C))),
  (43, 'b', P(id='n12', loc='neo train yard', cam='low angle', moment='Uno vs RAIJIN',
     scene='Low angle in a neon train yard: Uno raising his guard as RAIJIN winds up a crackling thunder hook', refs=['Uno', 'RAIJIN'],
     move="RAIJIN's gauntlet crackles and Uno raises his guard", sec='Electric sparks flicker on the rails', cam_m='locked off', exp=5.5,
     sfx=('KZZZT!', [0.78, 0.3], -6, Y))),
 ]),
 ('page06', 47, 63, 'fight 2 - Aura vs LOTUS, hologram garden', [
  (47, 'a', P(id='n13', loc='pagoda hologram garden', cam='symmetrical wide', moment='bow on the bridge',
     scene='Symmetrical wide shot of Aura and LOTUS bowing on an arched bridge in a hologram pagoda garden, cherry petals', refs=['Aura'], extra=['LOTUS'],
     move='Both bow slowly on the bridge', sec='Hologram petals drift down', cam_m='locked off', exp=5.5)),
  (51, 'b', P(id='n14', loc='garden stepping stones', cam='low ground-level', moment='duck under the spin kick',
     scene="Ground-level shot of Aura ducking low as LOTUS's spin kick sweeps over her head, fan tail swirling", refs=['Aura'], extra=['LOTUS'],
     move="LOTUS's kick sweeps slowly over Aura's head", sec='Petals swirl in the kick wind', cam_m='locked off', exp=5.0,
     sfx=('WHSSH!', [0.78, 0.25], 6, C))),
  (57, 'c', P(id='n15', loc='garden spectator stands', cam='high angle', moment='the crowd gets loud',
     scene='High angle over cheering chrome robot fans in garden stands, waving fans and glow banners', refs=[],
     move='The crowd jumps and waves on the beat', sec='Glow banners sway', cam_m='locked off', exp=5.0,
     sfx=('WOOO!', [0.78, 0.3], -5, M))),
  (60, 'splash', P(id='s16', loc='koi pond', cam='splash from the water line', moment='LOTUS in the pond',
     scene="Aura's cyan wave spinning LOTUS gently into a koi pond with a big comic splash, glowing robot koi fish leaping", refs=['Aura'], extra=['LOTUS'],
     move='The water splash rises and falls slowly', sec='Koi fish leap', cam_m='locked off', exp=4.5,
     sfx=('SPLOOSH!', [0.7, 0.3], 6, C))),
 ]),
 ('page07', 63, 72, 'boss reveal - the server temple', [
  (63, 'a', P(id='n17', loc='server temple throne', cam='extreme low angle', moment='SHOGUN wakes',
     scene='Extreme low angle of SHOGUN.EXE rising from a throne of server racks, horned helmet, eyes igniting red', refs=['SHOGUN'],
     move="SHOGUN's eyes ignite and he rises slowly", sec='Server lights blink, red smoke curls', cam_m='slow tilt up', exp=5.0)),
  (66, 'b', P(id='n18', loc='throne pedestal', cam='insert close-up', moment='the stolen belt',
     scene="Close-up of SHOGUN.EXE's armored hands lifting the stolen golden dojo belt, red light glinting", refs=['SHOGUN'],
     move='The belt lifts and the gold glints', sec='Red light pulses', cam_m='locked off', exp=4.5)),
  (69, 'splash', P(id='s19', loc='temple courtyard', cam='split-frame tag-team splash', moment='two vs one',
     scene='Uno and Aura back to back in cyan light facing giant SHOGUN in red light', refs=['Uno', 'Aura', 'SHOGUN'],
     move="Aura's magic and SHOGUN's red aura pulse", sec="Uno's coat and SHOGUN's cape ripple", cam_m='locked off', exp=4.5,
     sfx=('VS!', [0.5, 0.25], -4, Y))),
 ]),
 ('page08', 72, 80, 'chorus 2 - the boss hits back, tag-in', [
  (72, 'a', P(id='n20', loc='temple stone floor', cam='side-on medium', moment='katana wave',
     scene="Side-on shot of SHOGUN.EXE's red katana wave pushing Uno back, his heels sliding on the stone floor", refs=['Uno', 'SHOGUN'],
     move="Uno slides back slowly, holding his guard", sec='Red energy ripples past', cam_m='locked off', exp=5.5,
     sfx=('VWASH!', [0.78, 0.25], -6, M))),
  (76, 'b', P(id='n21', loc='temple pillar edge', cam='close two-shot', moment='tag hand-off',
     scene="Tag hand-off: Uno slapping Aura's outstretched hand as she leaps past him into the fight, cyan sparkle at the hands", refs=['Uno', 'Aura'],
     move='Their hands meet in a slow slap and Aura leaps forward', sec='Cyan sparks burst from the hands', cam_m='locked off', exp=5.5,
     sfx=('TAG!', [0.5, 0.25], 6, C))),
 ]),
 ('page09', 80, 91, 'bridge - standoff and the double super', [
  (80, 'a', P(id='n22', loc='wind-swept temple steps', cam='wide profile', moment='quiet standoff',
     scene='Wide profile on temple steps: Uno and Aura facing SHOGUN, one red leaf drifting between', refs=['Uno', 'Aura', 'SHOGUN'],
     move='A single leaf drifts slowly between them', sec='Capes and hair move in the wind', cam_m='locked off', exp=5.5)),
  (84, 'b', P(id='n23', loc='cyan energy void', cam='three-quarter close-up', moment='super cut-in: Aura',
     scene='Super-move cut-in: Aura charging a bright cyan magic orb between her hands, speed lines behind', refs=['Aura'],
     move='The cyan orb grows slowly between her hands', sec='Her hair lifts in the energy', cam_m='locked off', exp=4.0,
     sfx=('HMMMN', [0.78, 0.3], -5, C))),
  (87, 'splash', P(id='s24', loc='temple roof', cam='heroic double-super splash', moment='armor pops into sparkles',
     scene="Uno's punch and Aura's cyan beam pop SHOGUN's armor into harmless sparkles; he sits dizzy", refs=['Uno', 'Aura', 'SHOGUN'],
     move='Sparkles burst outward and SHOGUN sits down', sec='Cyan and purple light flares', cam_m='slow push-in', exp=5.0,
     sfx=('KRAK-BOOM!', [0.6, 0.3], -6, Y))),
 ]),
 ('page10', 91, None, 'victory - the belt comes home', [
  (91, 'a', P(id='n25', loc='rebuilt dojo', cam='warm high angle', moment='belt returned',
     scene='Rebuilt dojo: Uno returns the golden belt to Sensei; KAZE-9 and RAIJIN bow', refs=['Uno', 'KAZE-9', 'RAIJIN'], extra=['Sensei'],
     move='The Sensei takes the belt and everyone bows', sec='Lanterns glow, petals drift', cam_m='locked off', exp=5.0)),
  (94, 'b', P(id='n26', loc='sunrise rooftop', cam='behind-the-back wide', moment='walk off into the sunrise',
     scene='Uno and Aura walking away from the camera across a rooftop into a pink sunrise over Neo-Kyoto', refs=['Uno', 'Aura'],
     move='They walk slowly away into the sunrise', sec='The sun rises and clouds glow', cam_m='locked off', exp=5.5)),
 ]),
]
PAGE_LAYOUT = {   # never the same layout or splash style on consecutive pages (QA)
 'page01': ('slant-two', None), 'page02': ('inset-two', None), 'page03': ('tilt-two', None),
 'page04': ('mixed-three', 'breakout'), 'page05': ('slant-two', None), 'page06': ('diagonal-three', 'tilt'),
 'page07': ('inset-two', 'full'), 'page08': ('tilt-two', None), 'page09': ('slant-two', 'breakout'),
 'page10': ('inset-two', None),
}
NARR = {'n01': 'NEO-KYOTO. THE TOURNAMENT RETURNS.', 'n03': 'YEARS AGO...', 'n06': 'TOGETHER.'}

def words(s): return len(s.split())

def build():
    pages, prompts, rows = [], [], []
    for pid, sdb, edb, note, items in PAGES:
        start = DB[sdb] if sdb else 0.0
        end = DB[edb] if edb is not None else END
        lands = [DB[db] for db, _, _ in items]
        pg = {'id': pid, 'note': note, 'start': round(start, 3), 'end': round(end, 3), 'panels': []}
        for k, (db, slot, f) in enumerate(items):
            land = DB[db]
            nxt = lands[k + 1] if k + 1 < len(items) else end
            chars = '; '.join(CAST[r] for r in f['refs'] + f.get('extra', []))
            prompt = STYLE.format(scene=f['scene'], chars=chars) if chars else STYLE.format(scene=f['scene'], chars='').replace('. . ', '. ')
            assert words(prompt) < 60, (f['id'], words(prompt))
            motion = MOTION.format(move=f['move'], sec=f['sec'], cam=f['cam_m'])
            lyr = [(t, s) for t, s in LYR if (land - 0.6 if k or pid != 'page01' else -1) <= t < nxt - 0.3]
            caps = []
            if f['id'] in NARR:
                caps.append({'text': NARR[f['id']], 'anchor': 'tl', 'at': round(next_beat(land) if land > B[0] else B[0], 3)})
            for i, (t, s) in enumerate(lyr[:2 - (1 if f['id'] in NARR else 0)]):
                anchor = ['bl', 'tl'][i] if f['id'] in NARR else ['tl', 'bl'][i]
                caps.append({'text': s, 'anchor': anchor, 'at': round(max(snap(t), land), 3), 'lyric': True})
            refs = [r for r in f['refs'] if r in REFNAMES] or ['none']
            u = {'id': f['id'], 'image': f'panels/{f["id"]}.jpg', 'at': round(land, 3),
                 'location': f['loc'], 'camera': f['cam'], 'moment': f['moment'], 'scene': f['scene'],
                 'prompt': prompt, 'refs': refs, 'motionPrompt': motion,
                 'clip': {'src': f'clips/{f["id"]}.mp4', 'in': None, 'out': None, 'expected': f['exp']},
                 'lyric': ' / '.join(s for _, s in lyr[:2]), 'captions': caps}
            if 'sfx' in f:
                txt, pos, rot, col = f['sfx']
                u['sfx'] = [{'text': txt, 'at': round(next_beat(next_beat(land)), 3), 'pos': pos, 'rot': rot,
                             'size': 0.17 if slot != 'splash' else 0.2, 'color': col}]
            dur = None
            if slot == 'splash':
                dur = land - max(b for b in B if b < land - 0.05)
                pg['transition'] = {'type': 'zoom', 'panel': pg['panels'][-1]['id'], 'at': round(land, 3), 'dur': round(dur, 3)}
                pg['splash'] = u
            else:
                u['slot'] = slot
                pg['panels'].append(u)
            prompts.append({'id': f['id'], 'prompt': prompt, 'refs': refs})
            rows.append((pid, slot, u, f, round(dur, 3) if dur else None))
        # expected clip length capped so the clip ends before the page turns
        cut = pg['transition']['at'] - pg['transition']['dur'] if pg.get('transition') else pg['end']
        for u2 in pg['panels'] + ([pg['splash']] if pg.get('splash') else []):
            page_cut = pg['end'] if u2 is pg.get('splash') else cut
            avail = round(page_cut - next_beat(u2['at']) - 0.1, 2)
            u2['clip']['expected'] = min(u2['clip']['expected'], avail)
        lay, sst = PAGE_LAYOUT[pid]
        pg['layout'] = lay
        if pg.get('splash'):
            pg['splashStyle'] = sst
        pages.append(pg)
    spec = {'title': 'Neon Dojo - comic mode, full song (DRAFT plan; art not generated yet)', 'draft': True,
            'outName': 'neon-dojo-comic', 'assetsDir': OUT, 'fps': 30, 'defaults': {'holdBeats': 1},
            'song': {'suno': 'ea6b85b9-efbb-40b4-83db-e9bb853f4122', 'audio': 'audio/song.m4a',
                     'audioNote': 'relative to assetsDir; not committed. Copy shots/neon-dojo-fighter/stage/assets/song.m4a there',
                     'timeline': 'shots/neon-dojo-fighter/stage/timeline.json', 'start': 0.0, 'end': END, 'loudness': -14},
            'short': {'start': DB[63], 'end': DB[89], 'note': 'boss reveal -> tag-team chorus -> bridge double super (~44 s)'},
            'cast': CAST, 'styleTemplate': STYLE, 'motionTemplate': MOTION, 'pages': pages}
    return spec, prompts, rows

def write_plan(spec, rows):
    L = ["# Neon Dojo - comic mode panel plan (draft)\n",
         f"Song: Neon Dojo (Suno ea6b85b9-efbb-40b4-83db-e9bb853f4122), {END:.1f} s, 143.55 BPM (beat ~0.42 s, bar ~1.67 s).",
         "Timeline/lyrics: `shots/neon-dojo-fighter/stage/timeline.json`. Spec: `shots/neon-dojo-comic/neon-dojo-comic-full.comic.json`.\n",
         f"{len(rows)} panels on {len(spec['pages'])} pages. Every panel is a different scene (location + camera + moment).",
         "Each clip starts one beat (~0.42 s) after its panel lands, then plays 3.5-6 s (expected lengths below already fit the page).",
         "Generate `panels/<id>.jpg` (16:9, no text) and `clips/<id>.mp4` (Grok Imagine i2v, 480p, 6 s) in `/workspace/neon-dojo-comic/`.",
         "Reference images: /workspace/webshots/channels/progressiveslop/assets/neon-dojo-fighter/source/ (Uno: cutins/uno.jpg, uno/idle_a.jpg; Aura: cutins/aura.jpg, aura/idle_a.jpg; SHOGUN: cutins/shogun.jpg; KAZE-9: kaze9/idle_a.jpg; RAIJIN: raijin/idle_a.jpg). TEKKO, LOTUS and Sensei are described in text.\n"]
    cur = None
    for pid, slot, u, f, dur in rows:
        if pid != cur:
            pg = next(p for p in spec['pages'] if p['id'] == pid)
            L.append(f"\n## {pid} - {pg['note']} ({pg['start']:.2f}-{pg['end']:.2f} s) - layout {pg['layout']}{' + ' + pg['splashStyle'] + ' splash' if pg.get('splashStyle') else ''}\n")
            cur = pid
        caps = '; '.join(f"{c['at']:.2f} s \"{c['text']}\"" for c in u['captions']) or '-'
        sfx = ', '.join(f"{s['text']} @ {s['at']:.2f} s" for s in u.get('sfx', [])) or '-'
        L += [f"### {u['id']} - {slot} - lands {u['at']:.2f} s, clip {next_beat(u['at']):.2f} s, expected {u['clip']['expected']:.1f} s",
              f"- Scene: {u['location']} / {u['camera']} / {u['moment']}", f"- Refs: {', '.join(u['refs'])}",
              f"- Captions: {caps}", f"- SFX: {sfx}", f"- Image prompt: {u['prompt']}", f"- Motion prompt: {u['motionPrompt']}\n"]
    open(f'{OUT}/plan.md', 'w').write('\n'.join(L))

if __name__ == '__main__':
    spec, prompts, rows = build()
    json.dump(spec, open(f'{REPO}/shots/neon-dojo-comic/neon-dojo-comic-full.comic.json', 'w'), indent=1, ensure_ascii=False)
    json.dump(prompts, open(f'{OUT}/prompts.json', 'w'), indent=1, ensure_ascii=False)
    open(f'{OUT}/motion.txt', 'w').write(''.join(f"{u['id']} | {u['motionPrompt']}\n" for _, _, u, _, _ in rows))
    write_plan(spec, rows)
    print(len(prompts), 'panels', max(words(p['prompt']) for p in prompts), 'max words')

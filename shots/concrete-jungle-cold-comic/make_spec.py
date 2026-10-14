#!/usr/bin/env python3
"""CONCRETE JUNGLE COLD (Progressive Slop, comic mode): storyboard beats -> concrete-jungle-cold-comic.comic.json
(+ timeline.json with the curated lyric lines). Media lives on the box in /workspace/crime-comic (panels/, clips/,
bg/, audio.mp3), not in git.

  python3 shots/concrete-jungle-cold-comic/make_spec.py

Clips: Grok Imagine clips are not generated yet, so every panel is a still with a renderer motion preset
(`stillMotion`). Drop a clip at /workspace/crime-comic/clips/fNN.mp4 (480p, 6 s) and re-run this builder: that
panel switches to {"clip": {"src": "clips/fNN.mp4", "in": 0, "out": <capped to the page>}} automatically.
"""
import bisect, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../..'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
ASSETS = '/workspace/crime-comic'
SRC_TL = json.load(open(os.path.join(ASSETS, 'timeline.json')))
B, END = SRC_TL['beats'], round(SRC_TL['duration'], 3)
def snap(t): return round(min(B, key=lambda b: abs(b - t)), 3)

L1 = 'Concrete jungle, cold, stories untold'
L2 = 'Diamonds in the rough, souls bought and sold'
L3 = "Concrete jungle, cold, watchin' it unfold"
L4 = 'Survival of the fittest, heart made of gold'
# (start, end, text) from timeline words; the aligner missed chorus 1 lines 3-4 (placed from a faster-whisper small
# pass with the lyrics as prompt: watchin@23.92..unfold@25.86, Survival@26.62..fittest@29.44, heart@30.02..gold@31.38).
# Ad-lib "Yeah"s are not lettered. Short rap bars are joined into couplets.
LINES = [
    (9.46, 15.04, L1), (16.06, 20.88, L2), (21.20, 25.90, L3), (26.62, 29.90, 'Survival of the fittest,'),
    (29.98, 31.53, 'heart made of gold'),
    (33.66, 36.21, "Peep the script, ain't no actor"), (36.26, 38.73, 'Wordsmith truth, no cap no factor'),
    (38.78, 41.77, 'City lights flicker, souls get sicker'), (41.82, 44.21, 'Hustle every minute, make it quicker'),
    (44.26, 49.08, L1), (49.84, 55.15, L2), (55.20, 60.85, L3), (60.90, 66.20, L4),
    (66.76, 69.67, 'Block to the booth, undeniable proof'), (69.72, 72.37, 'Struggle and the youth, pain in the proof'),
    (72.42, 75.81, 'Lost in the maze, caught in a daze'), (75.86, 78.31, 'Paper dreams, urban haze'),
    (78.36, 82.63, L3), (82.68, 88.64, 'Heart made of gold, in the cold'),
    (89.32, 92.43, 'Wisdom in the streets, deeper than the beats'), (92.48, 94.61, 'Scar is a map, no defeats'),
    (94.66, 97.90, "Pen is a weapon, words connectin'"), (98.06, 100.61, 'Soul resurrection, no deflection'),
    (100.66, 105.54, L1), (106.20, 111.24, L2), (111.70, 117.10, L3), (117.18, 122.04, L4),
    (123.14, 125.54, 'They dim the light, flame burns bright'), (126.12, 128.30, 'Darkest night, we still fight'),
    (128.32, 130.98, 'No surrender, break the fetter'), (131.08, 134.26, "Soul's true letter, we get better"),
    (134.28, 139.94, L1), (139.96, 145.52, L2), (145.54, 150.96, L3), (150.98, 156.44, L4),
    (156.68, 162.20, L1), (162.22, 167.94, L2), (167.96, 172.44, L3), (172.46, 177.95, L4),
    (179.94, 183.10, 'Concrete cold, spirit bold'), (184.80, 187.98, 'Heart made of gold, in the cold'),
    (189.40, 194.32, 'Concrete cold, but the spirit bold'),
]

# pages per the storyboard page plan; (id, start, end, layout, pageTransition, mood,
#   [(panel, slot, land, sfx, impact, entrance, stillMotion)], splash=(panel, at, sfx, impact, splashStyle, zoom-from))
PAGES = [
    ('p01', 0.0, 33.60, 'three', None, 'action',
     [('f01', 'a', 0.0, 'KRAKOOM!', True, 'fade', 'push_in'), ('f02', 'b', 9.46, 'SPLASH!', False, 'slide_left', 'drift_up'),
      ('f03', 'c', 16.06, 'CLINK!', False, 'iris', 'pan_right')],
     ('f04', 30.68, 'SHING!', True, 'full', 'f03')),
    ('p02', 33.60, 49.45, 'mixed-three', 'wipe_diag', 'action',
     [('f05', 'a', 33.66, 'SNAP!', False, 'slide_down', 'push_in'), ('f06', 'b', 38.78, 'WAH-WAH', False, 'fade', 'pan_left'),
      ('f07', 'c', 41.82, 'CHA-CHING!', True, 'whip', 'push_in')],
     ('f08', 44.26, 'HMPH!', False, 'breakout', 'f07')),
    ('p03', 49.45, 66.50, 'tilt-two', 'slide_up', 'action',
     [('f09', 'a', 49.84, 'THUNK!', False, 'slide_up', 'push_in'), ('f10', 'b', 60.90, 'SKREEEE!', True, 'whip', 'pan_right')],
     None),
    ('p04', 66.50, 88.95, 'four-grid', 'whip', 'action',
     [('f11', 'a', 66.76, 'WHAM!', True, 'zoom_pop', 'push_in'), ('f12', 'b', 72.42, 'ZZT-ZZT!', False, 'wipe', 'pan_left'),
      ('f13', 'c', 75.86, 'KA-CHUNK!', False, 'iris', 'push_in'), ('f14', 'd', 78.36, 'FWOOSH!', False, 'slide_right', 'pull_out')],
     ('f15', 83.38, 'KLANG!', True, 'tilt', 'f14')),
    ('p05', 88.95, 100.63, 'inset-two', 'iris', 'eerie',
     [('f16', 'a', 89.32, 'TIK-TIK-CLAK!', False, 'fade', 'push_in'), ('f17', 'b', 94.66, 'RRRING!', False, 'wipe', 'pan_right')],
     None),
    ('p06', 100.63, 122.90, 'slant-two', 'wipe_linear', 'action',
     [('f18', 'a', 100.66, 'WHOOOM!', True, 'zoom_pop', 'drift_up'), ('f19', 'b', 111.70, 'VROOOM!', False, 'slide_left', 'pan_left')],
     None),
    ('p07', 122.90, 134.27, 'tilt-two', 'flash', 'scare',
     [('f20', 'a', 123.00, 'POOF!', True, 'glitch', 'push_in'), ('f21', 'b', 128.32, 'BOOM!', True, 'whip', 'pull_out')],
     None),
    ('p08', 134.27, 156.56, 'three', 'slide_left', 'action',
     [('f22', 'a', 134.28, 'KRAK!', True, 'zoom_pop', 'push_in'), ('f23', 'b', 145.54, 'YOINK!', False, 'slide_right', 'pan_left'),
      ('f24', 'c', 150.98, 'SPIN-SPIN!', False, 'iris', 'push_in')],
     None),
    ('p09', 156.56, 184.40, 'side-two', 'crossfade', 'action',
     [('f25', 'a', 156.68, 'FLASH!', True, 'glitch', 'push_in'), ('f26', 'b', 179.94, 'TING!', False, 'fade', 'pull_out')],
     None),
    ('p10', 184.40, END, 'inset-two', 'fade_black', 'eerie',
     [('f27', 'a', 184.80, 'KSSHH...', False, 'wipe', 'push_in'), ('f28', 'b', 189.40, None, False, 'iris', 'push_in')],
     None),
]

# Focus regions (normalised [x0, y0, x1, y1] on the panel image), read off a 10% grid sheet of every panel:
# the storyboard "Focus" column (required) + other faces (required when they are a named lead, else nice-to-have).
def R(label, *box, req=True):
    return {'label': label, 'box': list(box), 'required': req}
FOCUS_REGIONS = {
 'f01': [R('skyline spire', 0.45, 0.10, 0.57, 0.55), R('lightning', 0.48, 0.0, 0.75, 0.30, req=False)],
 'f02': [R('Uno face', 0.27, 0.02, 0.40, 0.24), R('Aura face', 0.58, 0.02, 0.71, 0.24)],
 'f03': [R("Aura's reflection", 0.05, 0.30, 0.34, 0.68), R('Ferro face', 0.50, 0.10, 0.66, 0.38, req=False)],
 'f04': [R('grill + face', 0.32, 0.22, 0.58, 0.75), R('gold 1 chain', 0.74, 0.12, 0.92, 0.90)],
 'f05': [R('slot eyes', 0.13, 0.12, 0.28, 0.30), R('Uno lips', 0.32, 0.12, 0.55, 0.48), R('bouncer + Aura', 0.66, 0.05, 0.95, 0.45, req=False)],
 'f06': [R('Aura face', 0.31, 0.02, 0.42, 0.22), R('Ferro monocle', 0.76, 0.12, 0.92, 0.40)],
 'f07': [R('coin burst', 0.48, 0.48, 0.74, 0.92), R('Uno face', 0.07, 0.02, 0.28, 0.38, req=False), R('Ferro face', 0.69, 0.02, 0.81, 0.30, req=False)],
 'f08': [R('Ferro grin', 0.19, 0.02, 0.33, 0.30), R('Uno face', 0.47, 0.10, 0.62, 0.35, req=False), R('Slick Nickel', 0.72, 0.20, 0.83, 0.40, req=False)],
 'f09': [R('Uno + crate swing', 0.13, 0.08, 0.48, 0.82), R('Aura face', 0.76, 0.02, 0.86, 0.20, req=False)],
 'f10': [R('car grille', 0.56, 0.28, 0.76, 0.70)],
 'f11': [R('Uno grin', 0.27, 0.05, 0.42, 0.38), R('blueprint', 0.30, 0.70, 0.70, 0.90), R('Aura face', 0.60, 0.08, 0.73, 0.35, req=False)],
 'f12': [R('Aura face in lasers', 0.28, 0.15, 0.45, 0.42)],
 'f13': [R('Uno ear + face', 0.12, 0.05, 0.42, 0.55), R('vault dial', 0.62, 0.22, 0.84, 0.70)],
 'f14': [R('Aura face', 0.32, 0.12, 0.45, 0.35), R('Uno face', 0.62, 0.02, 0.78, 0.30)],
 'f15': [R('Nickel smirk', 0.18, 0.02, 0.36, 0.35), R('eyes behind the bars', 0.58, 0.35, 0.85, 0.55, req=False)],
 'f16': [R('hair strands in lock', 0.12, 0.22, 0.55, 0.75), R('Aura eye', 0.72, 0.22, 0.95, 0.50, req=False)],
 'f17': [R('Uno face', 0.28, 0.08, 0.50, 0.40), R('lit-up map', 0.52, 0.0, 0.95, 0.55, req=False)],
 'f18': [R('Uno face', 0.30, 0.04, 0.43, 0.26), R('Aura face', 0.60, 0.04, 0.72, 0.26), R('searchlight', 0.45, 0.30, 0.65, 0.90, req=False)],
 'f19': [R('car mid-leap', 0.29, 0.25, 0.72, 0.62), R('moon', 0.30, 0.05, 0.55, 0.35, req=False)],
 'f20': [R("Ferro's furious face", 0.28, 0.12, 0.46, 0.42), R('Nickel face', 0.78, 0.20, 0.92, 0.42, req=False)],
 'f21': [R('Uno face', 0.28, 0.0, 0.42, 0.18), R('Aura face', 0.58, 0.0, 0.72, 0.18)],
 'f22': [R('Uno eyes', 0.17, 0.02, 0.40, 0.40), R('Ferro eyes', 0.74, 0.22, 0.97, 0.58)],
 'f23': [R("Aura's smile", 0.12, 0.05, 0.30, 0.35), R('Nickel + hat', 0.50, 0.10, 0.85, 0.50, req=False)],
 'f24': [R('headline', 0.22, 0.12, 0.90, 0.45)],
 'f25': [R('Uno face', 0.31, 0.05, 0.48, 0.32), R('Aura face', 0.58, 0.05, 0.75, 0.35), R('gold 1 chain', 0.15, 0.0, 0.30, 0.45, req=False)],
 'f26': [R('hand on hat', 0.47, 0.06, 0.60, 0.28), R('glass', 0.74, 0.48, 0.88, 0.80), R('Uno face', 0.54, 0.18, 0.74, 0.52, req=False)],
 'f27': [R('envelope seal', 0.10, 0.25, 0.45, 0.70), R('Aura eyes', 0.42, 0.15, 0.66, 0.42)],
 'f28': [R('monocle glint', 0.22, 0.05, 0.38, 0.35), R('empty jail truck', 0.56, 0.30, 1.0, 0.90, req=False)],
}
SHORT = {'start': 128.30, 'end': 177.95,
         'note': 'word gap after "we still fight" -> warehouse doors BOOM, showdown, final chorus, newspaper, penthouse triumph; ends after the last "heart made of gold" (49.65 s)'}
CAPTION_FILLS = [[255, 226, 150], [240, 232, 214], [255, 190, 190], [214, 200, 255]]   # deco gold, ivory, crimson blush, lilac
SFX_COLORS = [[255, 200, 60], [230, 40, 60], [190, 120, 255], [255, 245, 230], [255, 150, 40]]
CLIP_LEN = 6.0
MOMENTS = {}
for l in open(os.path.join(HERE, 'storyboard.md')).read().splitlines():
    m = re.match(r'^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|', l)
    if m:
        MOMENTS[f'f{int(m.group(1)):02d}'] = {'moment': m.group(4).strip(), 'cast': m.group(5).strip(), 'focusNote': m.group(6).strip(),
                                             'storyTransition': m.group(7).strip()}


def up(s):
    return s.replace('\u2019', "'").upper()


def sfx_pos(fid):
    """Starburst spot: the candidate corner farthest from the panel's required focus regions."""
    req = [r['box'] for r in FOCUS_REGIONS.get(fid, []) if r['required']]
    cands = [([0.72, 0.30], -8), ([0.28, 0.30], 7), ([0.72, 0.70], 6), ([0.28, 0.70], -6)]
    def cost(c):
        (x, y), _ = c
        return sum(max(0, min(x + 0.14, b[2]) - max(x - 0.14, b[0])) * max(0, min(y + 0.12, b[3]) - max(y - 0.12, b[1])) for b in req)
    return min(cands, key=cost)


def next_beat(t, k=1):
    i = bisect.bisect_right(B, t + 0.05)
    return round(B[min(len(B) - 1, i + k - 1)], 3)


def unit(fid, land, sfx, impact, ent, motion, k, slot=None):
    u = {'id': fid, 'image': f'panels/{fid}.jpg', 'at': land, **MOMENTS.get(fid, {}), 'captions': [],
         'entrance': {'type': ent, 'dur': 0.3}}
    if slot:
        u['slot'] = slot
    clip = os.path.join(ASSETS, 'clips', f'{fid}.mp4')
    if os.path.exists(clip):
        u['clip'] = {'src': f'clips/{fid}.mp4', 'in': 0.0, 'out': CLIP_LEN}
    else:
        u['stillMotion'] = {'type': motion, 'amount': 0.05, 'dur': 6.0}
        u['clipPending'] = f'clips/{fid}.mp4'
    u['focusRegions'] = FOCUS_REGIONS.get(fid, [])
    u['shotKind'] = 'fx' if fid in ('f01', 'f24') else ('vehicle' if fid in ('f10', 'f19') else 'character')
    if fid not in ('f01', 'f10', 'f19', 'f24'):
        u['refs'] = ['/workspace/progressive-slop-refs/uno-locked.jpg', '/workspace/progressive-slop-refs/aura-locked.jpg']
    if sfx:
        pos, rot = sfx_pos(fid)
        u['sfx'] = [{'text': sfx, 'at': next_beat(land, 2), 'pos': pos, 'rot': rot, 'size': 0.15,
                     'color': SFX_COLORS[k % len(SFX_COLORS)], 'impact': impact}]
    return u


def build():
    tl = dict(SRC_TL)
    tl['lyrics'] = [{'t': s, 'end': e, 'text': x, 'words': [{'w': w, 't': round(s + (e - s) * 0.85 * i / max(1, len(x.split()) - 1), 2)}
                                                         for i, w in enumerate(x.split())]} for s, e, x in LINES]
    tl['lyricsNote'] = 'lines curated by make_spec.py (aligner + faster-whisper pass for chorus 1); word times inside a line are evenly spread'
    json.dump(tl, open(os.path.join(HERE, 'timeline.json'), 'w'))
    pages, k, n = [], 0, 0
    for pid, start, end, layout, ptr, mood, panels, splash in PAGES:
        out = {'id': pid, 'start': start, 'end': end, 'layout': layout, 'mood': mood, 'panels': []}
        if ptr:
            out['pageTransition'] = {'type': ptr, 'dur': 0.5}
        for j, (fid, slot, land, sfx, imp, ent, mot) in enumerate(panels):
            land = round(B[bisect.bisect_left(B, start - 0.03)], 3) if j == 0 and land <= start + 0.5 else snap(land)
            out['panels'].append(unit(fid, land, sfx, imp, ent, mot, k, slot)); k += 1
        sp_at = None
        if splash:
            fid, at, sfx, imp, style, frm = splash
            sp_at = snap(at)
            su = unit(fid, sp_at, sfx, imp, 'fade', 'push_in', k); k += 1
            su.pop('entrance'); su.pop('at')
            out['transition'] = {'type': 'zoom', 'panel': frm, 'at': sp_at, 'dur': round(sp_at - B[bisect.bisect_left(B, sp_at - 0.03) - 1], 3)}   # zoom starts on the previous beat
            out['splash'] = su
            out['splashStyle'] = style
        # lyric captions: on the latest panel landed by the line's first word, or on the splash after its zoom;
        # a line still being sung when the zoom lands is carried onto the splash
        caps = []
        for s, e, x in LINES:
            if not (start - 0.3 <= s < end - 0.2):
                continue
            c = {'text': up(x), 'anchor': 'tl', 'lyric': True, 'fill': CAPTION_FILLS[n % len(CAPTION_FILLS)]}
            n += 1
            if sp_at is not None and s >= sp_at - 0.1:
                c['at'] = sp_at if abs(snap(s) - sp_at) < 0.07 else max(snap(s), sp_at)
                out['splash']['captions'].append(c); caps.append((c, e, 'splash'))
                continue
            u = max((p for p in out['panels'] if p['at'] <= s + 0.4), key=lambda p: p['at'], default=out['panels'][0])
            c['at'] = round(max(snap(s), u['at']), 3)
            u['captions'].append(c); caps.append((c, e, u['id']))
            if sp_at is not None and e > sp_at:
                out['splash']['captions'].append(dict(c, at=sp_at))
        # each caption stays up until the first beat after its line is sung (then gives way); anchors alternate
        # tl/bl so a caption still finishing never collides with the next one
        for c, e, who in caps:
            ub = next((b for b in B if b >= e - 0.01), END)
            if ub < end - 0.05 and not (sp_at is not None and who != 'splash' and e > sp_at - 0.8):
                c['until'] = round(max(ub, c['at'] + 0.7), 3)
        for u in out['panels'] + ([out['splash']] if splash else []):
            for i, c in enumerate(u['captions']):
                c['anchor'] = ['bl', 'tl'][i % 2] if u['id'] in ('f02', 'f18', 'f21', 'f25') else ['tl', 'bl'][i % 2]
            if u.get('clip'):
                avail = round(end - next_beat(u.get('at', sp_at or start)) - 0.1, 2)
                if avail < CLIP_LEN - 0.01:
                    u['clip']['out'] = avail
                    u['clip']['trimNote'] = f'page turns at {end:.2f}s, clip capped to {avail}s'
        pages.append(out)
    spec = {'title': 'Concrete Jungle Cold - comic mode (Progressive Slop)', 'outName': 'concrete-jungle-cold', 'assetsDir': ASSETS, 'fps': 30,
            'defaults': {'holdBeats': 1}, 'mood': 'action', 'bgTheme': 'deco_gold', 'loop': True,
            'bg_video': {'landscape': 'bg/deco_gold-landscape.mp4', 'vertical': 'bg/deco_gold-vertical.mp4'},  # scripts/make_loop_bg.py --theme deco_gold
            'song': {'suno': '007325bb-143d-467d-90bc-cc25083181d6', 'audio': 'audio.mp3',
                     'audioNote': 'relative to assetsDir; not committed', 'timeline': 'shots/concrete-jungle-cold-comic/timeline.json',
                     'start': 0.0, 'end': END, 'loudness': -14},
            'short': SHORT,
            'intro': {'enabled': True, 'title': 'CONCRETE JUNGLE COLD', 'lines': ['CONCRETE', 'JUNGLE COLD'],
                      'subtitle': 'PROGRESSIVE SLOP PRESENTS', 'seconds': 2.6,
                      'glow': [255, 196, 70], 'glow2': [200, 20, 50],
                      'chrome': [[255, 250, 215], [255, 215, 110], [196, 140, 40], [90, 52, 8], [210, 160, 60], [255, 236, 170]],
                      'subColor': [255, 226, 150], 'rot': -3, 'dim': 0.5, 'sunburst': {'color': [230, 180, 70], 'alpha': 0.3}},
            'tbc': {'enabled': True, 'text': 'TO BE CONTINUED...', 'seconds': 2.5,
                    'style': {'style': 'plain', 'glow': [255, 196, 70], 'glow2': [200, 20, 50], 'subColor': [255, 226, 150],
                              'chrome': [[255, 250, 215], [255, 215, 110], [196, 140, 40], [90, 52, 8], [210, 160, 60], [255, 236, 170]]}},
            'endCard': {'enabled': True, 'seconds': 3.0, 'sunburst': {'color': [230, 180, 70], 'alpha': 0.6},
                        'fills': [[255, 214, 110], [255, 70, 90]],
                        'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!']},
            'pages': pages}
    spec['_dir'] = HERE
    for line in fix_layouts(spec):
        print('layout fix:', line)
    spec.pop('_dir')
    path = os.path.join(HERE, 'concrete-jungle-cold-comic.comic.json')
    json.dump(spec, open(path, 'w'), indent=1, ensure_ascii=False)
    print(os.path.relpath(path, REPO), sum(len(p['panels']) + bool(p.get('splash')) for p in pages), 'panels', len(pages), 'pages')


def fix_layouts(spec):
    """Scene-aware layout pass (as in shots/fright-night-comic/make_spec.py): when a page's crops cannot fit every
    required focus region, try every layout with the same panel count and every slot order; keep the fewest misses
    (16:9 and the Short weigh fully, vertical pages outside the Short count half), never repeating a neighbour's layout."""
    import itertools
    import comic_lib as C
    pages = spec['pages']; report = []
    s0, s1 = spec['short']['start'], spec['short']['end']
    def score(pg, layout, slots):
        sub = dict(spec, panels=[dict(u, slot=s) for u, s in zip(pg['panels'], slots)], layout=layout, page=pg['id'],
                   song=dict(spec['song'], start=pg['start'], end=pg['end']))
        in_short = {u['id'] for u in pg['panels'] if u['at'] < s1 and pg['end'] > s0}
        return round(sum(f for *_, f in C.page_focus_problems(spec, sub, 'landscape')) +
                     sum(f * (1.0 if uid in in_short else 0.3) for uid, *_, f in C.page_focus_problems(spec, sub, 'vertical')), 3)
    for i, pg in enumerate(pages):
        n = len(pg['panels'])
        orig = (pg['layout'], tuple(u['slot'] for u in pg['panels']))
        best = (score(pg, *orig), 0, orig)
        if best[0] > 0:
            for name, L in C.LAYOUTS.items():
                if L['n'] != n or (i and pages[i - 1]['layout'] == name) or (i + 1 < len(pages) and pages[i + 1]['layout'] == name):
                    continue
                for perm in itertools.permutations(sorted(L['slots'])):
                    sc = score(pg, name, perm)
                    if (sc, 1) < best[:2]:
                        best = (sc, 1, (name, perm))
        if best[2] != orig:
            report.append(f"{pg['id']}: {orig[0]} {''.join(orig[1])} -> {best[2][0]} {''.join(best[2][1])} (misses {score(pg, *orig)} -> {best[0]})")
            pg['layout'] = best[2][0]
            for u, sl in zip(pg['panels'], best[2][1]):
                u['slot'] = sl
        elif best[0] > 0:
            report.append(f"{pg['id']}: {orig[0]} kept, misses {best[0]}")
    return report


if __name__ == '__main__':
    build()

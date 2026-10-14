#!/usr/bin/env python3
"""FRIGHT NIGHT: storyboard beats -> renderable comic spec fright-night-comic.comic.json (+ timeline.json with the
manually placed lyric lines). Media lives on the box in /workspace/halloween-comic (panels/, clips/, audio.mp3), not in git.

  python3 shots/fright-night-comic/make_spec.py      # rebuild after changing TAKE / timings
Clip slots point at clips/<id>_<TAKE>.mp4 (all '_a' until the takes are reviewed); every clip is budgeted at the full 6 s.
"""
import bisect, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../..'))
ASSETS = '/workspace/halloween-comic'
SRC_TL = json.load(open(os.path.join(ASSETS, 'timeline.json')))      # analyze_music.py output (librosa + faster-whisper small)
B, END = SRC_TL['beats'], round(SRC_TL['duration'], 2)
def beat_le(t): return B[max(0, bisect.bisect_right(B, t + 1e-6) - 1)]

# Lyric lines. The aligner missed 6 lines (sung over the busy intro / chorus pickups); those were placed from a
# faster-whisper medium.en pass with the lyrics as prompt (word times in comments). Lines are (start, end, text).
LINES = [
    (3.70, 5.60, 'Fright night, fright night'),                                   # manual: Fright@3.70 night@5.06
    (9.82, 12.40, "It ain't my kind of night"),                                   # manual: It@9.82 .. night@11.76
    (13.68, 16.25, 'Deadbolt shaking, something scratching at the hall'),         # manual: Deadbolt@13.68 .. hall@16.16
    (16.28, 20.47, 'Mud on the carpet, hear them moving in the wall'),
    (20.74, 22.90, 'Fright night, fright night'),
    (22.96, 25.40, "I don't like what I just saw"),                               # manual: I@22.96 .. saw@24.98
    (25.48, 29.90, 'Bone-deep cold, got the air going thin'),                     # manual: Bone@25.48 .. thin@29.22
    (30.00, 32.24, "Figures in the hallway, and they're leaning in"),
    (33.60, 35.01, 'Fright night, fright night'),
    (35.06, 39.54, "I'm looking for the door"),
    (39.94, 42.71, 'Black cat screaming, clock stuck on three'),
    (42.76, 46.40, 'Every little shadow got a name for me'),
    (46.50, 48.77, 'Fright night, fright night'),
    (48.82, 52.88, 'This whole house feels wrong'),
    (53.00, 56.15, "Wolves on the roof and the graveyard's gone"),
    (56.20, 59.43, 'Storm at the window, doom keeps coming on'),
    (59.54, 61.85, 'Fright night, fright night'),
    (61.90, 65.25, 'I need out tonight'),
    (65.30, 69.05, 'Ghost in the mirror, and it just moved twice'),
    (69.10, 72.59, "End of the block, but it still don't feel nice"),
    (72.70, 75.76, 'Fright night, fright night'),
    (75.84, 78.33, 'No sleep till dawn'),
    (78.38, 82.23, "If the dead want in, they can't wait long"),
    (82.28, 86.06, "I hear 'em at the ceiling, and they're getting strong"),
    (86.28, 88.40, 'Fright night, fright night'),                                 # manual: Fright@86.28 .. night@87.68
    (89.16, 92.20, "It ain't right night"),                                       # manual: It@89.16 .. night@92.08
    (92.26, 95.25, 'When the doors start buckling and the candles die'),          # medium pass: When@92.26 (small model said 91.06)
    (95.30, 98.90, "I'm rapping through the panic till the sky goes shy"),
    (99.32, 101.40, 'Fright night, fright night'),                                # outro chorus (aligner: 99.32-101.86)
    (102.46, 106.00, 'Fright night, fright night'),
    (106.96, 111.30, 'Fright night, fright night'),                               # last word night@110.58
]

# pages: (id, start, end, layout, mood, [(panel id, slot, land target, sfx)])   boundaries sit in lyric gaps
PAGES = [
    ('p01', 0.00, 9.497, 'slant-two', None, [('f01', 'a', 0.0, None), ('f02', 'b', 2.95, 'SLAM!')]),
    ('p02', 9.497, 20.735, 'tilt-two', None, [('f03', 'a', 9.497, None), ('f04', 'b', 13.60, None)]),
    ('p03', 20.735, 32.299, 'three', None, [('f05', 'a', 20.735, None), ('f06', 'b', 23.00, None), ('f07', 'c', 25.40, None)]),
    ('p04', 32.299, 46.5, 'diagonal-three', None, [('f08', 'a', 32.299, None), ('f09', 'b', 36.50, None), ('f10', 'c', 39.88, None)]),
    ('p05', 46.5, 59.536, 'mixed-three', None, [('f11', 'a', 46.5, None), ('f12', 'b', 49.497, None), ('f13', 'c', 52.85, None)]),
    ('p06', 59.536, 72.64, 'inset-three', None, [('f14', 'a', 59.536, 'KRAK!'), ('f15', 'b', 62.60, 'FWOOSH!'), ('f16', 'c', 65.30, None)]),
    ('p07', 72.64, 86.216, 'tilt-three', 'action', [('f17', 'a', 72.64, None), ('f18', 'b', 75.80, 'SMASH!'), ('f19', 'c', 78.40, None)]),
    ('p08', 86.216, 99.335, 'diagonal-three', 'action', [('f20', 'a', 86.216, None), ('f21', 'b', 89.20, None), ('f22', 'c', 92.40, 'BOOM!')]),
    ('p09', 99.335, END, 'inset-three', 'eerie', [('f23', 'a', 99.335, None), ('f24', 'b', 102.40, None), ('f25', 'c', 106.00, None)]),
]
# 8 fps review 2026-10-13 (8-frame strips of all 50 takes): _a everywhere except
#   f02 -> b (the _a push-in drifts Aura's face toward human-looking at the end), f16 -> b (_a morphs Uno's dome into a red visor)
#   f06 -> a (the Leaners in _b multiply), f23 -> a (_b faces morph in the last second), f09 -> a (clock hands stay stuck on three)

# Focus regions (normalised [x0, y0, x1, y1] on the panel image): every face and the key action of each shot.
# Authored from a 10% grid sheet of the panels (auto eye-pair detection misses small/dim robot eyes here).
def R(label, *box, req=True):
    return {'label': label, 'box': list(box), 'required': req}
FOCUS_REGIONS = {
 'f01': [R('mansion + red windows', 0.28, 0.15, 0.68, 0.58)],
 'f02': [R('Uno face', 0.31, 0.15, 0.42, 0.33), R('Aura face', 0.48, 0.12, 0.57, 0.30)],
 'f03': [R('rattling deadbolt', 0.22, 0.22, 0.45, 0.62), R('scratch marks', 0.58, 0.15, 0.86, 0.58)],
 'f04': [R('Uno face', 0.32, 0.15, 0.48, 0.40), R('Aura', 0.75, 0.04, 0.86, 0.26), R('clawed prints', 0.30, 0.65, 0.75, 0.95, req=False)],
 'f05': [R('Aura eyes + face', 0.42, 0.12, 0.82, 0.72)],
 'f06': [R('Aura face', 0.40, 0.15, 0.50, 0.32), R('Uno face', 0.52, 0.30, 0.62, 0.48), R('Leaners', 0.0, 0.1, 1.0, 0.6, req=False)],
 'f07': [R('Uno face', 0.35, 0.04, 0.48, 0.22), R('Aura face', 0.55, 0.05, 0.65, 0.25), R('cyan magic', 0.70, 0.0, 0.88, 0.25)],
 'f08': [R('Uno', 0.44, 0.40, 0.52, 0.56), R('Aura', 0.53, 0.46, 0.60, 0.60)],
 'f09': [R('chrome cat', 0.50, 0.10, 0.78, 0.35), R('clock at three', 0.50, 0.35, 0.75, 0.66)],
 'f10': [R('Uno head', 0.27, 0.30, 0.36, 0.45), R('Aura head', 0.39, 0.30, 0.50, 0.48), R('shadow eyes', 0.55, 0.12, 0.90, 0.38)],
 'f11': [R('Aura', 0.48, 0.05, 0.60, 0.30), R('Uno face', 0.33, 0.45, 0.46, 0.65)],
 'f12': [R('chrome wolves', 0.05, 0.45, 0.42, 0.75), R('moon', 0.27, 0.05, 0.55, 0.48, req=False)],
 'f13': [R('Uno head', 0.10, 0.0, 0.28, 0.25), R('Aura head', 0.68, 0.05, 0.88, 0.35)],
 'f14': [R('wolf head', 0.40, 0.10, 0.60, 0.45), R('Uno face', 0.62, 0.10, 0.82, 0.45)],
 'f15': [R('Aura face', 0.18, 0.10, 0.30, 0.30), R('cyan blast', 0.45, 0.15, 0.80, 0.70)],
 'f16': [R('Uno face', 0.22, 0.0, 0.40, 0.35), R('Aura face', 0.62, 0.10, 0.78, 0.32)],
 'f17': [R('Aura face', 0.08, 0.10, 0.25, 0.35), R('mirror ghost', 0.45, 0.10, 0.75, 0.60)],
 'f18': [R('mirror ghost', 0.12, 0.0, 0.42, 0.55), R('fist + glass', 0.40, 0.25, 0.62, 0.55), R('Aura face', 0.76, 0.05, 1.0, 0.42)],
 'f19': [R('Uno face', 0.24, 0.15, 0.40, 0.40), R('Aura face', 0.55, 0.15, 0.68, 0.42)],
 'f20': [R('red eyes in the cracks', 0.30, 0.12, 0.75, 0.60)],
 'f21': [R('Uno eyes', 0.15, 0.45, 0.27, 0.60), R('Aura eyes', 0.77, 0.45, 0.90, 0.60)],
 'f22': [R('Uno face', 0.28, 0.05, 0.42, 0.30), R('door blast', 0.45, 0.15, 0.70, 0.60), R('Aura face', 0.73, 0.20, 0.88, 0.42)],
 'f23': [R('Uno face', 0.20, 0.20, 0.32, 0.45), R('Aura face', 0.40, 0.25, 0.52, 0.48)],
 'f24': [R('ghost in the window', 0.42, 0.15, 0.58, 0.45)],
 'f25': [R('both eyes (red -> green)', 0.22, 0.18, 0.80, 0.50)],
}
TAKE = {f'f{i:02d}': 'a' for i in range(1, 26)}
TAKE.update(f02='b', f16='b', f25='b')   # f25_b: red-start re-take, eyes turn green once at ~3.25 s (never *_greenstart)
F25_SHIFT = {'boxes': [[0.23, 0.22, 0.44, 0.46], [0.56, 0.21, 0.78, 0.44]], 'hold': 2.0, 'fade': 1.0, 'color': [110, 255, 160]}
FOCUS = {'f21': [0.27, 0.45]}   # diagonal centre slot: the panel centre is the dark corridor - keep Uno in the crop
CLIP_LEN = 6.0
SHORT = {'start': 72.64, 'end': END, 'note': 'chorus (Fright night / No sleep till dawn) -> mirror ghost SMASH -> ceiling -> doors buckle, BOOM escape -> sunrise -> ghost in the window -> cliffhanger, then TO BE CONTINUED + end card (~47 s)'}
CAPTION_FILLS = [[198, 236, 160], [232, 226, 204], [206, 188, 244], [255, 196, 120]]   # sickly green, bone, ghost violet, candle orange
SFX_STYLE = {'a': ([0.7, 0.32], -8), 'b': ([0.3, 0.3], 7), 'c': ([0.7, 0.35], -6)}
SFX_COLORS = [[150, 255, 90], [255, 70, 50], [190, 120, 255], [255, 170, 40], [255, 245, 230]]
MOMENTS = {}
for l in open(os.path.join(HERE, 'storyboard.md')).read().splitlines():
    m = re.match(r'^(\d+) (.*)', l)
    if m:
        MOMENTS[f'f{int(m.group(1)):02d}'] = m.group(2)
MOTION = dict(l.split(' | ', 1) for l in open(os.path.join(HERE, 'motion.txt')).read().splitlines() if ' | ' in l)


def up(s):
    return s.replace('’', "'").upper()


def build():
    tl = dict(SRC_TL)
    tl['lyrics'] = [{'t': s, 'end': e, 'text': x, 'words': [{'w': w, 't': round(s + (e - s) * 0.85 * k / max(1, len(x.split()) - 1), 2)}
                                                         for k, w in enumerate(x.split())]} for s, e, x in LINES]
    tl['lyricsNote'] = 'lines placed by make_spec.py (aligner + manual medium.en pass); word times inside a line are evenly spread'
    json.dump(tl, open(os.path.join(HERE, 'timeline.json'), 'w'))
    pages, k, n = [], 0, 0
    for pid, start, end, layout, mood, panels in PAGES:
        out = {'id': pid, 'start': start, 'end': end, 'layout': layout, 'panels': []}
        if mood:
            out['mood'] = mood
        for j, (fid, slot, land, sfx) in enumerate(panels):
            land = round(B[bisect.bisect_left(B, start - 0.03)], 3) if j == 0 else round(min(B, key=lambda b: abs(b - land)), 3)   # first panel lands on the first beat of the page
            u = {'id': fid, 'slot': slot, 'image': f'panels/{fid}.jpg', 'at': land, 'moment': MOMENTS.get(fid, ''),
                 'motionPrompt': MOTION.get(fid, ''), 'captions': [],
                 'clip': {'src': f'clips/{fid}_{TAKE[fid]}.mp4', 'in': 0.0, 'out': CLIP_LEN}}
            if fid == 'f25' and not os.path.exists(os.path.join(ASSETS, u['clip']['src'])):
                # red-start f25 clips not delivered yet: the red-eyed still with a renderer-side eye crossfade
                # (hold red 2 s, fade to ghost-green over 1 s, hold green) - red -> green exactly once
                del u['clip']
                u['eyeShift'] = F25_SHIFT
            u['focusRegions'] = FOCUS_REGIONS.get(fid, [])
            if fid in FOCUS:
                u['focus'] = FOCUS[fid]
            if sfx:
                pos, rot = SFX_STYLE[slot]
                at = B[bisect.bisect_right(B, land + 0.05) + 1]
                u['sfx'] = [{'text': sfx, 'at': round(at, 3), 'pos': pos, 'rot': rot, 'size': 0.17,
                             'color': SFX_COLORS[k % len(SFX_COLORS)], 'impact': True}]
                k += 1
            out['panels'].append(u)
        # lyric captions: each line on the latest panel landed by its first word (one caption per line per page)
        caps = []
        for s, e, x in LINES:
            if start - 0.3 <= s < end - 0.2:
                u = max((p for p in out['panels'] if p['at'] <= s + 0.3), key=lambda p: p['at'], default=out['panels'][0])
                c = {'text': up(x), 'anchor': 'tl', 'at': round(max(min(B, key=lambda b: abs(b - s)), u['at']), 3), 'lyric': True,
                     'fill': CAPTION_FILLS[n % len(CAPTION_FILLS)], '_end': e}
                n += 1
                u['captions'].append(c); caps.append(c)
        # a finished line gives way to the next (page-wide, so a repeated chorus line never shows twice at once)
        for a, b in zip(caps, caps[1:]):
            if a['_end'] <= b['at'] + 0.05:
                a['until'] = b['at']
        for u in out['panels']:
            for i, c in enumerate(u['captions']):
                c['anchor'] = ['tl', 'bl'][i % 2]
                c.pop('_end')
            cs = C_start(u)
            avail = round(end - cs - 0.1, 2)
            if avail < CLIP_LEN - 0.01:
                u['clip']['out'] = avail
                u['clip']['trimNote'] = f'page turns at {end:.2f}s, clip capped to {avail}s'
        pages.append(out)
    spec = {'title': 'Fright Night - comic mode (Progressive Slop)', 'outName': 'fright-night-comic', 'assetsDir': ASSETS, 'fps': 30,
            'defaults': {'holdBeats': 1}, 'mood': 'eerie', 'bgTheme': 'blinking_eyes', 'loop': True,
            'bg_video': {'landscape': 'bg/eyes-landscape.mp4', 'vertical': 'bg/eyes-vertical.mp4'},  # scripts/make_loop_bg.py --theme blinking_eyes
            'song': {'suno': '6ad72320-98e4-4b59-8575-fdc8b96b2005', 'audio': 'audio.mp3',
                     'audioNote': 'relative to assetsDir; not committed', 'timeline': 'shots/fright-night-comic/timeline.json',
                     'start': 0.0, 'end': END, 'loudness': -14},
            'short': SHORT,
            'intro': {'enabled': True, 'title': 'FRIGHT NIGHT', 'subtitle': 'PROGRESSIVE SLOP PRESENTS', 'seconds': 2.6,
                      'style': 'drip', 'lightning': True, 'glow': [120, 255, 90], 'glow2': [150, 40, 220],
                      'chrome': [[235, 255, 210], [170, 230, 120], [90, 150, 60], [20, 40, 18], [120, 190, 80], [215, 250, 180]],
                      'subColor': [200, 255, 170], 'rot': -3, 'dim': 0.6},
            'tbc': {'enabled': True, 'text': 'TO BE CONTINUED...', 'seconds': 2.5},
            'endCard': {'enabled': True, 'seconds': 3.0, 'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!']},
            'pages': pages}
    spec['_dir'] = HERE
    for line in fix_layouts(spec):
        print('layout fix:', line)
    spec.pop('_dir')
    path = os.path.join(HERE, 'fright-night-comic.comic.json')
    json.dump(spec, open(path, 'w'), indent=1, ensure_ascii=False)
    print(os.path.relpath(path, REPO), sum(len(p['panels']) for p in pages), 'panels', len(pages), 'pages')


def fix_layouts(spec):
    """Scene-aware layout pass: when a page's crops cannot fit every required focus region (both orientations),
    try the other layouts with the same panel count and every slot order; keep the one with the fewest misses
    (original wins ties), never repeating the neighbouring pages' layouts."""
    import itertools
    sys.path.insert(0, os.path.join(REPO, 'scripts'))
    import comic_lib as C
    pages = spec['pages']
    report = []
    def score(pg, layout, slots):
        sub = dict(spec, panels=[dict(u, slot=s) for u, s in zip(pg['panels'], slots)], layout=layout, page=pg['id'],
                   song=dict(spec['song'], start=pg['start'], end=pg['end']))
        pr = C.page_focus_problems(spec, sub, 'landscape') + C.page_focus_problems(spec, sub, 'vertical')
        return round(sum(f for *_, f in pr), 3), pr
    for i, pg in enumerate(pages):
        n = len(pg['panels'])
        orig = (pg['layout'], tuple(u['slot'] for u in pg['panels']))
        best = (score(pg, *orig)[0], 0, orig)
        if best[0] > 0:
            for name, L in C.LAYOUTS.items():
                if L['n'] != n or (i and pages[i - 1]['layout'] == name) or (i + 1 < len(pages) and pages[i + 1]['layout'] == name):
                    continue
                for perm in itertools.permutations(sorted(L['slots'])):
                    sc = score(pg, name, perm)[0]
                    if (sc, 1) < best[:2]:
                        best = (sc, 1, (name, perm))
        if best[2] != orig:
            report.append(f"{pg['id']}: {orig[0]} {''.join(orig[1])} -> {best[2][0]} {''.join(best[2][1])} (focus misses {score(pg, *orig)[0]} -> {best[0]})")
            pg['layout'] = best[2][0]
            for u, sl in zip(pg['panels'], best[2][1]):
                u['slot'] = sl
    return report


def C_start(u):
    return B[bisect.bisect_right(B, u['at'] + 0.05)]


if __name__ == '__main__':
    build()

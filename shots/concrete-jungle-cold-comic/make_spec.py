#!/usr/bin/env python3
"""CONCRETE JUNGLE COLD (Progressive Slop, comic mode): storyboard beats -> concrete-jungle-cold-comic.comic.json
(+ timeline.json with the curated lyric lines). Media lives on the box in /workspace/crime-comic (panels/, clips/,
bg/, audio.mp3), not in git.

  python3 shots/concrete-jungle-cold-comic/make_spec.py

Clips: Grok Imagine clips are not generated yet, so every panel is a still with a renderer motion preset
(`stillMotion`). Drop a clip at /workspace/crime-comic/clips/fNN.mp4 (480p, 6 s) and re-run this builder: that
panel switches (with CJC_CLIPS=1) to {"clip": {"src": "clips/fNN.mp4", "in": 0, "out": <capped to the page>}} automatically.
"""
import bisect, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../..'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
ASSETS = '/workspace/crime-comic'
LYRIC_OVERLAY = True
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
     [('f09', 'a', 49.84, 'THUNK!', False, 'slide_up', 'push_in'), ('f10', 'b', 53.33, 'SKREEEE!', True, 'whip', 'pan_right')],
     None),
    ('p04', 66.50, 82.68, 'four-grid', 'whip', 'action',
     [('f11', 'a', 66.76, 'WHAM!', True, 'zoom_pop', 'push_in'), ('f12', 'b', 67.46, 'ZZT-ZZT!', False, 'wipe', 'pan_left'),
      ('f13', 'c', 68.15, 'KA-CHUNK!', False, 'iris', 'push_in'), ('f15a', 'd', 68.85, None, False, 'slide_right', 'pan_right')],
     None),
    # v5: the betrayal gets its own page: Nickel at the vault door (new clip), then the bars slam (payoff)
    ('p04b', 82.68, 88.95, 'tilt-two', 'crossfade', 'scare',
     [('f15c', 'a', 82.68, None, False, 'glitch', 'push_in'), ('f15', 'b', 84.78, 'KLANG!', True, 'zoom_pop', 'push_in')],
     None),
    ('p05', 88.95, 100.63, 'inset-two', 'iris', 'eerie',
     [('f16', 'a', 89.32, 'TIK-TIK-CLAK!', False, 'fade', 'push_in'), ('f17', 'b', 94.66, 'RRRING!', False, 'wipe', 'pan_right')],
     None),
    ('p06', 100.63, 122.90, 'slant-two', 'wipe_linear', 'action',
     [('f18', 'a', 100.66, 'WHOOOM!', True, 'zoom_pop', 'drift_up'), ('f19', 'b', 105.53, 'VROOOM!', False, 'slide_left', 'pan_left')],
     None),
    ('p07', 122.90, 134.27, 'tilt-two', 'flash', 'scare',
     [('f20', 'a', 123.00, 'POOF!', True, 'glitch', 'push_in'), ('f21', 'b', 128.32, 'BOOM!', True, 'whip', 'pull_out')],
     None),
    # v5 sequence S2 (showdown): shoes square off, Uno's eyes flare, Ferro's monocle glints (insets), the hat flies
    # (big panel under the strip) -> full-frame payoff f22 (splash zoom out of the hat panel)
    ('p08', 134.27, 142.30, 'seq-four', 'slide_left', 'action',
     [('f22a', 'a', 134.28, None, False, 'slide_down', 'pan_right'), ('f22b', 'b', 134.63, None, False, 'slide_left', 'push_in'),
      ('f22c', 'c', 134.98, None, False, 'slide_right', 'push_in'), ('f22d', 'd', 135.33, None, False, 'zoom_pop', 'drift_up')],
     ('f22', 136.37, 'KRAK!', True, 'full', 'f22d')),
    # v5 sequence S3 (the catch): Nickel's feet run, Aura waits under the lamp, the bowler tumbles, sirens sweep the
    # alley (4 insets along the bottom) -> payoff f23 (clip f23_new: Aura with the hat, Nickel slumped at the lamp post)
    ('p08b', 142.30, 156.56, 'seq-five-low', 'whip', 'action',
     [('f23a', 'a', 142.33, None, False, 'slide_up', 'pan_left'), ('f23b', 'b', 142.68, None, False, 'iris', 'push_in'),
      ('f23c', 'c', 143.03, None, False, 'slide_up', 'drift_up'), ('f23d', 'd', 143.38, None, False, 'wipe', 'pan_right'),
      ('f23', 'e', 143.72, 'YOINK!', False, 'zoom_pop', 'push_in')],
     ('f24', 150.98, 'SPIN-SPIN!', False, 'tilt', 'f23')),
    # living panels: the triumph splash f25 holds the whole frame (16:9 and Short) until the toast f26 joins it
    ('p09', 156.56, 184.40, 'inset-two', 'crossfade', 'action',
     [('f25', 'a', 156.68, 'FLASH!', True, 'glitch', 'push_in'), ('f26', 'b', 179.94, 'TING!', False, 'fade', 'pull_out')],
     None),
    ('p10', 184.40, END, 'inset-two', 'fade_black', 'eerie',
     [('f27', 'a', 184.80, 'KSSHH...', False, 'wipe', 'push_in'), ('f28', 'b', 189.40, None, False, 'iris', 'push_in')],
     None),
]

# Focus regions (normalised [x0, y0, x1, y1] on the panel image), read off a 10% grid sheet of every panel:
# the storyboard "Focus" column (required) + other faces (required when they are a named lead, else nice-to-have).
def R(label, *box, req=True):
    r = {'label': label, 'box': list(box), 'required': req}
    if any(k in label.lower().replace('headline', '').split() for k in ('face', 'grin', 'smirk', 'eyes', 'eye', 'lips', 'reflection', 'monocle', 'grill', 'ear', 'nickel', 'head')):
        r['face'] = True
    return r
# extra face-only boxes (not required): every character visible in a panel, so captions / SFX can steer clear
FACES = {
 'f04': [R('Uno face', 0.30, 0.15, 0.62, 0.80, req=False)],
 'f07': [R('middle face', 0.37, 0.0, 0.49, 0.22, req=False)],
 'f09': [R('Uno face', 0.27, 0.08, 0.40, 0.32, req=False)],
 'f13': [R('Uno face', 0.10, 0.02, 0.40, 0.50, req=False)],
 'f20': [R('Ferro face', 0.25, 0.05, 0.48, 0.45, req=False)],
 'f23': [R('Nickel face', 0.69, 0.10, 0.83, 0.32, req=False)],
 'f26': [R('Aura face', 0.25, 0.0, 0.42, 0.25, req=False)],
 'f05': [R('Aura face', 0.66, 0.20, 0.80, 0.45, req=False), R('bouncer face', 0.80, 0.05, 0.95, 0.35, req=False)],
}
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
 'f11': [R('Uno grin', 0.29, 0.10, 0.41, 0.36), R('blueprint', 0.30, 0.70, 0.70, 0.90), R('Aura face', 0.60, 0.08, 0.73, 0.35, req=False)],
 'f12': [R('Aura face in lasers', 0.28, 0.15, 0.45, 0.42)],
 'f13': [R('Uno ear + face', 0.12, 0.05, 0.42, 0.55), R('vault dial', 0.62, 0.22, 0.84, 0.70)],
 'f14': [R('Aura face', 0.32, 0.12, 0.45, 0.35), R('Uno face', 0.62, 0.02, 0.78, 0.30)],
 'f15': [R('Nickel smirk', 0.18, 0.02, 0.36, 0.35), R('eyes behind the bars', 0.58, 0.35, 0.85, 0.55, req=False)],
 'f16': [R('hair strands in lock', 0.12, 0.22, 0.55, 0.75), R('Aura eye', 0.72, 0.22, 0.95, 0.50, req=False)],
 'f17': [R('Uno face', 0.28, 0.08, 0.50, 0.40), R('lit-up map', 0.52, 0.0, 0.95, 0.55, req=False)],
 'f18': [R('Uno face', 0.30, 0.04, 0.43, 0.26), R('Aura face', 0.60, 0.04, 0.72, 0.26), R('searchlight', 0.45, 0.30, 0.65, 0.90, req=False)],
 'f19': [R('car mid-leap', 0.29, 0.25, 0.72, 0.62), R('moon', 0.30, 0.05, 0.55, 0.35, req=False)],
 'f20': [R("Ferro's furious face", 0.28, 0.12, 0.46, 0.42), R('Nickel face', 0.78, 0.20, 0.92, 0.42, req=False)],
 'f21': [R('Uno face + headphones', 0.32, 0.0, 0.42, 0.19), R('Aura face', 0.62, 0.0, 0.71, 0.17),  # redraw 07:51
         R('Uno + Aura stride', 0.18, 0.0, 0.78, 0.97, req=False)],
 'f22': [R('Uno eyes', 0.17, 0.02, 0.40, 0.40), R('Ferro eyes', 0.74, 0.22, 0.97, 0.58)],
 'f23': [R("Aura's smile", 0.12, 0.05, 0.30, 0.35), R('Nickel + hat', 0.50, 0.10, 0.85, 0.50, req=False)],
 'f24': [R('headline', 0.22, 0.12, 0.90, 0.45)],
 'f25': [R('Uno face', 0.31, 0.05, 0.48, 0.32), R('Aura face', 0.58, 0.05, 0.75, 0.35), R('gold 1 chain', 0.15, 0.0, 0.30, 0.45, req=False)],
 'f26': [R('hand on hat', 0.47, 0.06, 0.60, 0.28), R('glass', 0.74, 0.48, 0.88, 0.80), R('Uno face', 0.54, 0.18, 0.74, 0.52, req=False)],
 'f27': [R('envelope seal', 0.10, 0.25, 0.45, 0.70), R('Aura eyes', 0.46, 0.10, 0.64, 0.30)],
 'f28': [R('monocle glint', 0.22, 0.05, 0.38, 0.35), R('empty jail truck', 0.56, 0.30, 1.0, 0.90, req=False)],
}
SHORT = {'start': 128.30, 'end': 177.95,
         # teaser/trailer (Jason 2026-10-14): glimpses from every act over the final-chorus audio, no betrayal payoff
         # (f15 slam, f20 swap, f22/f23 takedowns, f24 headline) and no ending (f28); cuts on the window's beats
         # native 9:16 glimpses: [song_t, beats, cells top->bottom] built from source clips (vshot.py)
         'trailer': [[2.0, 8, [{"id": "f01", "fx": 0.51}, {"id": "n01", "fx": 0.5}]], [11.0, 4, [{"id": "f02", "fx": 0.5}, {"id": "n05", "fx": 0.5}]], [31.2, 3, [{"id": "f04", "fx": 0.5}, {"id": "n02", "fx": 0.5}]], [45.5, 5, [{"id": "f08", "fx": 0.5}, {"id": "f07", "fx": 0.62}]], [54.5, 4, [{"id": "f09", "fx": 0.47}, {"id": "n29", "fx": 0.5}]], [70.0, 8, [{"id": "f11", "fx": 0.53}, {"id": "f12", "fx": 0.45}]], [76.0, 4, [{"id": "f14", "fx": 0.51}, {"id": "n11", "fx": 0.5}]], [83.0, 2, [{"id": "f15c", "fx": 0.4}, {"id": "f13", "fx": 0.45}]], [96.5, 4, [{"id": "f17", "fx": 0.44}, {"id": "f16", "fx": 0.4}]], [107.0, 6, [{"id": "f18", "fx": 0.57}, {"id": "f19", "fx": 0.5}]], [134.3, 2, [{"id": "f22b", "fx": 0.4}, {"id": "f22c", "fx": 0.48}]], [158.0, 8, [{"id": "f25", "fx": 0.5}, {"id": "n22", "fx": 0.5}]], [168.5, 4, [{"id": "n23", "fx": 0.39}, {"id": "n24", "fx": 0.46}]], [180.5, 4, [{"id": "f26", "fx": 0.47}, {"id": "n25", "fx": 0.5}]], [185.6, 0, [{"id": "f27", "fx": 0.64}, {"id": "n26", "fx": 0.55}]]],
         'note': 'word gap after "we still fight" -> warehouse doors BOOM, showdown, final chorus, newspaper, penthouse triumph; ends after the last "heart made of gold" (49.65 s)'}
CAPTION_FILLS = [[255, 226, 150], [240, 232, 214], [255, 190, 190], [214, 200, 255]]   # deco gold, ivory, crimson blush, lilac
SFX_COLORS = [[255, 200, 60], [230, 40, 60], [190, 120, 255], [255, 245, 230], [255, 150, 40]]
CLIP_LEN = 6.0
# v5 (2026-10-14): new clips in clips/v5 (never *_take1); unit id -> clip file when it differs from clips/v5/<id>.mp4
CLIP_SRC = {'f23': 'clips/v5/f23_new.mp4', 'f23x': 'clips/v5/f23.mp4'}
UNIT_IMAGE = {'f23': 'panels/f23_new.jpg', 'f23x': 'panels/f23.jpg'}
# sequence lead-up sub-panels with no clip: gentle pan/zoom of the still (allowed only as sequence insets)
NO_CLIP = {'f15a', 'f22a', 'f22d', 'f23a', 'f23c', 'f23d'}
def clip_rel(fid):
    if fid in NO_CLIP:
        return None
    for rel in (CLIP_SRC.get(fid), f'clips/v5/{fid}.mp4', f'clips/{fid}.mp4'):
        if rel and os.path.exists(os.path.join(ASSETS, rel)):
            return rel
    return None
# Clip review (2026-10-14, 1 fps strips + first-frame match). DROP: no clip until a keepable take lands.
DROP_CLIPS = {}  # f21 new take approved 2026-10-14 09:27
TRIMS_V4 = {'f04': (2.25, 'face drifts to a pale skull look from ~2.75 s (low-angle mask); cut 0.5 s before'),
         'f05': (3.25, 'hard reframe / new figure at ~3.75 s, Uno skull-like from ~5.25 s; cut 0.5 s before the break'),
         'f13': (4.0, 'from ~4.5 s the gold flare washes Uno\'s face toward a bright skull look; ends before it')}
# Clip-start stills: when a clip's first frame does not register on its panel (NCC < 0.75), the panel still is
# replaced by the clip's first frame (Lanczos 2x-ish upscale to 1280x720 + light unsharp), saved as
# panels/fNN_clipstart.jpg, so the still->clip handoff is seamless. Focus regions re-derived on those stills.
CLIPSTART_FOCUS = {
 'f02': [R('Uno face', 0.25, 0.08, 0.42, 0.28), R('Aura face', 0.58, 0.08, 0.75, 0.28)],
 'f08': [R('Ferro grin', 0.12, 0.08, 0.32, 0.35), R('Uno face', 0.42, 0.15, 0.58, 0.40, req=False), R('Nickel face', 0.65, 0.15, 0.80, 0.40, req=False)],
 'f09': [R('Uno + crate swing', 0.15, 0.25, 0.50, 0.85), R('Uno face', 0.28, 0.25, 0.42, 0.42, req=False), R('Aura face', 0.68, 0.05, 0.82, 0.22, req=False)],
 'f12': [R('Aura face in lasers', 0.38, 0.30, 0.58, 0.55)],
 'f13': [R('Uno ear + face', 0.18, 0.02, 0.45, 0.42), R('vault dial', 0.62, 0.40, 0.85, 0.75)],
 'f22': [R('Uno face', 0.05, 0.02, 0.32, 0.30), R('Nickel eyes', 0.52, 0.05, 0.75, 0.42)],
 'f23': [R("Aura's smile", 0.10, 0.08, 0.38, 0.45), R('Nickel face', 0.62, 0.18, 0.85, 0.45, req=False)],
 'f25': [R('Uno face', 0.34, 0.10, 0.49, 0.32), R('Aura face', 0.57, 0.10, 0.73, 0.36), R('gold 1 chain', 0.20, 0.18, 0.30, 0.67, req=False)],
}
CLIPSTART_FOCUS.update({
 'f03': [R("Aura's reflection", 0.26, 0.12, 0.56, 0.58), R('diamond crate', 0.58, 0.52, 0.92, 0.88, req=False)],
 'f04': [R('Uno face', 0.36, 0.0, 0.68, 0.56), R('gold 1 chain', 0.33, 0.48, 0.67, 0.92, req=False)],
 'f05': [R('slot eyes', 0.16, 0.18, 0.37, 0.42), R('Uno face', 0.46, 0.08, 0.64, 0.42), R('bouncer', 0.68, 0.0, 0.92, 0.42, req=False)],
 'f06': [R('Aura face', 0.28, 0.12, 0.47, 0.42)],
 'f11': [R('Uno face', 0.23, 0.0, 0.42, 0.32), R('Aura face', 0.58, 0.0, 0.77, 0.32), R('blueprint', 0.30, 0.68, 0.76, 1.0, req=False)],
 'f14': [R('Aura face', 0.28, 0.08, 0.47, 0.37), R('Uno face', 0.56, 0.0, 0.75, 0.32)],
 'f15': [R('Nickel face', 0.23, 0.08, 0.42, 0.42), R('brass key', 0.23, 0.53, 0.42, 0.82, req=False)],
 'f16': [R('hair strands in lock', 0.30, 0.22, 0.70, 0.80)],
 'f20': [R("Ferro's furious face", 0.18, 0.03, 0.47, 0.47), R('Nickel face', 0.68, 0.13, 0.90, 0.47, req=False)],
 'f21': [R('light seam between the doors', 0.42, 0.25, 0.58, 0.75)],
 'f26': [R('Aura face', 0.28, 0.0, 0.47, 0.32), R('Uno face', 0.50, 0.0, 0.68, 0.37), R('soda glass', 0.33, 0.73, 0.52, 1.0, req=False)],
 'f27': [R('Aura face', 0.40, 0.0, 0.60, 0.32), R('envelope seal', 0.23, 0.48, 0.47, 0.82)],
})
TRIMS = {'f21': (2.5, 'v5 clip pushes in on the pair; feet leave the cell from ~3 s, so it ends (and ping-pongs) before that'), 'f28': (4.0, 'v5 clip pushes in until Ferro fills the frame; keep the first 4 s so the full figure stays in')}
# v5 focus regions, read off a 10% grid sheet of the v5 panel art (the v5 clips' start images)
V5_FOCUS = {
 'f02': [R('Uno face', 0.29, 0.0, 0.42, 0.17), R('Aura face', 0.60, 0.08, 0.72, 0.26)],
 'f04': [R('Uno face', 0.52, 0.0, 0.82, 0.60), R('gold 1 chain', 0.38, 0.25, 0.62, 0.75, req=False)],
 'f05': [R('slot eyes', 0.08, 0.18, 0.25, 0.42), R('Uno face', 0.30, 0.05, 0.52, 0.42), R('Aura face', 0.62, 0.05, 0.80, 0.38)],
 'f06': [R('Aura face', 0.52, 0.08, 0.66, 0.35), R('Ferro face', 0.88, 0.30, 0.98, 0.50, req=False)],
 'f07': [R('Uno face', 0.52, 0.04, 0.66, 0.30), R('cards', 0.68, 0.15, 0.86, 0.45), R('coins', 0.20, 0.70, 0.45, 1.0, req=False)],
 'f08': [R('Ferro face', 0.28, 0.0, 0.48, 0.32), R('Nickel face', 0.52, 0.0, 0.68, 0.35, req=False), R('Uno face', 0.72, 0.0, 0.92, 0.35)],
 'f09': [R('Uno face', 0.25, 0.0, 0.40, 0.20), R('Aura face', 0.57, 0.12, 0.69, 0.30)],
 'f11': [R('Uno face', 0.45, 0.0, 0.62, 0.25), R('blueprint', 0.25, 0.65, 0.85, 1.0, req=False)],
 'f12': [R('Aura face in lasers', 0.38, 0.08, 0.52, 0.30)],
 'f13': [R('Uno face', 0.35, 0.0, 0.55, 0.30), R('vault dial', 0.62, 0.25, 0.90, 0.75, req=False)],
 'f14': [R('Uno face', 0.27, 0.0, 0.45, 0.25), R('Aura face', 0.60, 0.08, 0.75, 0.32)],
 'f15c': [R('Nickel face', 0.31, 0.04, 0.42, 0.20), R('Nickel figure', 0.20, 0.0, 0.50, 0.98, req=False)],
 'f16': [R('Aura face', 0.25, 0.05, 0.55, 0.55), R('lock', 0.60, 0.20, 0.95, 0.80, req=False)],
 'f17': [R('Uno face', 0.35, 0.0, 0.53, 0.32)],
 'f18': [R('Uno face', 0.43, 0.06, 0.55, 0.26), R('Aura face', 0.60, 0.12, 0.70, 0.30)],
 'f20': [R('Ferro face', 0.37, 0.0, 0.60, 0.40), R('confetti', 0.60, 0.10, 0.85, 0.80, req=False)],
 'f21': [R('Uno face', 0.38, 0.14, 0.47, 0.30), R('Aura face', 0.55, 0.16, 0.64, 0.32), R('Uno + Aura full figures', 0.34, 0.12, 0.66, 0.93)],
 'f22': [R('Uno face', 0.52, 0.02, 0.68, 0.25), R('Ferro head', 0.05, 0.52, 0.25, 0.75), R('Uno figure', 0.45, 0.0, 0.75, 0.75, req=False)],
 'f22b': [R('Uno face', 0.35, 0.08, 0.46, 0.22)],
 'f22c': [R('Ferro face', 0.43, 0.08, 0.54, 0.26)],
 'f23': [R('Aura face', 0.32, 0.04, 0.40, 0.14), R('Nickel face', 0.60, 0.28, 0.75, 0.50), R('bowler hat', 0.25, 0.60, 0.40, 0.85, req=False)],
 'f23x': [R('Aura face', 0.22, 0.05, 0.38, 0.30), R('Nickel face', 0.74, 0.38, 0.86, 0.55, req=False), R('bowler hat', 0.08, 0.12, 0.22, 0.35, req=False)],
 'f23b': [R('Aura face', 0.36, 0.08, 0.53, 0.36)],
 'f25': [R('Uno face', 0.28, 0.08, 0.45, 0.35), R('Aura face', 0.58, 0.12, 0.73, 0.38), R('gold 1 chain fist', 0.05, 0.0, 0.25, 0.45, req=False)],
 'f26': [R('Uno face', 0.19, 0.04, 0.34, 0.27), R('Aura face', 0.60, 0.05, 0.75, 0.32), R('glasses', 0.40, 0.15, 0.60, 0.40, req=False)],
 'f27': [R('Aura face', 0.55, 0.05, 0.78, 0.40), R('envelope seal', 0.35, 0.38, 0.51, 0.58)],
 'f28': [R('Ferro head', 0.24, 0.08, 0.33, 0.26), R('Ferro full figure', 0.19, 0.08, 0.35, 0.92)],
 'f24': [R('headline', 0.22, 0.12, 0.90, 0.45), dict(R('headline text', 0.15, 0.10, 0.92, 0.62, req=False), face=True)],
 'f15': [R('Nickel face', 0.25, 0.0, 0.42, 0.42), R('eyes behind the bars', 0.60, 0.30, 0.90, 0.60, req=False)],
 'f15a': [R('vault bars', 0.20, 0.10, 0.80, 0.90)],
 'f15b': [R('hand + key', 0.10, 0.10, 0.85, 0.80)],
 'f22a': [R('shoes', 0.20, 0.62, 0.60, 0.88)],
 'f22d': [R('flying fedora', 0.45, 0.25, 0.75, 0.55), R('confetti pile', 0.25, 0.5, 0.75, 0.95, req=False)],
 'f23a': [R('running feet', 0.35, 0.40, 0.75, 0.90)],
 'f23c': [R('bowler hat', 0.15, 0.40, 0.45, 0.75), R('streetlamp', 0.50, 0.10, 0.70, 0.40, req=False)],
 'f23d': [R('alley lights', 0.40, 0.30, 0.60, 0.80)],
}
FORCE_LAYOUT = {'p09': 'inset-two', 'p10': 'tilt-two', 'p04b': 'inset-two'}   # p04b: a 3.8:1 strip cuts Nickel's head   # f28's full figure needs the wide inset (slant-two cuts it)
MATCH_MIN = 0.75
BEAT = 60 / 86.1


def clip_start_still(fid):
    """(image path, matched?) for a clip: the original panel when the clip's first frame registers on it, else the
    clip-start still (written once from the first frame)."""
    import comic_lib as C
    from PIL import Image, ImageFilter
    clip = os.path.join(ASSETS, clip_rel(fid))
    img_rel = UNIT_IMAGE.get(fid, f'panels/{fid}.jpg')
    panel = Image.open(os.path.join(ASSETS, img_rel)).convert('RGB')
    fr = C.first_frame(clip)
    _, score = C.register(panel, fr)
    if score >= MATCH_MIN:
        return img_rel, round(score, 3)
    out = os.path.join(ASSETS, 'panels', f'{fid}_clipstart.jpg')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(clip):
        fr.resize((1280, 720), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2)).save(out, quality=95)
    return f'panels/{fid}_clipstart.jpg', round(score, 3)
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


# Motivated SFX only (Jason 2026-10-14): a burst needs an on-screen action at that moment; everything else is cut.
MOTIVATED_SFX = {
    'f01': 'lightning strikes the spire', 'f02': 'boot lands in the puddle', 'f05': 'door slot snaps open',
    'f07': 'cards slapped down, coins explode up', 'f09': 'crate drops off the crane', 'f10': 'tyres drift and spark',
    'f11': 'blueprint slammed on the table', 'f13': 'vault dial tumblers crack', 'f15': 'vault door slams shut',
    'f16': 'wire hair picks the lock', 'f18': 'they blast out of the vault roof', 'f20': 'crate bursts open into confetti',
    'f21': 'warehouse doors kicked in', 'f22': 'Uno flips Ferro onto the floor', 'f26': 'glasses clink',
}


def unit(fid, land, sfx, impact, ent, motion, k, slot=None):
    if fid not in MOTIVATED_SFX:
        sfx, impact = None, False
    u = {'id': fid, 'image': UNIT_IMAGE.get(fid, f'panels/{fid}.jpg'), 'at': land, **MOMENTS.get(fid, {}), 'captions': [],
         'entrance': {'type': ent, 'dur': 0.3}}
    if slot:
        u['slot'] = slot
    rel = clip_rel(fid)
    if os.environ.get('CJC_CLIPS') == '1' and rel and fid not in DROP_CLIPS:
        u['clip'] = {'src': rel, 'in': 0.0, 'out': CLIP_LEN}
        if fid in TRIMS:
            u['clip']['out'], u['clip']['trimNote'] = TRIMS[fid]
        img, score = clip_start_still(fid)
        u['clip']['firstFrameNcc'] = score
        if img != u['image']:
            u['panelOriginal'] = u['image']; u['image'] = img
            u['clipStartStill'] = True
    else:
        if fid in NO_CLIP:
            u['stillMotion'] = {'type': motion, 'amount': 0.12, 'dur': 5.0}
            u['stillOk'] = 'sequence lead-up inset (no clip by design): gentle pan/zoom of the still'
        else:
            u['stillMotion'] = {'type': motion, 'amount': 0.05, 'dur': 6.0}
            u['clipPending'] = f'clips/{fid}.mp4'
    if fid in V5_FOCUS and not u.get('clipStartStill'):
        u['focusRegions'] = V5_FOCUS[fid]
    else:
        u['focusRegions'] = (CLIPSTART_FOCUS[fid] if u.get('clipStartStill') else FOCUS_REGIONS.get(fid, []) + FACES.get(fid, []))
    if fid in DROP_CLIPS:
        u['clipDropped'] = DROP_CLIPS[fid]
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
            land = round(B[bisect.bisect_left(B, start - 0.03)], 3) if j == 0 and land <= start + 0.5 else (round(land, 3) if layout.startswith('seq-') else snap(land))   # sequence insets land on half beats: no empty wait
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
        # lyric captions live on the floating lyric overlay (scripts/lyric_overlay.py, spec.lyricOverlay), timed by
        # the song alone: nothing is attached to panels and no page waits on a caption. Legacy per-panel lyric
        # captions (below) only when LYRIC_OVERLAY is off.
        # lyric captions (legacy): on the latest panel landed by the line's first word, or on the splash after its zoom;
        # a line still being sung when the zoom lands is carried onto the splash
        caps = []
        for s, e, x in ([] if LYRIC_OVERLAY else LINES):
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
            if u.get('clip') and u is not out.get('splash') and not layout.startswith('seq-'):
                # richer motion (v3): when the page turn would cut this clip, land the panel earlier (whole beats,
                # never sooner than 2 beats after the previous panel on the page) so the clip plays out
                want = u['clip']['out'] - u['clip']['in']
                prev = max((p['at'] for p in out['panels'] if p['at'] < u['at'] - 0.01), default=start)
                orig = u['at']
                # never move a panel across a Short boundary (the Short's first/last panels stay put)
                floor_ = max([x for x in (SHORT['start'], SHORT['end']) if orig >= x - 0.05], default=-1)
                end_ = sp_at if sp_at is not None else end   # a splash zoom cuts the page's panels too
                while end_ - next_beat(u['at']) - 0.1 < want - 0.01:
                    cand = max((b for b in B if b < u['at'] - 0.05), default=None)
                    if cand is None or cand < next_beat(prev, 2) - 0.01 or cand < start + 0.3 or cand < floor_ + 0.3:
                        break
                    u['at'] = round(cand, 3)
                    u['landNote'] = f"landed {orig - u['at']:.2f}s early (from {orig:.3f}) so the clip plays out before the page turn"
                for c in u['captions']:
                    c['at'] = round(max(c['at'], u['at']), 3)
            if u.get('clip'):
                is_sp = u is out.get('splash')
                end_ = end if (is_sp or sp_at is None) else sp_at
                avail = round(end_ - next_beat(u.get('at', sp_at or start)) - 0.1, 2)
                if avail < u['clip']['out'] - 0.01:
                    u['clip']['out'] = avail
                    u['clip']['trimNote'] = f"{'page turns' if end_ == end else 'splash zooms in'} at {end_:.2f}s, clip capped to {avail}s"
        pages.append(out)
    spec = {'title': 'Concrete Jungle Cold - comic mode (Progressive Slop)', 'outName': 'concrete-jungle-cold', 'assetsDir': ASSETS, 'fps': 30,
            'defaults': {'holdBeats': 1}, 'camera': {'rule': 'reveal'},   # pan only across the crop-hidden part, one way, linear; no ping-pong (clips hold their last frame) 'mood': 'action', 'bgTheme': 'deco_gold', 'loop': True,
            'bg_video': {'landscape': 'bg/deco_gold-landscape.mp4', 'vertical': 'bg/deco_gold-vertical.mp4'},  # scripts/make_loop_bg.py --theme deco_gold
            'song': {'suno': '007325bb-143d-467d-90bc-cc25083181d6', 'audio': 'audio.mp3',
                     'audioNote': 'relative to assetsDir; not committed', 'timeline': 'shots/concrete-jungle-cold-comic/timeline.json',
                     'start': 0.0, 'end': END, 'loudness': -14},
            'lyricOverlay': {'enabled': LYRIC_OVERLAY, 'style': 'deco_gold'},   # floating lyric layer (docs/VIDEO_PIPELINE.md)
            'short': SHORT,
            'intro': {'enabled': True, 'title': 'CONCRETE JUNGLE COLD', 'lines': ['CONCRETE', 'JUNGLE COLD'],
                      'subtitle': 'PROGRESSIVE SLOP PRESENTS', 'seconds': round(4 * BEAT, 3),   # 4 beats: build-in + short hold
                      'logotype': 'title/cjc-logotype.jpg',   # approved 2026-10-14 (Art Deco gold badge)
                      'glow': [255, 196, 70], 'glow2': [200, 20, 50],
                      'chrome': [[255, 250, 215], [255, 215, 110], [196, 140, 40], [90, 52, 8], [210, 160, 60], [255, 236, 170]],
                      'subColor': [255, 226, 150], 'rot': -3, 'dim': 0.5, 'sunburst': {'color': [230, 180, 70], 'alpha': 0.3}},
            'tbc': {'enabled': True, 'text': 'TO BE CONTINUED...', 'seconds': 2.5,
                    'style': {'style': 'plain', 'glow': [255, 196, 70], 'glow2': [200, 20, 50], 'subColor': [255, 226, 150],
                              'chrome': [[255, 250, 215], [255, 215, 110], [196, 140, 40], [90, 52, 8], [210, 160, 60], [255, 236, 170]]}},
            'endCard': {'enabled': True, 'seconds': 3.0, 'sunburst': {'color': [230, 180, 70], 'alpha': 0.6},
                        'fills': [[255, 214, 110], [255, 70, 90]],
                        'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!'],
                        'shortLines': ['See the whole story @progressiveslop']},
            'pages': pages}
    spec['_dir'] = HERE
    for line in fix_layouts(spec):
        print('layout:', line)
    for line in place_lettering(spec):
        if 'cover 0.0' not in line:
            print('lettering:', line)
    spec.pop('_dir')
    add_chains(spec)
    # HARD GATE: every panel animated. Without CJC_CLIPS=1 this is a preview spec (QA warns, not deliverable).
    still = [u['id'] for p in pages for u in p['panels'] + ([p['splash']] if p.get('splash') else []) if not u.get('clip') and not u.get('stillOk')]
    if os.environ.get('CJC_CLIPS') != '1':
        spec['allowStills'] = True
    elif still:
        msg = f"{len(still)} panel(s) without a clip: {', '.join(dict.fromkeys(still))}"
        if os.environ.get('CJC_ALLOW_STILLS') != '1':
            sys.exit('FAIL every panel must have a QA-passed clip (still-only is not deliverable): ' + msg)
        print('WARN preview only (CJC_ALLOW_STILLS=1):', msg); spec['allowStills'] = True
    path = os.path.join(HERE, 'concrete-jungle-cold-comic.comic.json')
    json.dump(spec, open(path, 'w'), indent=1, ensure_ascii=False)
    print(os.path.relpath(path, REPO), sum(len(p['panels']) + bool(p.get('splash')) for p in pages), 'panels', len(pages), 'pages')


def fix_layouts(spec):
    """Scene-aware layout pass. Panels always keep story order (slot a, b, c, d = reading order, never permuted).
    Per page, every layout with the right panel count is scored on required focus misses: hard = 16:9 + panels inside
    the Short (QA fails), soft = vertical panels outside the Short (QA warns). Only layouts with the page's minimum hard
    misses are allowed; a global search over those picks the combination with no neighbour repeats, the lowest maximum
    reuse of any layout, the fewest plain `side-two` pages, the most distinct layouts, then the fewest soft misses."""
    import comic_lib as C
    from collections import Counter
    pages = spec['pages']; report = []; used = Counter({'side-two': 1})   # plain columns: fallback only
    s0, s1 = spec['short']['start'], spec['short']['end']
    def score(pg, layout):
        slots = sorted(C.LAYOUTS[layout]['slots'])
        sub = dict(spec, panels=[dict(u, slot=s) for u, s in zip(pg['panels'], slots)], layout=layout, page=pg['id'],
                   song=dict(spec['song'], start=pg['start'], end=pg['end']))
        in_short = {u['id'] for u in pg['panels'] if u['at'] < s1 and pg['end'] > s0}
        vp = C.page_focus_problems(spec, sub, 'vertical')
        hard = sum(f for *_, f in C.page_focus_problems(spec, sub, 'landscape')) + sum(f for uid, *_, f in vp if uid in in_short)
        soft = sum(f for uid, *_, f in vp if uid not in in_short)   # QA only warns on these
        return round(hard, 3), round(soft, 3)
    import itertools
    opts = []
    for pg in pages:
        if pg['layout'].startswith('seq-'):
            sc = {pg['layout']: score(pg, pg['layout'])}   # v5 sequence strips: forced
        elif pg['id'] in FORCE_LAYOUT:
            sc = {FORCE_LAYOUT[pg['id']]: score(pg, FORCE_LAYOUT[pg['id']])}
        else:
            sc = {name: score(pg, name) for name, L in C.LAYOUTS.items() if L['n'] == len(pg['panels']) and not L.get('reflow') and not L.get('sequence')}   # living panels: opt-in per page only
        hmin = min(h for h, _ in sc.values())
        opts.append({k: v for k, v in sc.items() if v[0] <= hmin + 1e-6})
    best = None
    for combo in itertools.product(*[sorted(o) for o in opts]):
        if any(a == b for a, b in zip(combo, combo[1:])):
            continue
        cnt = Counter(combo)
        key = (max(cnt.values()), cnt['side-two'], -len(cnt), round(sum(o[c][1] for o, c in zip(opts, combo)), 2))
        if best is None or key < best[0]:
            best = (key, combo)
    for pg, o, name in zip(pages, opts, best[1]):
        report.append(f"{pg['id']}: {pg['layout']} -> {name} (misses hard/soft {o[name]}; options {sorted(o)})")
        pg['layout'] = name
        for u, sl in zip(pg['panels'], sorted(C.LAYOUTS[name]['slots'])):
            u['slot'] = sl
    return report


def _overlap(a, b):
    """Overlap area of rect a (x, y, w, h) with box b (x0, y0, x1, y1)."""
    return max(0, min(a[0] + a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[1] + a[3], b[3]) - max(a[1], b[1]))


def place_lettering(spec):
    """Face-aware lettering pass: every caption anchor (tl/tr/bl/br) and SFX spot is chosen so its measured box (the
    renderer's own caption_box / sfx_rect, after auto-fit) covers as little of ANY face in the panel as possible, in 16:9
    and in the Short (vertical pages outside the Short count x0.2). Captions on screen together use different
    top/bottom rows so they never stack."""
    import comic_lib as C
    s0, s1 = spec['short']['start'], spec['short']['end']
    report = []
    for pg in spec['pages']:
        units = [(u, u['slot']) for u in pg['panels']] + ([(pg['splash'], 'splash')] if pg.get('splash') else [])
        ctx = {}
        for orient in ('landscape', 'vertical'):
            G = C.layout_geo(orient, pg['layout'], pg.get('splashStyle', 'full'))
            Lr = C.layout(orient, pg['layout'], pg.get('splashStyle', 'full'))
            for u, sl in units:
                size, crop, regions, _, _ = C.unit_fit(spec, u, G[sl], spec.get('fps', 30))
                faces = [C.region_to_frame(r['box'], size, crop, G[sl]) for r in regions if r.get('face')]
                land = u.get('at', pg.get('transition', {}).get('at', pg['start']))
                w = 1.0 if orient == 'landscape' or (land < s1 and pg['end'] > s0) else 0.2
                ctx[(u['id'], orient)] = (G[sl], Lr[sl], faces, w)
        def cost_rect(uid, rect_fn):
            c = 0.0
            for orient in ('landscape', 'vertical'):
                geo, slot, faces, w = ctx[(uid, orient)]
                r = rect_fn(geo, slot, orient)
                c += w * sum(_overlap(r, f) for f in faces) / max(1, r[2] * r[3])
            return c
        for u, sl in units:
            caps = u.get('captions', [])
            for i, c in enumerate(caps):
                end_c = c.get('until', pg['end'])
                busy = {o['anchor'][0] for o in caps[:i] if o['at'] < end_c and o.get('until', pg['end']) > c['at']}
                best = None
                for a in ('tl', 'tr', 'bl', 'br'):
                    if a[0] in busy:
                        continue
                    cc = cost_rect(u['id'], lambda geo, slot, o: C.caption_box(dict(c, anchor=a), slot, geo, C.TEXT_SAFE[o])[0])
                    key = (round(cc, 3), a != c.get('anchor'))
                    if best is None or key < best[0]:
                        best = (key, a)
                if best:
                    c['anchor'] = best[1]
            for sx in u.get('sfx', []):
                best = None
                for px in (0.22, 0.5, 0.78):
                    for py in (0.25, 0.5, 0.75):
                        cand = dict(sx, pos=[px, py])
                        cc = cost_rect(u['id'], lambda geo, slot, o: C.sfx_rect(cand, slot, C.SFX_PEAK, geo, C.TEXT_SAFE[o],
                                                                               C.unit_caption_rects(u, slot, geo, C.TEXT_SAFE[o]))[0])
                        key = (round(cc, 3), abs(px - sx['pos'][0]) + abs(py - sx['pos'][1]))
                        if best is None or key < best[0]:
                            best = (key, [px, py])
                sx['pos'] = best[1]
                sx['rot'] = -8 if best[1][0] > 0.5 else 7
                report.append(f"{u['id']}: sfx {sx['text']} at {best[1]} face cover {best[0][0]}")
    return report


# v6 (2026-10-14): NO shot may repeat. When a cell's clip ends before the cell leaves the screen, the cell cuts (on a
# beat) to a NEW clip from clips/v6 (prompts_batch6.md); any leftover under the last clip is covered by forward-only
# slow motion (clip.speed >= 0.6), never a loop or a replay.
CHAINS = {'f01': ['n01', 'n02', 'n03', 'n04'], 'f02': ['n05', 'n06'], 'f03': ['n07'], 'f05': ['n08'], 'f06': ['n30'],
          'f09': ['n09', 'n10'], 'f10': ['n29'], 'f15a': ['f14'], 'f11': ['n11', 'n12'], 'f12': ['n13'], 'f13': ['n31'], 'f16': ['n14'], 'f17': ['n32'],
          'f18': ['n15', 'n16', 'n17'], 'f19': ['n18'], 'f20': ['n19'], 'f21': ['n20'], 'f23b': ['n21'],
          'f25': ['n22', 'n23', 'n24', 'n25'], 'f27': ['n26', 'n27'], 'f28': ['n28']}
CHAIN_AT = {'f14': 72.42}   # chain shots after a still base land at a fixed time
V6_FILE = {'n05': 'n05_street', 'n10': 'n10_take3', 'n17': 'n17_take2'}   # never *_take1*, *nopants*, *nocoat*, n10, n10_take2, n05(_take2/3)
CHAIN_ENTRANCES = ['fade', 'wipe', 'iris', 'slide_left', 'slide_up']
MIN_SPEED = 0.55
CHAIN_FOCUS = {   # read off a 10% grid sheet of the v6 panels (character shots); the rest are no-people shots
 'n06': [R('Aura face', 0.45, 0.05, 0.58, 0.30)],
 'n10': [R('Uno face', 0.25, 0.0, 0.42, 0.30), R('Aura face', 0.66, 0.30, 0.78, 0.48)],
 'n17': [R('Uno face', 0.30, 0.05, 0.45, 0.30), R('Aura face', 0.56, 0.10, 0.70, 0.35)],
 'n21': [R('Aura face', 0.38, 0.10, 0.55, 0.40)],
 'n23': [R('Uno face', 0.30, 0.12, 0.48, 0.42), R('gold 1 chain', 0.12, 0.30, 0.30, 0.80, req=False)],
 'n24': [R('Aura face', 0.37, 0.10, 0.55, 0.42)],
}


def add_chains(spec):
    import comic_lib as C
    from PIL import Image
    k = 0; used = []
    for pg in spec['pages']:
        sp = pg.get('splash'); spat = pg.get('transition', {}).get('at')
        base = [(u, spat if sp else pg['end']) for u in pg['panels']] + ([(sp, pg['end'])] if sp else [])
        new = []
        for u, cell_exit in base:
            if not u.get('clip') and u['id'] not in CHAINS:
                continue
            land0 = u.get('at', spat)
            cur, cur_land = u, land0
            for nid in CHAINS.get(u['id'], []):
                if nid in CHAIN_AT:
                    land = CHAIN_AT[nid]
                else:
                    c = cur['clip']
                    end_ = C.MIN_HOLD + cur_land + (c['out'] - c['in']) / c.get('speed', 1.0)
                    land = round(max([b for b in B if b <= end_ + 0.02 and b > cur_land + 1.0], default=end_), 3)
                if land > cell_exit - 0.9:
                    print('chain: no room for', nid, 'after', cur['id']); break
                rel = f"clips/v5/{nid}.mp4" if nid.startswith('f') else f"clips/v6/{V6_FILE.get(nid, nid)}.mp4"
                img = f'panels/{nid}.jpg'
                regs = CHAIN_FOCUS.get(nid, V5_FOCUS.get(nid))
                if regs is None:
                  regs = []
                  try:
                    regs = [] if nid not in ('n29',) else C.auto_focus_regions(Image.open(os.path.join(ASSETS, img)).convert('RGB'))
                  except Exception:
                    pass
                out_ = round(min(CLIP_LEN, cell_exit - land - C.MIN_HOLD), 2)
                nu = {'id': nid, 'image': img, 'at': land, 'slot': cur.get('slot', u.get('slot', 'splash')), 'captions': [],
                      'entrance': {'type': CHAIN_ENTRANCES[k % len(CHAIN_ENTRANCES)], 'dur': 0.3},
                      'clip': {'src': rel, 'in': 0.0, 'out': out_}, 'focusRegions': regs, 'chainOf': u['id'],
                      'shotKind': 'character' if regs else 'fx'}
                k += 1
                cur['until'] = land
                if u is sp:
                    nu['slot'] = None   # splash chains are not supported by the renderer: skip
                    print('chain: splash', u['id'], 'skipped', nid); break
                new.append(nu); used.append(nid)
                cur, cur_land = nu, land
            # leftover under the last shot of the cell: forward-only slow motion, spread over every chained clip of the
            # cell that is free to move (a chain cut then lands later on its beat)
            shots = [x for x in [u] + [n for n in new if n.get('chainOf') == u['id']] if x.get('clip')]
            c = cur['clip']
            L = c['out'] - c['in']
            once = (cur_land if cur is not u else land0) + C.MIN_HOLD + L / c.get('speed', 1.0)
            left = cell_exit - once
            if left > 0.1:
                free = [x for x in shots if x is cur or (x is not u and x['id'] not in CHAIN_AT)]
                tot = sum(x['clip']['out'] - x['clip']['in'] for x in free)
                sp_ = max(MIN_SPEED, tot / (tot + left)) - 0.005
                t_ = None
                for x in shots:
                    if x in free:
                        if t_ is not None and x['id'] not in CHAIN_AT and x is not u:
                            x['at'] = round(t_, 3)
                        x['clip']['speed'] = round(sp_, 4)
                    t_ = (x['at'] if x is not u else land0) + C.MIN_HOLD + (x['clip']['out'] - x['clip']['in']) / x['clip'].get('speed', 1.0)
                # re-link until + cap the last clip to the cell
                for a_, b_ in zip(shots, shots[1:]):
                    a_['until'] = b_['at']
                last = shots[-1]; lc = last['clip']
                rem = cell_exit - ((last['at'] if last is not u else land0) + C.MIN_HOLD)
                lc['out'] = round(min(lc['out'], rem * lc['speed']), 2)
                endt = (last['at'] if last is not u else land0) + C.MIN_HOLD + (lc['out'] - lc['in']) / lc['speed']
                if cell_exit - endt > 0.12:
                    print(f"chain: {last['id']} cell still {cell_exit - endt:.2f}s short")
        pg['panels'] += new
    print('chains: used', len(used), 'new clips:', ' '.join(used))


if __name__ == '__main__':
    build()

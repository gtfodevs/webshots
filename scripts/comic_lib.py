"""Comic mode: shared layout, timing and drawing code for comic_render.py and comic_qa.py.

A comic scene is a JSON spec (shots/<name>/<name>.comic.json) listing panels in reading
order. Each panel lands on a beat in a slot of a page layout, holds as a static panel,
optionally plays a short trimmed Grok Imagine clip inside its frame, then freezes on the
clip's last frame. A transition (zoom into a panel) leads to a full-frame splash.
All "at" times in the spec are SONG seconds; scene time = song time - song.start.
"""
import json, math, os, re, subprocess, shutil, urllib.request
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANGERS_URL = 'https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf'
PAPER = (244, 236, 216)
INK = (12, 10, 14)
CAPTION_FILL = (255, 228, 122)

# ---------------------------------------------------------------- spec + paths
def load_spec(path):
    with open(path) as f:
        spec = json.load(f)
    spec['_path'] = os.path.abspath(path)
    spec['_dir'] = os.path.dirname(spec['_path'])
    return spec

def resolve(spec, p):
    """Media paths: absolute, repo-relative (song), or relative to spec.assetsDir (env COMIC_ASSETS overrides)."""
    if os.path.isabs(p):
        return p
    base = os.environ.get('COMIC_ASSETS') or spec.get('assetsDir') or spec['_dir']
    cand = os.path.join(base, p)
    return cand if os.path.exists(cand) else os.path.join(ROOT, p)

def song_timeline(spec):
    tl = spec['song'].get('timeline')
    if not tl:
        return {}
    with open(resolve(spec, tl)) as f:
        return json.load(f)


def song_beats(spec):
    return song_timeline(spec).get('beats', [])


def beat_period(spec):
    """Seconds per beat: the timeline's tempo when it has one, else the median beat spacing."""
    tl = song_timeline(spec)
    if tl.get('tempo'):
        return 60.0 / tl['tempo']
    b = tl.get('beats', [])
    if len(b) < 3:
        return 0.5
    d = sorted(b[i + 1] - b[i] for i in range(len(b) - 1))
    return d[len(d) // 2]

def T(spec, song_t):
    return song_t - spec['song']['start']

DEFAULT_HOLD_BEATS = 1     # Jason's rule: static hold of ~one beat (0.3-0.5 s) before the clip plays
MIN_HOLD = 0.25            # ...but keep the anticipation beat (Jason likes it)
MAX_HOLD = 0.6             # QA fails if clip start - panel land > this


def subspecs(spec):
    """A spec is one page (panels/transition/splash) or a whole song ("pages": [...]).
    Returns one page-level spec per page with song.start/end set to the page's span."""
    assign_entrances(spec)
    if 'pages' not in spec:
        return [spec]
    out = []
    for pg in spec['pages']:
        sub = {k: v for k, v in spec.items() if k != 'pages'}
        sub.update(panels=pg['panels'], transition=pg.get('transition'), splash=pg.get('splash'), page=pg['id'],
                   layout=pg.get('layout', 'three'), splashStyle=pg.get('splashStyle', 'full'),
                   song=dict(spec['song'], start=pg['start'], end=pg['end']))
        for k in ('reflowArrive', 'reflowMove'):      # living-panel timing (beats), per page
            if k in pg:
                sub[k] = pg[k]
        out.append(sub)
    trs = {round(tr['at'], 3): tr['type'] for tr in page_transitions(spec)}
    for sub in out:
        sub['outTransition'] = trs.get(round(sub['song']['end'], 3))
    return out


def clip_start(spec, u):
    """Song time the clip starts: explicit clip.at, else the first beat at/after the panel lands
    (the one-beat anticipation hold: the first beat after the panel lands). Slow songs (one beat > MAX_HOLD) are
    allowed: QA caps the delay at max(MAX_HOLD, one beat), so snapping to that beat always passes."""
    c = u['clip']
    if c.get('at') is not None:
        return c['at']
    # first beat strictly after the land: the anticipation hold. (A panel lands on a beat, so "at or after" would
    # start the clip at 0 s and kill the hold; "after" keeps one beat and the tempo-aware max allows it.)
    if spec.get('camera', {}).get('rule', 'reveal') == 'reveal':
        return round(u['at'] + MIN_HOLD, 3)   # no dead air (Jason 2026-10-14): shortest anticipation hold, never > 0.5 s
    beats = [b for b in song_beats(spec) if b > u['at'] + 0.05]
    return beats[0] if beats else u['at'] + 0.45


def splash_unit(spec):
    sp = spec.get('splash')
    if not sp or not spec.get('transition'):
        return None
    return dict(sp, id=sp.get('id', 'splash'), at=spec['transition']['at'])


def scene_len(spec):
    return spec['song']['end'] - spec['song']['start']

def probe_duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True).stdout
    return float(out.strip())

def next_free(path):
    """Never overwrite: foo.mp4 -> foo-v2.mp4 -> foo-v3.mp4 ..."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f'{stem}-v{n}{ext}'):
        n += 1
    return f'{stem}-v{n}{ext}'

# ---------------------------------------------------------------- fonts
@lru_cache(None)
def font_path():
    try:
        p = subprocess.run(['fc-match', '-f', '%{file}', 'Bangers'], capture_output=True, text=True).stdout.strip()
        if p and 'angers' in p:
            return p
    except FileNotFoundError:
        pass
    cache = os.path.expanduser('~/.cache/webshots/fonts/Bangers-Regular.ttf')
    if not os.path.exists(cache):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        urllib.request.urlretrieve(BANGERS_URL, cache)  # SIL Open Font License
    return cache

@lru_cache(None)
def font(px):
    return ImageFont.truetype(font_path(), int(px))

# ---------------------------------------------------------------- layouts
SIZES = {'landscape': (1920, 1080), 'vertical': (1080, 1920)}

# Layout library. Each layout is a list of slot primitives in normalised page-content coordinates
# (u, v in 0..1, landscape). A primitive is one of
#   ('rect', u, v, w, h)                       axis-aligned panel
#   ('poly', [(u, v), ...], inner)             slanted / diagonal panel; inner = (u, v, w, h) lettering-safe rect
#   ('rot', cu, cv, w, h, deg)                 panel rotated by deg (overlapping-at-an-angle, insets)
# plus options {'z': draw order, 'keyline': white keyline around the ink (insets laid over other panels)}.
# 'vert' says how the layout becomes 1080x1920: 'same' (same normalised geometry in the tall content box)
# or 'T' (transpose u<->v, so left/right splits become top/bottom splits).
GX, GY = 0.013, 0.024   # gutters in normalised units (~24 px)

# ---- living panels (scripts/reflow.py): static slots are the FINAL state; Scene animates the earlier states
def _reflow(n, land='wide', vert='rows'):
    import reflow as RF
    sl = {chr(97 + i): ('rect',) + tuple(r) for i, r in enumerate(RF.states(n, land)[-1])}
    vs = {chr(97 + i): ('rect',) + tuple(r) for i, r in enumerate(RF.states(n, vert)[-1])}
    return {'n': n, 'vert': 'own', 'reflow': True, 'family': {'landscape': land, 'vertical': vert}, 'slots': sl, 'vslots': vs}


# ---- sequence strips (lead-up / sub-action panels, COMIC_MODE.md "Sequence strips"): a run of small keylined
# insets along the top that land on consecutive beats (story told by their order), over a big payoff panel.
def _seq(n, low=False):
    """low=True: the inset strip runs along the BOTTOM of the 16:9 frame over a payoff that fills the top 78 %, for
    payoffs whose faces sit high in the art (a top strip would cover them). Vertical is the same either way."""
    k = n - 1                      # insets
    w = (1 - 0.04 - 0.02 * (k - 1)) / k
    ins = {chr(97 + i): ('rot', 0.02 + w / 2 + i * (w + 0.02), 0.80 if low else 0.20, w, 0.36, (-2, 2)[i % 2], {'z': 1, 'keyline': True})
           for i in range(k)}
    ins[chr(97 + k)] = (('rect', 0, 0, 1, 0.78, {'inner': (0, 0, 1, 0.58)}) if low else
                        ('rect', 0, 0.22, 1, 0.78, {'inner': (0, 0.42, 1, 0.58)}))
    vk = {}
    cols = 2 if k >= 4 else k
    rows = -(-k // cols)
    vw = (1 - 0.04 - 0.03 * (cols - 1)) / cols; vh = 0.40 / rows
    for i in range(k):
        r_, c_ = divmod(i, cols)
        vy = (0.58 if low else 0.02) + vh / 2 + r_ * (vh + 0.012)
        vk[chr(97 + i)] = ('rot', 0.02 + vw / 2 + c_ * (vw + 0.03), vy, vw, vh, (-2, 2)[i % 2], {'z': 1, 'keyline': True})
    vk[chr(97 + k)] = (('rect', 0, 0, 1, 0.60, {'inner': (0, 0, 1, 0.48)}) if low else
                       ('rect', 0, 0.40, 1, 0.60, {'inner': (0, 0.52, 1, 0.48)}))
    return {'n': n, 'vert': 'own', 'sequence': True, 'slots': ins, 'vslots': vk}
LAYOUTS = {
    # ---- two panels
    'two-up': {'n': 2, 'vert': 'same', 'slots': {
        'a': ('rect', 0, 0, 1, 0.5 - GY / 2), 'b': ('rect', 0, 0.5 + GY / 2, 1, 0.5 - GY / 2)}},
    'slant-two': {'n': 2, 'vert': 'T', 'slots': {
        'a': ('poly', [(0, 0), (0.62, 0), (0.40, 1), (0, 1)], (0, 0, 0.40, 1)),
        'b': ('poly', [(0.62 + GX, 0), (1, 0), (1, 1), (0.40 + GX, 1)], (0.62 + GX, 0, 0.38 - GX, 1))}},
    'inset-two': {'n': 2, 'vert': 'same', 'slots': {
        'a': ('rect', 0, 0, 1, 1, {'inner': (0, 0, 0.52, 1)}),
        'b': ('rot', 0.76, 0.69, 0.42, 0.50, -3, {'z': 1, 'keyline': True})}},
    'tilt-two': {'n': 2, 'vert': 'T', 'slots': {
        'a': ('rot', 0.34, 0.45, 0.67, 0.88, 2, {'inner': (0.03, 0.06, 0.36, 0.78)}),
        'b': ('rot', 0.69, 0.56, 0.60, 0.84, -3, {'z': 1, 'keyline': True})}},
    'side-two': {'n': 2, 'vert': 'T', 'slots': {   # two near-square columns (two full-width tiers in vertical)
        'a': ('rect', 0, 0, 0.5 - GX / 2, 1), 'b': ('rect', 0.5 + GX / 2, 0, 0.5 - GX / 2, 1)}},
    # ---- three panels
    'three': {'n': 3, 'vert': 'stack', 'slots': {
        'a': ('rect', 0, 0, 0.4935, 0.509), 'b': ('rect', 0.5065, 0, 0.4935, 0.509), 'c': ('rect', 0, 0.533, 1, 0.467)}},
    'diagonal-three': {'n': 3, 'vert': 'T', 'slots': {
        'a': ('poly', [(0, 0), (0.37, 0), (0.30, 1), (0, 1)], (0, 0, 0.30, 1)),
        'b': ('poly', [(0.37 + GX, 0), (0.71, 0), (0.64, 1), (0.30 + GX, 1)], (0.37 + GX, 0, 0.27 - GX, 1)),
        'c': ('poly', [(0.71 + GX, 0), (1, 0), (1, 1), (0.64 + GX, 1)], (0.71 + GX, 0, 0.29 - GX, 1))}},
    'mixed-three': {'n': 3, 'vert': 'T', 'slots': {
        'a': ('rect', 0, 0, 0.62, 1),
        'b': ('poly', [(0.62 + GX, 0), (1, 0), (1, 0.42), (0.62 + GX, 0.56)], (0.62 + GX, 0, 0.38 - GX, 0.42)),
        'c': ('poly', [(0.62 + GX, 0.56 + GY), (1, 0.42 + GY), (1, 1), (0.62 + GX, 1)], (0.62 + GX, 0.56 + GY, 0.38 - GX, 0.44 - GY))}},
    'inset-three': {'n': 3, 'vert': 'same', 'slots': {
        'a': ('rect', 0, 0, 1, 0.47, {'inner': (0, 0, 0.62, 0.47)}),
        'b': ('rect', 0, 0.47 + GY, 1, 0.53 - GY, {'inner': (0, 0.47 + GY, 0.62, 0.53 - GY)}),
        'c': ('rot', 0.81, 0.49, 0.32, 0.44, -4, {'z': 2, 'keyline': True})}},
    # wide cells for scene-aware cropping: one big cell + two halves (picked when focus regions do not fit)
    'big-three': {'n': 3, 'vert': 'T', 'slots': {
        'a': ('rect', 0, 0, 0.6, 1), 'b': ('rect', 0.6 + GX, 0, 0.4 - GX, 0.5 - GY / 2), 'c': ('rect', 0.6 + GX, 0.5 + GY / 2, 0.4 - GX, 0.5 - GY / 2)}},
    'wide-three': {'n': 3, 'vert': 'same', 'slots': {
        'a': ('rect', 0, 0, 1, 0.5 - GY / 2), 'b': ('rect', 0, 0.5 + GY / 2, 0.5 - GX / 2, 0.5 - GY / 2), 'c': ('rect', 0.5 + GX / 2, 0.5 + GY / 2, 0.5 - GX / 2, 0.5 - GY / 2)}},
    # ---- four panels: slanted 2x2 in landscape; four full-width tiers in vertical (explicit 'vslots')
    'four-grid': {'n': 4, 'vert': 'own', 'slots': {
        'a': ('poly', [(0, 0), (0.56, 0), (0.50, 0.49), (0, 0.49)], (0, 0, 0.50, 0.49)),
        'b': ('poly', [(0.56 + GX, 0), (1, 0), (1, 0.49), (0.50 + GX, 0.49)], (0.56 + GX, 0, 0.44 - GX, 0.49)),
        'c': ('poly', [(0, 0.49 + GY), (0.46, 0.49 + GY), (0.40, 1), (0, 1)], (0, 0.49 + GY, 0.40, 0.51 - GY)),
        'd': ('poly', [(0.46 + GX, 0.49 + GY), (1, 0.49 + GY), (1, 1), (0.40 + GX, 1)], (0.46 + GX, 0.49 + GY, 0.54 - GX, 0.51 - GY))},
        'vslots': {'a': ('rect', 0, 0, 1, 0.235), 'b': ('rect', 0, 0.255, 1, 0.235),
                   'c': ('rect', 0, 0.51, 1, 0.235), 'd': ('rect', 0, 0.765, 1, 0.235)}},
    'tilt-three': {'n': 3, 'vert': 'T', 'slots': {
        'a': ('rot', 0.40, 0.50, 0.78, 0.94, 1.5, {'inner': (0.04, 0.06, 0.55, 0.88)}),
        'b': ('rot', 0.81, 0.27, 0.36, 0.48, -4, {'z': 1, 'keyline': True}),
        'c': ('rot', 0.80, 0.74, 0.37, 0.47, 3, {'z': 2, 'keyline': True})}},
    'seq-four': _seq(4), 'seq-five': _seq(5), 'seq-six': _seq(6),
    'seq-four-low': _seq(4, True), 'seq-five-low': _seq(5, True), 'seq-six-low': _seq(6, True),
    'reflow-two': _reflow(2), 'reflow-three': _reflow(3), 'reflow-four': _reflow(4),
    'reflow-grid-two': _reflow(2, 'grid'), 'reflow-grid-three': _reflow(3, 'grid'), 'reflow-grid-four': _reflow(4, 'grid'),
}
# legacy slot names (single-page specs written before the library)
ALIASES = {'top-left': 'a', 'top-right': 'b', 'bottom': 'c', 'top': 'a'}
SPLASH_STYLES = {
    'full': ('rect', 0, 0, 1, 1),
    'tilt': ('rot', 0.5, 0.5, 0.95, 0.93, -2),
    'breakout': ('breakout', 0.03, 0.13, 0.94, 0.84),   # frame + an impact burst that breaks out over the top border
}
CONTENT = {'landscape': (36, 36, 1848, 1008), 'vertical': (40, 60, 1000, 1800)}
SPLASH_BOX = {'landscape': (14, 14, 1892, 1052), 'vertical': (40, 400, 1000, 1120)}


def _rot_poly(cx, cy, w, h, deg):
    a = math.radians(deg); c, s_ = math.cos(a), math.sin(a)
    return [(cx + dx * c - dy * s_, cy + dx * s_ + dy * c) for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def _geo(prim, box, transpose=False):
    """Primitive -> pixel geometry {'polys', 'bbox', 'inner', 'z', 'keyline', 'burst'}."""
    bx, by, bw, bh = box
    opts = prim[-1] if isinstance(prim[-1], dict) else {}
    kind = prim[0]
    T_ = (lambda u, v: (v, u)) if transpose else (lambda u, v: (u, v))
    P = lambda u, v: (bx + T_(u, v)[0] * bw, by + T_(u, v)[1] * bh)
    def R(r):
        u, v, w, h = r
        (x0, y0), (x1, y1) = P(u, v), P(u + w, v + h)
        return (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
    burst = None
    if kind == 'rect':
        r = R(prim[1:5]); polys = [[(r[0], r[1]), (r[0] + r[2], r[1]), (r[0] + r[2], r[1] + r[3]), (r[0], r[1] + r[3])]]
        inner = R(opts['inner']) if 'inner' in opts else r
    elif kind == 'poly':
        polys = [[P(u, v) for u, v in prim[1]]]; inner = R(prim[2])
    elif kind == 'rot':
        cu, cv, w, h, deg = prim[1:6]
        cx, cy = P(cu, cv)
        pw, ph = (h * bw, w * bh) if transpose else (w * bw, h * bh)
        deg = -deg if transpose else deg
        polys = [_rot_poly(cx, cy, pw, ph, deg)]
        a = abs(math.radians(deg))
        iw, ih = pw * math.cos(a) - ph * math.sin(a), ph * math.cos(a) - pw * math.sin(a)
        inner = R(opts['inner']) if 'inner' in opts else (cx - iw / 2, cy - ih / 2, iw, ih)
    elif kind == 'breakout':
        r = R(prim[1:5]); polys = [[(r[0], r[1]), (r[0] + r[2], r[1]), (r[0] + r[2], r[1] + r[3]), (r[0], r[1] + r[3])]]
        cx, cy, R0 = r[0] + 0.70 * r[2], r[1] + 0.02 * r[3], 0.17 * min(r[2], r[3])
        pts = []
        for i in range(28):
            ang = -math.pi / 2 + i * math.pi / 14
            rad = R0 * (1.0 if i % 2 == 0 else 0.55) * (1.0 + 0.12 * math.sin(i * 2.3))
            pts.append((cx + rad * math.cos(ang) * 1.5, max(by + 4, cy + rad * math.sin(ang))))
        burst = pts
        inner = r
    xs = [x for p in polys + ([burst] if burst else []) for x, _ in p]
    ys = [y for p in polys + ([burst] if burst else []) for _, y in p]
    x0, y0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
    bbox = (x0, y0, int(math.ceil(max(xs))) - x0, int(math.ceil(max(ys))) - y0)
    inner = tuple(int(round(v)) for v in inner)
    burst = burst if DECOR_BURSTS else None   # Jason 2026-10-14: no unmotivated yellow bursts (one sat on Uno's face)
    return {'polys': polys, 'burst': burst, 'bbox': bbox, 'inner': inner, 'z': opts.get('z', 0),
            'keyline': opts.get('keyline', False)}


def layout_geo(orient, kind='three', splash='full'):
    """name -> pixel geometry for every slot of a layout (+ 'splash')."""
    if kind not in LAYOUTS:
        raise KeyError(f'unknown layout {kind!r}; have {sorted(LAYOUTS)}')
    L = LAYOUTS[kind]
    out = {}
    if orient == 'vertical' and L['vert'] == 'stack':
        x, y0, w, _ = CONTENT['vertical']
        h = round(w * 9 / 16); g = 28; top = (1920 - (3 * h + 2 * g)) // 2
        for i, n in enumerate(sorted(L['slots'])):
            out[n] = _geo(('rect', 0, 0, 1, 1), (x, top + i * (h + g), w, h))
    elif orient == 'vertical' and 'vslots' in L:
        for n, prim in L['vslots'].items():
            out[n] = _geo(prim, CONTENT[orient])
    else:
        for n, prim in L['slots'].items():
            out[n] = _geo(prim, CONTENT[orient], transpose=(orient == 'vertical' and L['vert'] == 'T'))
    out['splash'] = _geo(SPLASH_STYLES[splash], SPLASH_BOX[orient])
    for k, v in ALIASES.items():
        if v in out and k not in out:
            out[k] = out[v]
    return out


def layout(orient, kind='three', splash='full'):
    """Lettering-safe rect (x, y, w, h) per slot (captions, SFX and QA work in these)."""
    cx, cy, cw, ch = CONTENT[orient]
    def clamp(r):   # lettering never sits in the paper margin (a full-bleed splash would clip it at the frame edge)
        x0, y0 = max(r[0], cx), max(r[1], cy)
        x1, y1 = min(r[0] + r[2], cx + cw), min(r[1] + r[3], cy + ch)
        return (x0, y0, x1 - x0, y1 - y0)
    return {n: clamp(g['inner']) for n, g in layout_geo(orient, kind, splash).items()}


def slot_mask(geo):
    """L-mode mask (bbox-sized) of a slot's polygons (+ breakout burst)."""
    x0, y0, w, h = geo['bbox']
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    for p in geo['polys'] + ([geo['burst']] if geo['burst'] else []):
        d.polygon([(x - x0, y - y0) for x, y in p], fill=255)
    return m


def paper_fraction(spec, orient):
    """Share of the page that is bare paper once every panel of the page has landed."""
    W, H = SIZES[orient]
    G = layout_geo(orient, spec.get('layout', 'three'))
    m = Image.new('L', (W // 4, H // 4), 0)
    d = ImageDraw.Draw(m)
    for p in spec['panels']:
        for poly in G[p['slot']]['polys']:
            d.polygon([(x / 4, y / 4) for x, y in poly], fill=255)
    return 1 - float(np.asarray(m).mean()) / 255.0


def base_px(slot):
    return math.sqrt(slot[2] * slot[3]) * 0.75

def default_focus(img_w, img_h, dst_w, dst_h):
    """Crop centre when a slot's aspect differs from the art. Wide strips keep the upper-middle band
    (heads and hands sit there in comic framing); narrower crops stay centred. Override with "focus"."""
    return (0.5, 0.42) if dst_w / dst_h > img_w / img_h * 1.25 else (0.5, 0.5)


def cover_crop(src_w, src_h, dst_w, dst_h, focus=(0.5, 0.5), within=None):
    """Largest crop of aspect dst inside the source (or inside `within` rect), centred on focus."""
    bx, by, bw, bh = within or (0, 0, src_w, src_h)
    a = dst_w / dst_h
    cw, ch = (bw, bw / a) if bw / bh < a else (bh * a, bh)
    cx = min(max(bx + focus[0] * src_w - cw / 2, bx), bx + bw - cw)
    cy = min(max(by + focus[1] * src_h - ch / 2, by), by + bh - ch)
    return (cx, cy, cw, ch)

# ---------------------------------------------------------------- camera (shared: scripts/camera.py)
import camera as CAM
TAIL_LOOP = 2.0      # s of the clip's tail that ping-pongs after it ends (half speed): nothing ever freezes
TAIL_SPEED = 0.5
NO_REVERSE = True


LOOP_XF = 0.6   # s: forward-only crossfade loop overlap


def clip_loop(c, t_rel):
    """Never reverse video and never freeze (Jason 2026-10-14): once the clip has played, it keeps playing FORWARD
    in a loop whose seam is a crossfade: over [L-XF, L] the end blends into the start [0, XF].
    Returns (time A, time B, weight of B); weight 0 = A only."""
    L = c['out'] - c['in']
    t_rel = t_rel * c.get('speed', 1.0)   # forward-only slow motion (speed < 1) stretches a clip to fill its cell
    xf = min(LOOP_XF, L * 0.3)
    if t_rel < L - xf:
        return max(t_rel, 0.0), 0.0, 0.0
    C_ = L - xf
    u = (t_rel - C_) % C_
    if u < xf:
        return C_ + u, u, u / xf
    return u, 0.0, 0.0


def clip_time(c, t_rel, fps):
    """Clip-relative time for scene time t_rel (s since the clip started): plays once, then ping-pongs its last
    TAIL_LOOP s at TAIL_SPEED forever (a slow-mo breathing tail), so the panel never freezes."""
    L = c['out'] - c['in']
    if t_rel < L:
        return max(t_rel, 0.0)
    if NO_REVERSE:
        ta, tb, w = clip_loop(c, t_rel)
        return tb if w >= 0.5 else ta
    T_ = min(TAIL_LOOP, L * 0.5)
    m = ((t_rel - L) * TAIL_SPEED) % (2 * T_)
    return L - (m if m < T_ else 2 * T_ - m)


_PLAN_CACHE = {}
def unit_plan(spec, u, geo, fps=30, regions=None, img_size=None, within=None):
    """Per-cut camera move (scripts/camera.py) for a panel / splash in this cell. Clock = scene time (s since the
    page's song.start). Faces = required focus regions, tracked through the clip at 1 fps."""
    CAM.REVEAL = spec.get('camera', {}).get('rule', 'reveal') == 'reveal'   # default rule; 'legacy' = old moves
    if img_size is None or regions is None:
        img_size, _, regions, _, within = unit_fit(spec, u, geo, fps)
    iw, ih = img_size
    x, y, w, h = geo['bbox']
    req = [r for r in regions if r.get('required', True)]
    t_land = T(spec, u['at'])
    sp = spec.get('transition')
    is_splash = u.get('id') == (spec.get('splash') or {}).get('id', 'splash') and sp is not None and abs(u['at'] - sp['at']) < 1e-6
    t_exit = T(spec, spec['song']['end']) + 0.6
    if sp is not None and not is_splash:
        t_exit = T(spec, sp['at']) + 0.6
    if u.get('until') is not None:   # shot chains: the move runs only while this shot owns the cell
        t_exit = min(t_exit, T(spec, u['until']) + 0.3)
    # outgoing transition: the next panel's entrance on this page, else the page transition
    later = sorted([p for p in spec['panels'] if p['at'] > u['at'] + 1e-3], key=lambda p: p['at'])
    out_tr = entrance_of(later[0])['type'] if later and not is_splash else (sp.get('type') if sp and not is_splash else spec.get('outTransition'))
    key = (u['id'], tuple(geo['bbox']), spec.get('page'), json.dumps([r['box'] for r in req]), out_tr, round(t_land, 3), round(t_exit, 3))
    if key in _PLAN_CACHE:
        return _PLAN_CACHE[key]
    c = u.get('clip')
    tracks = None
    if c and req:
        cp = resolve(spec, c['src']); ip = resolve(spec, u['image'])
        reg, _ = register_cached(ip, cp, Image.open(ip).convert('RGB'), fps)
        rx, ry, rw, rh = reg
        boxes = [[(r['box'][0] * iw - rx) / rw, (r['box'][1] * ih - ry) / rh, (r['box'][2] * iw - rx) / rw, (r['box'][3] * ih - ry) / rh] for r in req]
        boxes = [[min(max(v, 0.0), 1.0) for v in b] for b in boxes]
        tracks = CAM.track_regions(cp, boxes, 1.0, os.path.join(ROOT, 'out', '.cache', 'tracks.json'), c['in'], c['out'])
        t0c = T(spec, clip_start(spec, u))
        def faces_at(t, tracks=tracks, reg=reg, t0c=t0c, c=c):
            tc = c['in'] + clip_time(c, t - t0c, fps) if t >= t0c else c['in']
            bs = CAM.interp_boxes(tracks, tc)
            return [[rx + b[0] * rw, ry + b[1] * rh, rx + b[2] * rw, ry + b[3] * rh] for b in bs]
    else:
        fixed = [[r['box'][0] * iw, r['box'][1] * ih, r['box'][2] * iw, r['box'][3] * ih] for r in req]
        faces_at = lambda t, fixed=fixed: fixed
    plan = None
    for pad in (0.06, 0.10, 0.15, 0.20):   # widen the face margin until the cell's real (slanted, inset) shape holds them
        cand = CAM.plan_move((iw, ih), (w, h), within, faces_at, t_land, t_exit, len(req), out_tr=out_tr,
                             in_tr=entrance_of(u)['type'], splash=is_splash, pad=pad)
        plan = plan or cand
        if not cand.fits:
            break
        if not _plan_misses(cand, req, (iw, ih), geo):
            plan = cand; break
    plan.labels = [r['label'] for r in req]
    _PLAN_CACHE[key] = plan
    return plan


# ---------------------------------------------------------------- clip registration
def gray_small(img, w=320):
    h = round(img.height * w / img.width)
    return np.asarray(img.convert('L').resize((w, h), Image.BILINEAR), dtype=np.float32)

def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = math.sqrt(float((a * a).sum() * (b * b).sum())) or 1.0
    return float((a * b).sum() / d)

def register(panel, frame):
    """Find where a clip frame sits on its panel: returns ((x, y, w, h) in panel px, score).
    Grok Imagine re-frames to its own aspect (736x400) so the clip covers a slightly
    different area than the 16:9 panel; we search scale + offset at low res."""
    P = gray_small(panel, 320)
    s = 320 / panel.width
    best = (-2, None)
    fa = frame.width / frame.height
    for wpx in range(280, 341, 2):
        hpx = round(wpx / fa)
        if hpx > P.shape[0] + 30:
            continue
        F = np.asarray(frame.convert('L').resize((wpx, hpx), Image.BILINEAR), dtype=np.float32)
        for ox in range(-(wpx - 320) if wpx > 320 else 0, (320 - wpx) + 1 if wpx <= 320 else 1, 2):
            for oy in range(min(0, P.shape[0] - hpx), max(0, P.shape[0] - hpx) + 1, 2):
                # overlap region
                x0, y0 = max(ox, 0), max(oy, 0)
                x1, y1 = min(ox + wpx, 320), min(oy + hpx, P.shape[0])
                if (x1 - x0) * (y1 - y0) < 0.8 * 320 * P.shape[0]:
                    continue
                sc = ncc(P[y0:y1, x0:x1], F[y0 - oy:y1 - oy, x0 - ox:x1 - ox])
                if sc > best[0]:
                    best = (sc, (ox / s, oy / s, wpx / s, hpx / s))
    return best[1], best[0]

# ---------------------------------------------------------------- clip frames
def first_frame(path):
    """The clip's real first frame (a single decoded frame), for the still->clip handoff check.
    read_clip samples a time window at the render fps, so its first sample can be several frames in."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                    '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(','))
    return Image.frombytes('RGB', (w, h), raw)


def read_clip(path, t_in, t_out, fps):
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                    'stream=width,height', '-of', 'csv=p=0', path],
                                   capture_output=True, text=True).stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t_in:.3f}', '-i', path, '-t', f'{t_out - t_in:.3f}',
                          '-vf', f'framerate=fps={fps}',   # blended rate conversion (24->30 without duplicate-frame judder)
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    arr = np.frombuffer(raw, np.uint8)[: n * w * h * 3].reshape(n, h, w, 3)
    return [Image.fromarray(a) for a in arr]

# ---------------------------------------------------------------- texture
@lru_cache(None)
def paper(W, H):
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    n = np.asarray(Image.fromarray(((n * 18) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    fine = rng.normal(0, 4, (H, W)).astype(np.float32)
    v = (n - 128) * 0.35 + fine
    base = np.array(PAPER, np.float32)[None, None, :] + v[..., None]
    return base.clip(0, 255).astype(np.uint8)

@lru_cache(None)
def dot_field(w, h, period=7.0):
    """Distance (in cell units, 0..~0.7) to nearest halftone dot centre on a 45-degree grid."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
    u = (xx * c + yy * s) / period
    v = (-xx * s + yy * c) / period
    du = u - np.round(u); dv = v - np.round(v)
    return np.sqrt(du * du + dv * dv)

def comic_finish(img, strength=0.22):
    """Light halftone (dots grow in shadows) + paper grain, so 480p clips sit with the ink art."""
    a = np.asarray(img, np.float32)
    h, w = a.shape[:2]
    lum = (a @ np.array([0.299, 0.587, 0.114], np.float32)) / 255.0
    r = 0.62 * np.sqrt(np.clip(1.0 - lum, 0, 1))          # dot radius from darkness
    d = dot_field(w, h)
    dots = np.clip((r - d) / 0.08, 0, 1)                    # anti-aliased dot mask
    a = a * (1.0 - strength * dots[..., None])
    grain = paper(w, h).astype(np.float32) / np.array(PAPER, np.float32)
    a = a * (0.94 + 0.06 * grain)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))

def upscale(img, box, size, sharpen=True):
    out = img.resize(size, Image.LANCZOS, box=tuple(box[:2]) + (box[0] + box[2], box[1] + box[3]))
    if sharpen:
        out = out.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    return out

# ---------------------------------------------------------------- lettering
def lyric_text(s):
    import re
    return re.sub(r'^\([^)]*\)\s*', '', s).replace('’', "'").upper()

def wrap(text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines

def caption_text_bounds(cap, slot, geo=None, safe=None):
    """Measured ink bounds (frame px) of every caption line, as draw_caption places them."""
    (x, y, w, h), lines, f, pad, lh = caption_box(cap, slot, geo, safe)
    out = []
    for i, l in enumerate(lines):
        b = f.getbbox(l)
        out.append((x + pad + b[0], y + pad + i * lh + b[1], b[2] - b[0], b[3] - b[1]))
    return out

LETTER_INSET = 16   # px kept clear between lettering and the panel's ink edge (border is 7-9 px)

_FIT_MASKS = {}
def fit_mask(geo):
    """bbox-sized bool mask of where lettering may sit: the panel's real clip path (slanted / tilted polygons,
    breakout burst) eroded by LETTER_INSET, so nothing touches or crosses a gutter."""
    key = (tuple(map(tuple, (tuple(map(tuple, p)) for p in geo['polys']))), geo['bbox'])
    if key not in _FIT_MASKS:
        m0 = slot_mask(geo)
        pad = LETTER_INSET + 4          # pad first: MinFilter replicates the image border, which would not erode it
        m = Image.new('L', (m0.width + 2 * pad, m0.height + 2 * pad), 0); m.paste(m0, (pad, pad))
        for _ in range(LETTER_INSET // 2):
            m = m.filter(ImageFilter.MinFilter(5))
        _FIT_MASKS[key] = np.asarray(m)[pad:-pad, pad:-pad] > 127
    return _FIT_MASKS[key]

def fits(rect, geo, safe=None, avoid=()):
    x, y, w, h = rect
    for a in avoid:   # other lettering of the same panel (+ a small gap)
        if x < a[0] + a[2] + 10 and a[0] < x + w + 10 and y < a[1] + a[3] + 10 and a[1] < y + h + 10:
            return False
    if safe and not (x >= safe[0] and y >= safe[1] and x + w <= safe[0] + safe[2] and y + h <= safe[1] + safe[3]):
        return False
    m = fit_mask(geo)
    bx, by = geo['bbox'][:2]
    x0, y0 = x - bx, y - by
    if x0 < 0 or y0 < 0 or x0 + w > m.shape[1] or y0 + h > m.shape[0]:
        return False
    return bool(m[y0:y0 + h, x0:x0 + w].all())

def place_in(rect, geo, safe=None, toward=None, avoid=()):
    """Smallest move of rect (towards the slot centre first) so it sits fully inside the panel clip path
    and the safe area. Returns the new (x, y) or None."""
    x, y, w, h = rect
    bx, by, bw, bh = geo['bbox']
    cx, cy = toward or (bx + bw / 2, by + bh / 2)
    best = None
    for r in range(0, int(max(bw, bh) * 0.5), 6):
        for dx in range(-r, r + 1, 6):
            for dy in (-r, r) if abs(dx) != r else range(-r, r + 1, 6):
                cand = (x + dx, y + dy, w, h)
                if fits(cand, geo, safe, avoid):
                    d = (dx * dx + dy * dy, -((cx - x) * dx + (cy - y) * dy))
                    if best is None or d < best[0]:
                        best = (d, (x + dx, y + dy))
        if best:
            return best[1]
    return None

def _caption_layout(cap, slot, scale=1.0):
    px = int(min(max(base_px(slot) * cap.get('size', 0.072), 32), 52) * scale)
    f = font(px)
    pad = int(px * 0.45)
    lines = wrap(cap['text'], f, slot[2] * cap.get('maxw', 0.6) * (1 if scale >= 1 else scale) - 2 * pad)
    lh = int(px * 1.08)
    # measured ink width (getbbox), so a glyph can never poke out of its box
    w = int(max(max(f.getlength(l), f.getbbox(l)[2]) for l in lines) + 2 * pad)
    h = int(lh * len(lines) + 2 * pad - (lh - px) + 4)
    a = cap.get('anchor', 'tl')
    x = slot[0] if a[1] == 'l' else slot[0] + slot[2] - w
    y = slot[1] if a[0] == 't' else slot[1] + slot[3] - h
    return (x, y, w, h), lines, f, pad, lh

def caption_box(cap, slot, geo=None, safe=None):
    """Returns (rect, lines, font, pad, lh) for a caption box pinned to a slot corner. With the panel geo,
    the box is auto-fitted: moved inward until it sits inside the panel's clip path (slanted gutters,
    tilted panels) and the safe area, shrinking the type when it cannot fit."""
    if geo is None:
        return _caption_layout(cap, slot)
    key = (cap['text'], cap.get('anchor'), cap.get('size'), cap.get('maxw'), tuple(slot), geo['bbox'], safe)
    if key in _CAP_CACHE:
        return _CAP_CACHE[key]
    res = None
    for scale in (1.0, 0.9, 0.8, 0.7, 0.6):
        (x, y, w, h), lines, f, pad, lh = _caption_layout(cap, slot, scale)
        pos = place_in((x, y, w, h), geo, safe)
        if pos:
            res = ((pos[0], pos[1], w, h), lines, f, pad, lh)
            break
    if res is None:
        res = _caption_layout(cap, slot, 0.6)
    _CAP_CACHE[key] = res
    return res
_CAP_CACHE = {}

def draw_caption(img, cap, slot, geo=None, safe=None):
    (x, y, w, h), lines, f, pad, lh = caption_box(cap, slot, geo, safe)
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=cap.get('fill') and tuple(cap['fill']) or CAPTION_FILL,
                outline=INK, width=5)
    for i, l in enumerate(lines):
        d.text((x + pad, y + pad + i * lh), l, font=f, fill=INK)

def _sfx_font(sfx, slot):
    px = int(base_px(slot) * sfx.get('size', 0.2))
    f = font(px)
    while f.getlength(sfx['text']) > slot[2] * 0.8 and px > 30:
        px -= 4; f = font(px)
    return f, px, max(4, px // 14)

def sfx_tile(sfx, slot, pad=None):
    """SFX lettering tile. Drawn on a generously padded canvas BEFORE rotating (Bangers is slanted: the last
    glyph and its 2x stroke overhang getlength() on the right; a tight canvas sliced the top-right corner
    off every SFX once rotated), rotated with expand=True, then cropped to the real ink. `pad` overrides the
    padding (QA renders an oversized reference and compares)."""
    f, px, sw = _sfx_font(sfx, slot)
    P = pad if pad is not None else int(0.3 * px) + 2 * sw + 8
    l, t, r, b = f.getbbox(sfx['text'], stroke_width=2 * sw)
    tw, th = (r - l) + 2 * P, (b - t) + 2 * P
    tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    o = (P - l, P - t)
    # outer white keyline, then black ink stroke, then colour fill
    d.text(o, sfx['text'], font=f, fill=(255, 255, 255, 255), stroke_width=2 * sw, stroke_fill=(255, 255, 255, 255))
    d.text(o, sfx['text'], font=f, fill=tuple(sfx.get('color', [255, 214, 0])) + (255,), stroke_width=sw, stroke_fill=INK + (255,))
    tile = tile.rotate(sfx.get('rot', -6), resample=Image.BICUBIC, expand=True)
    return tile.crop(tile.getbbox())

def sfx_ink_lost(sfx, slot):
    """QA: ink pixels the production tile loses vs an oversized-canvas reference (should be 0)."""
    a = np.asarray(sfx_tile(sfx, slot))[..., 3] > 24
    _, px, _ = _sfx_font(sfx, slot)
    b = np.asarray(sfx_tile(sfx, slot, pad=2 * px))[..., 3] > 24
    return int(b.sum()) - int(a.sum()), a.shape, b.shape

SFX_PEAK = 1.25    # the stamp-in animation starts at 125%

def sfx_rect(sfx, slot, scale=1.0, geo=None, safe=None, avoid=()):
    """avoid: caption rects of the same panel - the SFX (at its stamp-in peak) moves clear of them."""
    if geo is not None:
        avoid = tuple(tuple(a) for a in avoid)
        key = (sfx['text'], tuple(sfx['pos']), sfx.get('rot'), sfx.get('size'), tuple(slot), geo['bbox'], safe, avoid)
        if key not in _SFX_CACHE:
            tile0 = sfx_tile(sfx, slot)
            res = None
            for shrink in (1.0, 0.9, 0.8, 0.7, 0.6):
                (px_, py_, pw, ph), _ = sfx_rect(sfx, slot, SFX_PEAK * shrink)
                pos = place_in((px_, py_, pw, ph), geo, safe, avoid=avoid)
                if pos:
                    res = (pos[0] + pw / 2, pos[1] + ph / 2, shrink); break
            _SFX_CACHE[key] = res or (None, None, 0.6)
        cx, cy, shrink = _SFX_CACHE[key]
        tile = sfx_tile(sfx, slot)
        w, h = int(tile.width * scale * shrink), int(tile.height * scale * shrink)
        if cx is None:
            return sfx_rect(sfx, slot, scale * shrink)
        return (int(cx - w / 2), int(cy - h / 2), w, h), tile
    tile = sfx_tile(sfx, slot)
    w, h = int(tile.width * scale), int(tile.height * scale)
    cx = slot[0] + sfx['pos'][0] * slot[2]
    cy = slot[1] + sfx['pos'][1] * slot[3]
    m = 18  # keep the SFX inside its panel (layouts differ per orientation)
    cx = min(max(cx, slot[0] + m + w / 2), slot[0] + slot[2] - m - w / 2)
    cy = min(max(cy, slot[1] + m + h / 2), slot[1] + slot[3] - m - h / 2)
    return (int(cx - w / 2), int(cy - h / 2), w, h), tile

# ---------------------------------------------------------------- scene model
_SFX_CACHE = {}
DECOR_BURSTS = False
SFX_LIFE = 1.4         # s an SFX stays up after its stamp (timed to the action, then gone), last 0.25 s fades   # layout breakout starbursts are decoration: off (SFX must be motivated, never over a face)
_FACE_CACHE = {}

def _hit(a, b, m=0):
    return a[0] < b[2] + m and b[0] < a[0] + a[2] + m and a[1] < b[3] + m and b[1] < a[1] + a[3] + m

def sfx_faces(spec, orient, s):
    """Frame-px face boxes on screen when SFX s stamps in (scene time), from the shared face tracker."""
    key = (id(spec), orient, s['text'], s['at'])
    if key not in _FACE_CACHE:
        try:
            t0_ = T(spec, s['at'])
            fb = [b for k in range(7) for b in scene_faces(spec, orient, t0_ + SFX_LIFE * k / 6)]   # whole time it is up
        except Exception:
            fb = []
        _FACE_CACHE[key] = [tuple(int(v) for v in b) for b in fb]
    return _FACE_CACHE[key]

def sfx_place(spec, orient, s, u, slot, geo, S, scale=SFX_PEAK):
    """SFX rect + tile clear of captions AND faces (moved into open space); None = no open space, the SFX is dropped."""
    faces = sfx_faces(spec, orient, s)
    avoid = list(unit_caption_rects(u, slot, geo, S)) + [(f[0], f[1], f[2] - f[0], f[3] - f[1]) for f in faces]
    rect, tile = sfx_rect(s, slot, scale, geo, S, avoid)
    peak, _ = sfx_rect(s, slot, SFX_PEAK, geo, S, avoid)
    if any(_hit(peak, f) for f in faces):
        return None, None
    return rect, tile

def unit_caption_rects(u, slot, geo, safe):
    return [caption_box(c, slot, geo, safe)[0] for c in u.get('captions', [])]

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3

def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def text_items(spec, orient):
    """Every caption / SFX with its page rect and visible interval (scene seconds). Used by QA."""
    L = layout(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    S = TEXT_SAFE[orient]
    items = []
    tr = spec.get('transition')
    end = scene_len(spec)
    page_end = T(spec, tr['at']) - tr.get('dur', 0.4) if tr else end
    splash_t0 = T(spec, tr['at']) if tr else end
    for p in spec['panels']:
        slot = L[p['slot']]; geo = G[p['slot']]
        # the zoom target keeps its lettering through the zoom (Scene._frame letters_only=target) until the splash lands
        p_end = splash_t0 if tr and p['id'] == tr.get('panel') else page_end
        for c in p.get('captions', []):
            items.append({'who': f"{p['id']} caption '{c['text']}'", 'rect': caption_box(c, slot, geo, S)[0], 'geo': geo, 'unit': p['id'],
                          'from': T(spec, c.get('at', p['at'])), 'to': min(p_end, T(spec, c['until'])) if 'until' in c else p_end, 'slot': slot, 'kind': 'caption', 'obj': c})
        for s in p.get('sfx', []):
            items.append({'who': f"{p['id']} sfx '{s['text']}'", 'rect': sfx_rect(s, slot, SFX_PEAK, geo, S, unit_caption_rects(p, slot, geo, S))[0], 'geo': geo, 'unit': p['id'],
                          'from': T(spec, s['at']), 'to': page_end, 'slot': slot, 'kind': 'sfx', 'obj': s})
    sp = splash_unit(spec) or {}
    slot = L['splash']; geo = G['splash']
    for c in sp.get('captions', []):
        items.append({'who': f"{sp['id']} caption '{c['text']}'", 'rect': caption_box(c, slot, geo, S)[0], 'geo': geo, 'unit': sp.get('id'),
                      'from': max(splash_t0, T(spec, c.get('at', tr['at']))), 'to': min(end, T(spec, c['until'])) if 'until' in c else end, 'slot': slot, 'kind': 'caption', 'obj': c})
    for s in sp.get('sfx', []):
        items.append({'who': f"{sp['id']} sfx '{s['text']}'", 'rect': sfx_rect(s, slot, SFX_PEAK, geo, S, unit_caption_rects(sp, slot, geo, S))[0], 'geo': geo, 'unit': sp.get('id'),
                      'from': T(spec, s['at']), 'to': end, 'slot': slot, 'kind': 'sfx', 'obj': s})
    return items


_BURST_CACHE = {}
def burst_fill(geo):
    """Opaque RGBA tile (geo bbox size) for a breakout impact burst: radial white -> yellow -> orange gradient
    with halftone dots, alpha 255 everywhere inside the star outline (Jason: a hollow star cutout let the video
    show through and looked strange)."""
    k = tuple(map(tuple, geo['burst'])) + tuple(geo['bbox'])
    if k in _BURST_CACHE:
        return _BURST_CACHE[k]
    x0, y0, w, h = geo['bbox']
    pts = geo['burst']
    cx = sum(x for x, _ in pts) / len(pts) - x0; cy = sum(y for _, y in pts) / len(pts) - y0
    R = max(math.hypot(x - x0 - cx, y - y0 - cy) for x, y in pts) or 1
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.clip(np.hypot(xx - cx, yy - cy) / R, 0, 1)[..., None]
    c0, c1, c2 = np.array([255, 255, 240.]), np.array([255, 226, 40.]), np.array([255, 140, 20.])
    rgb = np.where(r < 0.5, c0 + (c1 - c0) * (r / 0.5), c1 + (c2 - c1) * ((r - 0.5) / 0.5))
    # halftone: dots grow toward the rim
    per = 9.0
    gx, gy = (xx % per) - per / 2, (yy % per) - per / 2
    dot = (np.hypot(gx, gy) < (r[..., 0] * per * 0.42))[..., None]
    rgb = np.where(dot, rgb * 0.82, rgb)
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
    tile = Image.fromarray(np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), np.asarray(m)]), 'RGBA')
    _BURST_CACHE[k] = tile
    return tile


def paint_burst(img, geo, w=7):
    """Solid burst fill + ink outline (used by Scene._paint and by the QA opacity check)."""
    tile = burst_fill(geo)
    img.paste(tile, tuple(geo['bbox'][:2]), tile)
    d = ImageDraw.Draw(img)
    pts = [(round(x), round(y)) for x, y in geo['burst']] + [(round(geo['burst'][0][0]), round(geo['burst'][0][1]))]
    d.line(pts, fill=INK, width=w, joint='curve')


def burst_see_through(geo, W, H, inset=6):
    """QA: count burst-interior pixels that change with what is underneath (should be 0 = fully opaque)."""
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in geo['burst']], fill=255)
    from PIL import ImageFilter
    inner = np.asarray(m.filter(ImageFilter.MinFilter(2 * inset + 1))) > 0
    a = Image.new('RGB', (W, H), (0, 0, 0)); b = Image.new('RGB', (W, H), (255, 0, 255))
    paint_burst(a, geo); paint_burst(b, geo)
    diff = np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).sum(2) > 0
    return int((diff & inner).sum()), int(inner.sum())


class Scene:
    """Builds frames for one orientation."""
    def __init__(self, spec, orient, fps=None):
        self.spec, self.orient = spec, orient
        self.W, self.H = SIZES[orient]
        self.fps = fps or spec.get('fps', 30)
        self.G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
        self.bgv = bg_video(spec, orient)
        self.paper = Image.new('RGB', (self.W, self.H), (0, 0, 0)) if self.bgv else Image.fromarray(paper(self.W, self.H))
        self.L = layout(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
        self.units = [dict(p, slotrect=self.L[p['slot']], geo=self.G[p['slot']]) for p in spec['panels']]
        sp = splash_unit(spec)
        self.splash = sp and dict(sp, slotrect=self.L['splash'], geo=self.G['splash'])
        for u in self.all_units():
            self._prep(u)
        self._page_cache = {}

    def all_units(self):
        return self.units + ([self.splash] if self.splash else [])

    def _prep(self, u):
        img = Image.open(resolve(self.spec, u['image'])).convert('RGB')
        x, y, w, h = u['geo']['bbox']
        u['mask'] = slot_mask(u['geo'])
        within = None
        if u.get('clip'):
            c = u['clip']
            path = resolve(self.spec, c['src'])
            frames = read_clip(path, c['in'], c['out'], self.fps)
            reg, score = register_cached(resolve(self.spec, u['image']), path, img, self.fps)
            u['reg'], u['regScore'] = reg, score
            # keep the crop inside the area the clip covers so static -> clip lines up exactly
            rx, ry, rw, rh = reg
            within = (max(rx, 0), max(ry, 0), min(rx + rw, img.width) - max(rx, 0), min(ry + rh, img.height) - max(ry, 0))
        focus = u.get('focus')
        if focus is None:
            focus = default_focus(img.width, img.height, w, h)
        u['focusUsed'] = focus
        # scene-aware crop: slide the cover crop so every focus region (faces, key action) sits inside the cell
        u['focusRegions'] = focus_regions(self.spec, u, img)
        crop, u['focusMiss'] = fit_crop(img.width, img.height, u['geo'], u['focusRegions'], within, tuple(focus))
        u['crop'] = crop
        u['_imgsize'] = img.size
        u['static'] = comic_finish(upscale(img, crop, (w, h), sharpen=False))
        u['src_img'] = img
        u['_within'] = within
        u['plan'] = unit_plan(self.spec, u, u['geo'], self.fps, u['focusRegions'], img.size, within)
        if u.get('eyeShift') and not u.get('clip'):
            u['static_alt'] = comic_finish(upscale(eye_shift_image(img, u['eyeShift']), crop, (w, h), sharpen=False))
        if u.get('clip'):
            rx, ry, rw, rh = u['reg']
            fw, fh = frames[0].size
            cbox = ((crop[0] - rx) * fw / rw, (crop[1] - ry) * fh / rh, crop[2] * fw / rw, crop[3] * fh / rh)
            u['clipbox'] = cbox
            u['clipscale'] = (fw / rw, fh / rh, rx, ry)
            u['raw'] = frames            # small source frames; upscaled + finished lazily (6 s clips at 1080p would not fit in RAM)
            u['size'] = (w, h)
            u['_cache'] = (None, None)

    def live_geo(self, u, t):
        """(geo, mask) of u at t: the static slot, or the living-panel cell (masks cached per size)."""
        if not is_reflow(self.spec) and fullframe_k(self.spec, u, t) <= 1e-4:
            return u['geo'], u['mask']
        geo, _ = reflow_geo(self.spec, self.orient, u, t)
        if geo is None:
            return None, None
        geo = dict(geo, bbox=[int(round(v)) for v in geo['bbox']])
        x, y, w, h = geo['bbox']
        geo['polys'] = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
        return geo, Image.new('L', (w, h), 255)

    def art(self, u, t, geo=None):
        """Panel art at scene time t. The per-cut camera move (unit_plan) moves a crop window over the art the whole
        time the panel is on screen: over the still before its clip starts, then over every clip frame (same
        window, so the hand-off never jumps). After the clip ends its tail ping-pongs in slow motion, so a panel
        never freezes."""
        plan = u.get('plan')
        geo = geo or u['geo']
        win = cell_window(plan, t, geo, u['_imgsize'], u.get('_within')) if plan else u['crop']
        size = tuple(geo['bbox'][2:])
        if not u.get('clip'):
            return comic_finish(upscale(u['src_img'], win, tuple(size), sharpen=False))
        t0 = T(self.spec, clip_start(self.spec, u))
        sx, sy, rx, ry = u['clipscale']
        cbox = ((win[0] - rx) * sx, (win[1] - ry) * sy, win[2] * sx, win[3] * sy)
        if t < t0:
            return comic_finish(upscale(u['src_img'], win, tuple(size), sharpen=False))
        ta, tb, wb = clip_loop(u['clip'], t - t0)
        fi = lambda tt: u['raw'][min(int(tt * self.fps), len(u['raw']) - 1)]
        src = fi(ta) if wb <= 0 else Image.blend(fi(ta), fi(tb), wb)
        fr = comic_finish(upscale(src, cbox, size))
        xf = 3 / self.fps
        if t - t0 < xf:
            st = comic_finish(upscale(u['src_img'], win, tuple(size), sharpen=False))
            return Image.blend(st, fr, (t - t0) / xf)
        return fr

    def _ink(self, img, r, w=7):
        x, y, ww, hh = r
        ImageDraw.Draw(img).rectangle([x - w + 1, y - w + 1, x + ww + w - 2, y + hh + w - 2], outline=INK, width=w)

    def _outline(self, img, poly, w=7, keyline=False):
        d = ImageDraw.Draw(img)
        pts = [(round(x), round(y)) for x, y in poly] + [(round(poly[0][0]), round(poly[0][1]))]
        if keyline:
            d.line(pts, fill=(250, 246, 236), width=w + 12, joint='curve')
        d.line(pts, fill=INK, width=w, joint='curve')

    def _paint(self, img, u, t, w=7):
        """Panel art masked to its slot shape, then ink (white keyline for insets laid over other panels)."""
        geo, mask = self.live_geo(u, t) if u is not self.splash else (u['geo'], u['mask'])
        if geo is None:
            return
        art = self.art(u, t, geo)
        x0, y0 = geo['bbox'][:2]
        if geo['keyline']:   # keyline first so it sits under the art edge and over the panel below
            for p in geo['polys']:
                self._outline(img, p, w, keyline=True)
        fl = self._flash(u, t)
        if fl > 0:   # impact flash: the panel art blows out to white on the hit, then decays
            art = Image.blend(art, Image.new('RGB', art.size, (255, 252, 235)), fl)
        img.paste(art, (x0, y0), mask)
        for p in geo['polys']:
            self._outline(img, p, w, keyline=geo['keyline'])
        if geo['burst']:     # impact burst breaking out over the border: SOLID fill, never a see-through cutout
            paint_burst(img, geo, w)

    def _letter(self, img, u, t):
        slot = u['slotrect']
        if u is not self.splash and fullframe_k(self.spec, u, t) > 1e-4:
            return      # SFX come in once the panel sits in its cell (lyrics float on the overlay regardless)
        if is_reflow(self.spec) and u is not self.splash:
            geo, _ = self.live_geo(u, t)
            if geo is None:
                return
            # SFX ride the live cell (quantised to 4 px so the lettering cache stays small)
            bb = tuple(int(4 * round(v / 4)) for v in geo['bbox'])
            slot = bb; u = dict(u, geo=dict(u['geo'], bbox=bb, polys=[[(bb[0], bb[1]), (bb[0] + bb[2], bb[1]), (bb[0] + bb[2], bb[1] + bb[3]), (bb[0], bb[1] + bb[3])]], inner=bb))
        S = TEXT_SAFE[self.orient]
        for c in ([] if self.spec.get('lyricOverlay', {}).get('enabled') else u.get('captions', [])) + \
                 ([c for c in u.get('captions', []) if not c.get('lyric')] if self.spec.get('lyricOverlay', {}).get('enabled') else []):
            if t >= max(T(self.spec, c.get('at', u['at'])), T(self.spec, u['at']) + entrance_of(u)['dur']) and ('until' not in c or t < T(self.spec, c['until'])):
                draw_caption(img, c, slot, u['geo'], S)
        for s in u.get('sfx', []):
            ts = max(T(self.spec, s['at']), T(self.spec, u['at']) + entrance_of(u)['dur'])
            if ts <= t < ts + SFX_LIFE:
                k = min((t - ts) * self.fps / 3, 1.0)
                scale = 1.25 - 0.25 * ease(k)          # quick 3-frame stamp, then still
                rect, tile = sfx_place(self.spec, self.orient, s, u, slot, u['geo'], S, scale)
                if rect is None:
                    continue   # no open space clear of the faces: drop it
                if (rect[2], rect[3]) != tile.size:
                    tile = tile.resize((rect[2], rect[3]), Image.BICUBIC)
                fo = min(1.0, (ts + SFX_LIFE - t) / 0.25)
                if fo < 1.0:
                    tile = tile.copy(); tile.putalpha(tile.getchannel('A').point(lambda v, fo=fo: int(v * fo)))
                img.paste(tile, rect[:2], tile)

    def background(self, t):
        if self.bgv:   # looping background video on the song clock (seamless across page turns)
            return self.bgv.at(t + self.spec['song']['start'], self.spec.get('loop', True)).copy()
        return self.paper.copy()

    def page(self, t, letters_only=None, letters=True):
        img = self.background(t)
        if is_reflow(self.spec):
            live = [(u, reflow_geo(self.spec, self.orient, u, t)[1]) for u in self.units if t >= T(self.spec, u['at'])]
            for u, _ in sorted(live, key=lambda x: (x[1], x[0]['at'])):
                ta = T(self.spec, u['at'])
                if t - ta < 0.12:      # quick fade-in at full frame, then it settles into the reflowed grid
                    fr = img.copy(); self._paint(fr, u, t)
                    img = Image.blend(img, fr, max(0.0, (t - ta) / 0.12))
                else:
                    self._paint(img, u, t)
            for u in (self.units if letters else []):
                if t >= T(self.spec, u['at']) and (letters_only is None or u['id'] == letters_only):
                    self._letter(img, u, t)
            return img
        zk = lambda u: FULLFRAME_Z if fullframe_k(self.spec, u, t) > 1e-4 else u['geo']['z']
        for u in sorted(self.units, key=zk):
            ta = T(self.spec, u['at'])
            if t < ta or (u.get('until') is not None and t >= T(self.spec, u['until']) + 0.5):
                continue   # not landed yet / replaced by the next shot in its cell (shot chains)
            en = entrance_of(u)
            if u.get('fullFrame') and fullframe_k(self.spec, u, t) > 1e-4:
                fr = img.copy(); self._paint(fr, u, t)
                img = Image.blend(img, fr, min(1.0, (t - ta) / 0.12)) if t - ta < 0.12 else fr
            elif t - ta < en['dur']:
                fr = img.copy(); self._paint(fr, u, t)
                img = panel_entrance(img, fr, u['geo']['bbox'], en['type'], (t - ta) / en['dur'], seed=int(ta * 10))
            else:
                self._paint(img, u, t)
        for u in (self.units if letters else []):
            if u.get('until') is not None and t >= T(self.spec, u['until']):
                continue   # its cell cut to the next shot: the old SFX go with it
            if t >= T(self.spec, u['at']) and (letters_only is None or u['id'] == letters_only):
                self._letter(img, u, t)
        return img

    def splash_frame(self, t, letters=True):
        img = self.background(t)
        u = self.splash
        self._paint(img, u, t, 9)
        if letters:
            self._letter(img, u, t)
        return img

    IMPACT_FLASH = 0.18     # s of white-out decay on an impact SFX
    IMPACT_SHAKE = 0.28     # s of screen shake
    def _impacts(self, u):
        return [T(self.spec, s_['at']) for s_ in u.get('sfx', []) if s_.get('impact')]

    def _flash(self, u, t):
        k = 0.0
        for ts in self._impacts(u):
            if ts <= t < ts + self.IMPACT_FLASH:
                k = max(k, 0.6 * (1 - (t - ts) / self.IMPACT_FLASH))
        return k

    def frame(self, t, letters=True):
        """Frame at scene time t. letters=False gives the art only (page transitions composite art, then lay the
        lettering back on unmoved and unmasked so it can never be clipped)."""
        img = self._frame(t, letters)
        tr = self.spec.get('transition')
        live = [self.splash] if (tr and self.splash and t >= T(self.spec, tr['at'])) else self.units
        amp = 0.0
        for u in live:
            for ts in self._impacts(u):
                if ts <= t < ts + self.IMPACT_SHAKE:
                    amp = max(amp, 1 - (t - ts) / self.IMPACT_SHAKE)
        if amp <= 0:
            return img
        # screen shake: decaying jitter, zoomed 2% so no edge shows
        A = 0.008 * self.W * amp
        n = (t * self.fps)
        dx, dy = A * math.sin(n * 2.7), A * math.cos(n * 3.9)
        zw, zh = self.W / 1.02, self.H / 1.02
        x0 = min(max((self.W - zw) / 2 + dx, 0), self.W - zw)
        y0 = min(max((self.H - zh) / 2 + dy, 0), self.H - zh)
        return img.resize((self.W, self.H), Image.BICUBIC, box=(x0, y0, x0 + zw, y0 + zh))

    def view_box(self, t):
        """Page-space box the frame at t shows (zoom transition), before shake. QA maps lettering through it."""
        tr = self.spec.get('transition')
        if not tr:
            return (0, 0, self.W, self.H)
        t_land = T(self.spec, tr['at']); dur = tr.get('dur', 0.4)
        if t >= t_land or t < t_land - dur:
            return (0, 0, self.W, self.H)
        target = next(u for u in self.units if u['id'] == tr['panel'])['geo']['bbox']
        a = self.W / self.H
        tx, ty, tw, th = target
        if tw / th > a:
            th2 = tw / a; ty -= (th2 - th) / 2; th = th2
        else:
            tw2 = th * a; tx -= (tw2 - tw) / 2; tw = tw2
        tx = min(max(tx, 0), self.W - tw); ty = min(max(ty, 0), self.H - th)
        k = ease_io((t - (t_land - dur)) / dur)
        return (tx * k, ty * k, self.W + (tw - self.W) * k, self.H + (th - self.H) * k)

    def shake_box(self, t):
        """Frame-space crop the shake applies at t (x0, y0, w, h), or None."""
        tr = self.spec.get('transition')
        live = [self.splash] if (tr and self.splash and t >= T(self.spec, tr['at'])) else self.units
        amp = 0.0
        for u in live:
            for ts in self._impacts(u):
                if ts <= t < ts + self.IMPACT_SHAKE:
                    amp = max(amp, 1 - (t - ts) / self.IMPACT_SHAKE)
        if amp <= 0:
            return None
        A = 0.008 * self.W * amp; n = t * self.fps
        zw, zh = self.W / 1.02, self.H / 1.02
        x0 = min(max((self.W - zw) / 2 + A * math.sin(n * 2.7), 0), self.W - zw)
        y0 = min(max((self.H - zh) / 2 + A * math.cos(n * 3.9), 0), self.H - zh)
        return (x0, y0, zw, zh)

    def _frame(self, t, letters=True):
        tr = self.spec.get('transition')
        if not tr:
            return self.page(t, letters=letters)
        t_land = T(self.spec, tr['at'])
        dur = tr.get('dur', 0.4)
        if t >= t_land:
            return self.splash_frame(t, letters)
        if t < t_land - dur:
            return self.page(t, letters=letters)
        # zoom into the target panel, then hard cut to the splash on the beat
        key = (round(t_land - dur, 4), letters)
        if key not in self._page_cache:
            # only the zoom target keeps its lettering: other panels' words would be sliced by the frame edge
            self._page_cache[key] = self.page(t_land - dur, letters_only=tr['panel'], letters=letters)
        src = self._page_cache[key]
        target = next(u for u in self.units if u['id'] == tr['panel'])['geo']['bbox']
        a = self.W / self.H
        tx, ty, tw, th = target
        if tw / th > a:
            th2 = tw / a; ty -= (th2 - th) / 2; th = th2
        else:
            tw2 = th * a; tx -= (tw2 - tw) / 2; tw = tw2
        tx = min(max(tx, 0), self.W - tw); ty = min(max(ty, 0), self.H - th)
        k = ease_io((t - (t_land - dur)) / dur)
        box = (tx * k, ty * k, self.W + (tw - self.W) * k, self.H + (th - self.H) * k)
        return src.resize((self.W, self.H), Image.LANCZOS, box=(box[0], box[1], box[0] + box[2], box[1] + box[3]))


# ---------------------------------------------------------------- end card (Jason's rule: every video + Short)
ENDCARD_DEFAULT = {'enabled': True, 'seconds': 3.0,
                   'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!']}
TEXT_SAFE = CONTENT       # panel lettering must stay on the printed page area (inside the paper margin)
SAFE = {'landscape': (96, 54, 1824, 1026), 'vertical': (54, 96, 1026, 1824)}   # 5% title-safe (x0, y0, x1, y1)
TAIL_FADE = 2.5            # seconds of natural fade at the very end of the audio


def endcard(spec):
    ec = dict(ENDCARD_DEFAULT, **(spec.get('endCard') or {}))
    return ec if ec.get('enabled', True) and ec.get('seconds', 0) > 0 else None


def endcard_layout(ec, orient):
    """Measured lettering for the end card: [(rect, text, font, stroke, fill, pad)], all rects in frame px.
    Each line sits on its own caption box; the text is fitted so its measured bbox stays inside the safe area."""
    W, H = SIZES[orient]
    sx0, sy0, sx1, sy1 = SAFE[orient]
    maxw = (sx1 - sx0) * 0.9
    fills = [tuple(c) for c in ec['fills']] if ec.get('fills') else [CAPTION_FILL, (255, 70, 90)]
    out, boxes = [], []
    for i, text in enumerate(ec['lines']):
        # prefer one line (shrinking to a floor), then a balanced two-line wrap; text is measured with getbbox
        px, floor = (104, 76) if orient == 'landscape' else (100, 100)
        f = font(px)
        while f.getbbox(text)[2] - f.getbbox(text)[0] > maxw - px and px > floor:
            px -= 4; f = font(px)
        lines = [text]
        if f.getbbox(text)[2] - f.getbbox(text)[0] > maxw - px:
            ws = text.split()
            k = min(range(1, len(ws)), key=lambda k: abs(len(' '.join(ws[:k])) - len(' '.join(ws[k:]))))
            lines = [' '.join(ws[:k]), ' '.join(ws[k:])]
            while max(f.getbbox(l)[2] - f.getbbox(l)[0] for l in lines) > maxw - px and px > 30:
                px -= 4; f = font(px)
        pad = int(px * 0.4)
        lh = int(px * 1.1)
        tw = max(f.getbbox(l)[2] - f.getbbox(l)[0] for l in lines)
        boxes.append((lines, f, px, pad, lh, tw + 2 * pad, lh * len(lines) + 2 * pad, fills[i % 2]))
    gap = 70
    total = sum(b[6] for b in boxes) + gap * (len(boxes) - 1)
    y = (H - total) // 2
    for k, (lines, f, px, pad, lh, w, h, fill) in enumerate(boxes):
        x = (W - w) // 2 + (-30 if k % 2 == 0 else 30) * (orient == 'landscape')
        out.append({'rect': (x, y, w, h), 'lines': lines, 'font': f, 'pad': pad, 'lh': lh, 'fill': fill, 'rot': -3 if k % 2 == 0 else 2})
        y += h + gap
    return out


def endcard_text_bounds(item):
    """Measured ink bounds of every line (frame px) for QA."""
    x, y, w, h = item['rect']
    res = []
    for i, l in enumerate(item['lines']):
        b = item['font'].getbbox(l)
        lx = x + (w - (b[2] - b[0])) // 2 - b[0]
        ly = y + item['pad'] + i * item['lh']
        res.append((lx + b[0], ly + b[1], b[2] - b[0], b[3] - b[1]))
    return res


def endcard_frame(base, orient, ec, t=0.0):
    """End card over the LIVE last page (base keeps moving), dimmed under halftone, with the two lettering boxes on
    top; the boxes bob a few px and the sunburst breathes so the card itself is never static either."""
    W, H = SIZES[orient]
    if isinstance(base, np.ndarray):
        base = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGB')
    img = Image.blend(base.convert('RGB'), Image.new('RGB', (W, H), (20, 8, 40)), 0.62)
    dots = dot_field(W, H, 9.0)
    arr = np.asarray(img, np.float32)
    arr = arr * (1 - 0.25 * (dots < 0.22)[..., None])
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if ec.get('sunburst'):
        draw_sunburst(img, W / 2, H / 2, ec['sunburst'].get('color', [230, 180, 70]), ec['sunburst'].get('alpha', 0.8) * (0.85 + 0.15 * math.sin(t * 2.4)))
    for j, it in enumerate(endcard_layout(ec, orient)):
        it = dict(it, rect=[it['rect'][0], int(it['rect'][1] + 5 * math.sin(t * 2.2 + j * 1.7)), it['rect'][2], it['rect'][3]])
        x, y, w, h = it['rect']
        tile = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        d.rectangle([14, 14, w + 13, h + 13], fill=INK + (255,))             # drop shadow
        d.rectangle([4, 4, w + 3, h + 3], fill=it['fill'] + (255,), outline=INK + (255,), width=6)
        for i, l in enumerate(it['lines']):
            b = it['font'].getbbox(l)
            d.text((4 + (w - (b[2] - b[0])) // 2 - b[0], 4 + it['pad'] + i * it['lh']), l, font=it['font'], fill=INK + (255,))
        tile = tile.rotate(it['rot'], resample=Image.BICUBIC, expand=True)
        img.paste(tile, (x + w // 2 + 6 - tile.width // 2, y + h // 2 + 6 - tile.height // 2), tile)
    return img


def endcard_bounds_rotated(item):
    """Bounding box of the rotated lettering box as drawn (frame px)."""
    x, y, w, h = item['rect']
    import math
    a = math.radians(abs(item['rot']))
    rw = (w + 20) * math.cos(a) + (h + 20) * math.sin(a)
    rh = (w + 20) * math.sin(a) + (h + 20) * math.cos(a)
    cx, cy = x + w / 2 + 6, y + h / 2 + 6
    return (int(cx - rw / 2), int(cy - rh / 2), int(rw), int(rh))


def lettering_layer(spec, orient, unit_id):
    """RGBA layer with only one unit's lettering at its peak (captions on, SFX at the stamp-in peak).
    Used by QA's pixel check: any lettering pixel outside the panel clip path is clipped/overhanging."""
    W, H = SIZES[orient]
    L = layout(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    units = [dict(p) for p in spec['panels']] + ([dict(splash_unit(spec), slot='splash')] if splash_unit(spec) else [])
    u = next(x for x in units if x['id'] == unit_id)
    slot, geo, S = L[u['slot']], G[u['slot']], TEXT_SAFE[orient]
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for c in u.get('captions', []):
        draw_caption(img, c, slot, geo, S)
    for s_ in u.get('sfx', []):
        rect, tile = sfx_rect(s_, slot, SFX_PEAK, geo, S, unit_caption_rects(u, slot, geo, S))
        tile = tile.resize((rect[2], rect[3]), Image.BICUBIC)
        img.alpha_composite(tile, (max(rect[0], 0), max(rect[1], 0))) if rect[0] >= 0 and rect[1] >= 0 else img.paste(tile, rect[:2], tile)
    return np.asarray(img)[..., 3] > 24, geo


def clip_path_mask(geo, W, H, inset=4):
    """Full-frame bool mask of a panel's clip path (polygons + burst), eroded by `inset` px (inside the ink)."""
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    for p in geo['polys'] + ([geo['burst']] if geo['burst'] else []):
        d.polygon([(x, y) for x, y in p], fill=255)
    for _ in range(inset // 2):
        m = m.filter(ImageFilter.MinFilter(5))
    return np.asarray(m) > 127


# ---------------------------------------------------------------- title logo intro (standing rule: default ON)
# Every Progressive Slop video and Short opens with a bold text logo for the song title: chunky comic/arcade
# lettering, chrome bevel, heavy ink outline, neon glow, slamming in on the first downbeat with an impact flash,
# a little screen shake and sparkles. It is overlaid on the opening frames (the music starts immediately in most
# songs; with a long silent lead-in the slam still waits for the first downbeat).
INTRO_DEFAULT = {'enabled': True, 'seconds': 2.6, 'title': None, 'subtitle': 'PROGRESSIVE SLOP PRESENTS',
                 'glow': [255, 60, 200], 'glow2': [60, 230, 255], 'chrome': [[255, 255, 255], [190, 215, 255], [120, 135, 170], [30, 36, 60], [150, 170, 210], [245, 250, 255]],
                 'subColor': [255, 228, 122], 'rot': -4, 'width': 0.78, 'dim': 0.45}
INTRO_PEAK = 1.18      # slam-in starts at 118% and settles to 100%
INTRO_FLASH, INTRO_SHAKE, INTRO_FADE = 0.16, 0.32, 0.35


def intro(spec):
    """Intro config, or None when a spec explicitly disables it (QA fails that: the intro is required)."""
    ic = dict(INTRO_DEFAULT, **(spec.get('intro') or {}))
    if not ic.get('title'):
        ic['title'] = re.split(r'\s+[-\u2013\u2014]\s+', spec.get('title', 'UNTITLED'))[0]
    ic['title'] = ic['title'].upper()
    if ic.get('logotype'):   # per-song designed logotype (required, QA): resolved once so the tile cache can load it
        ic['logotype'] = resolve(spec, ic['logotype']) if '_dir' in spec or spec.get('assetsDir') or os.environ.get('COMIC_ASSETS') else ic['logotype']
    return ic if ic.get('enabled', True) and ic.get('seconds', 0) > 0 else None


def intro_slam(spec, t0=None):
    """Video-relative time of the slam: the first downbeat at/after the video's first song second."""
    s0 = spec['song']['start'] if t0 is None else t0
    beats = [b for b in song_beats(spec) if b >= s0 + 0.15]
    return round(beats[0] - s0, 3) if beats else 0.4


STILL_MOTIONS = ('push_in', 'pull_out', 'pan_left', 'pan_right', 'drift_up')


def still_motion_frame(spec, u, t):
    """Motion preset for a still panel (no Grok clip yet): a slow eased push-in / pull-out / pan of the finished
    static art inside its cell, starting on the same beat a clip would (one-beat anticipation hold). The zoom is
    centred on the required focus regions so they stay in the cell; `amount` (default 0.06) caps the scale change.
    Spec: panels[i].stillMotion = {"type": push_in|pull_out|pan_left|pan_right|drift_up, "amount": 0.06, "dur": 6}.
    Drop it (or add a "clip") to swap in an animated clip later."""
    sm = u['stillMotion']; img = u['static']
    beats = [b for b in song_beats(spec) if b > u['at'] + 0.05]
    hold = spec.get('defaults', {}).get('holdBeats', DEFAULT_HOLD_BEATS)
    t0 = T(spec, beats[hold - 1] if len(beats) >= hold else u['at'] + 0.45)
    p = ease_io(min(1.0, max(0.0, (t - t0) / sm.get('dur', 6.0))))
    a = sm.get('amount', 0.06); typ = sm.get('type', 'push_in')
    W, H = img.size
    # anchor: centre of the required focus regions mapped into the static (crop) space
    cx, cy = 0.5, 0.5
    req = [r for r in u.get('focusRegions') or [] if r.get('required', True)]
    if req and u.get('crop') and u.get('_imgsize'):
        iw, ih = u['_imgsize']; X, Y, CW, CH = u['crop']
        xs = [((r['box'][0] + r['box'][2]) / 2 * iw - X) / CW for r in req]; ys = [((r['box'][1] + r['box'][3]) / 2 * ih - Y) / CH for r in req]
        cx, cy = min(max(sum(xs) / len(xs), 0.3), 0.7), min(max(sum(ys) / len(ys), 0.3), 0.7)
    if typ == 'push_in':
        z = 1 - a * p
    elif typ == 'pull_out':
        z = 1 - a * (1 - p)
    else:
        z = 1 - a
    zw, zh = W * z, H * z
    x0 = cx * W - zw * cx; y0 = cy * H - zh * cy
    if typ in ('pan_left', 'pan_right'):
        x0 = (W - zw) * (p if typ == 'pan_left' else 1 - p)
    elif typ == 'drift_up':
        y0 = (H - zh) * (1 - p)
    x0 = min(max(x0, 0), W - zw); y0 = min(max(y0, 0), H - zh)
    if z >= 0.9995:
        return img
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + zw, y0 + zh))


def draw_sunburst(img, cx, cy, color, alpha=1.0, rays=32, r0=0.0):
    """Art-deco sunburst: alternating translucent gold wedges + thin rays from (cx, cy), under the logo / end card."""
    if alpha <= 0:
        return img
    W, H = img.size
    R = math.hypot(W, H)
    lay = Image.new('L', (W, H), 0); d = ImageDraw.Draw(lay)
    for k in range(rays):
        a0 = 2 * math.pi * k / rays; a1 = 2 * math.pi * (k + 0.5) / rays
        d.polygon([(cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1)), (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1))], fill=70)
        d.line([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0))], fill=170, width=3)
    for rr in (0.12, 0.125, 0.2):
        r_ = rr * R; d.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], outline=150, width=3)
    lay = lay.point(lambda v: int(v * alpha))
    img.paste(Image.new('RGB', (W, H), tuple(color)), (0, 0), lay)
    return img


def _intro_fonts(ic, orient):
    W, H = SIZES[orient]
    maxw = W * ic.get('width', 0.78) / INTRO_PEAK
    words = ic['title'].split()
    k = min(range(1, max(2, len(words))), key=lambda k: abs(len(' '.join(words[:k])) - len(' '.join(words[k:]))))
    lines = [ic['title']] if orient == 'landscape' or len(words) < 2 else [' '.join(words[:k]), ' '.join(words[k:])]
    if ic.get('lines'):   # explicit stacked lines, e.g. ["CONCRETE", "JUNGLE", "COLD"] (both orientations)
        lines = [l.upper() for l in ic['lines']]
    px = int(H * (0.26 if orient == 'landscape' else 0.15))
    while px > 40 and max(font(px).getlength(l) for l in lines) + 2 * max(6, px // 9) > maxw:
        px -= 4
    return lines, px, max(6, px // 9), int(px * 0.24)


def intro_tile(ic, orient, pad=None):
    """RGBA logo tile (title + optional subtitle, glow included), drawn on a padded canvas, rotated with
    expand=True and cropped to its ink - the same overhang-safe recipe as sfx_tile. `pad` = oversized QA reference."""
    from PIL import ImageFilter
    lines, px, sw, spx = _intro_fonts(ic, orient)
    f, fs = font(px), font(spx)
    glow_r = max(8, px // 7)
    P = pad if pad is not None else int(0.3 * px) + 3 * sw + 3 * glow_r
    sub = ic.get('subtitle')
    boxes = [f.getbbox(l, stroke_width=2 * sw) for l in lines]
    lw = max(b[2] - b[0] for b in boxes); lh = [b[3] - b[1] for b in boxes]
    sb = fs.getbbox(sub, stroke_width=max(3, spx // 8)) if sub else (0, 0, 0, 0)
    gap = int(px * 0.08)
    tw = max(lw, sb[2] - sb[0]) + 2 * P
    drip = ic.get('style') == 'drip'
    D = int(px * 0.5) if drip else 0          # room under the last line for ink drips
    th = (sb[3] - sb[1] + gap if sub else 0) + sum(lh) + gap * (len(lines) - 1) + 2 * P + D
    text = Image.new('L', (tw, th), 0); outer = Image.new('L', (tw, th), 0); fill = Image.new('L', (tw, th), 0)
    dt, do, df = ImageDraw.Draw(text), ImageDraw.Draw(outer), ImageDraw.Draw(fill)
    y = P
    subpos = None
    if sub:
        subpos = ((tw - (sb[2] - sb[0])) // 2 - sb[0], y - sb[1]); y += sb[3] - sb[1] + gap
    pos = []
    for l, b in zip(lines, boxes):
        o = ((tw - (b[2] - b[0])) // 2 - b[0], y - b[1]); pos.append((l, o)); y += b[3] - b[1] + gap
    for l, o in pos:
        do.text(o, l, font=f, fill=255, stroke_width=2 * sw, stroke_fill=255)
        dt.text(o, l, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        df.text(o, l, font=f, fill=255)
    if drip:   # dripping ink: runs hanging off the glyph bottoms (fill, keyline and outline all follow them)
        rnd = np.random.default_rng(ic.get('seed', 13))
        fa0 = np.asarray(fill)
        for l, o in pos:
            yb = o[1] + f.getbbox('H')[3]      # baseline (descending punctuation would hog the drips)
            cols = np.nonzero(fa0[max(0, yb - 4)] > 128)[0]
            if not len(cols):
                continue
            for x in rnd.choice(cols, size=min(len(cols), max(4, int(len(l.replace(' ', '')) * 1.2))), replace=False):
                ln = rnd.uniform(0.1, 0.42) * px * (D / (px * 0.5) if l == pos[-1][0] else 0.55)
                w = rnd.uniform(0.05, 0.1) * px
                for dd, extra in ((df, 0), (dt, sw), (do, 2 * sw)):
                    dd.rounded_rectangle([x - w / 2 - extra, yb - w - extra, x + w / 2 + extra, yb + ln + extra], radius=w / 2 + extra, fill=255)
                    r = w * 0.8 + extra
                    dd.ellipse([x - r, yb + ln - r, x + r, yb + ln + r], fill=255)
    # neon glow (two colours), white keyline, ink outline, chrome bevel gradient fill with a hot specular band
    tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    for col, r, k in ((ic['glow2'], glow_r * 2, 0.8), (ic['glow'], glow_r, 1.0)):
        g = outer.filter(ImageFilter.GaussianBlur(r)).point(lambda v: min(255, int(v * 2.2 * k)))
        tile.alpha_composite(Image.merge('RGBA', [Image.new('L', (tw, th), c) for c in col] + [g]))
    tile.alpha_composite(Image.merge('RGBA', [Image.new('L', (tw, th), 255)] * 3 + [outer]))
    tile.alpha_composite(Image.merge('RGBA', [Image.new('L', (tw, th), c) for c in INK] + [text]))
    # chrome: sky-to-horizon gradient per text line (bright top, dark horizon just under the middle, bright floor)
    stops = np.array(ic['chrome'], np.float32)
    xs = np.array([0, 0.3, 0.5, 0.53, 0.8, 1.0]) if len(stops) == 6 else np.linspace(0, 1, len(stops))
    rgb = np.zeros((th, tw, 3), np.float32)
    for (l, o), b in zip(pos, boxes):
        y0, y1 = o[1] + f.getbbox(l)[1], o[1] + f.getbbox(l)[3]
        ys = np.clip((np.arange(th) - y0) / max(1, y1 - y0), 0, 1)
        g = np.stack([np.interp(ys, xs, stops[:, c]) for c in range(3)], -1)
        m = (np.arange(th) >= y0 - sw) & (np.arange(th) <= y1 + sw + (int(px * 0.5) if drip else 0))
        rgb[m] = g[m][:, None, :]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    fill_rgba = Image.fromarray(np.dstack([rgb, np.asarray(fill)]), 'RGBA')
    # bevel: light top-left edge / dark bottom-right edge inside the glyphs
    fa = np.asarray(fill).astype(np.int16)
    edge_hi = np.clip(fa - np.roll(np.roll(fa, 3, 0), 3, 1), 0, 255).astype(np.uint8)
    edge_lo = np.clip(fa - np.roll(np.roll(fa, -3, 0), -3, 1), 0, 255).astype(np.uint8)
    tile.alpha_composite(fill_rgba)
    tile.alpha_composite(Image.merge('RGBA', [Image.new('L', (tw, th), 255)] * 3 + [Image.fromarray(edge_hi)]))
    tile.alpha_composite(Image.merge('RGBA', [Image.new('L', (tw, th), 40)] * 3 + [Image.fromarray((edge_lo * 0.7).astype(np.uint8))]))
    if sub:
        ssw = max(3, spx // 8)
        ImageDraw.Draw(tile).text(subpos, sub, font=fs, fill=tuple(ic['subColor']) + (255,), stroke_width=ssw, stroke_fill=INK + (255,))
    tile = tile.rotate(ic.get('rot', -4), resample=Image.BICUBIC, expand=True)
    bb = Image.fromarray((np.asarray(tile)[..., 3] > 8).astype(np.uint8) * 255).getbbox()
    return tile.crop(bb)


def intro_ink_lost(ic, orient):
    """QA: logo ink (alpha > 24) the production tile loses vs an oversized-canvas reference (should be 0)."""
    a = np.asarray(intro_tile(ic, orient))[..., 3] > 24
    _, px, _, _ = _intro_fonts(ic, orient)
    b = np.asarray(intro_tile(ic, orient, pad=2 * px))[..., 3] > 24
    return int(b.sum()) - int(a.sum())


_INTRO_CACHE = {}
def logotype_tile(path, max_w=1600):
    """Designed logotype art (JPG/PNG) -> RGBA tile: transparent where the flat outer background is (flood fill
    from the border, so the badge's own dark interior stays opaque), trimmed, soft 2 px edge."""
    from PIL import ImageFilter
    from scipy import ndimage
    im = Image.open(path).convert('RGBA')
    if im.getchannel('A').getextrema()[0] < 250:      # already has alpha
        a = np.asarray(im.getchannel('A')) > 8
    else:
        rgb = np.asarray(im.convert('RGB'), np.float32)
        bg = np.median(np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]), axis=0)
        near = np.abs(rgb - bg).max(2) < 28
        lab, _ = ndimage.label(near)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        a = ~np.isin(lab, list(edge))
        a = ndimage.binary_fill_holes(ndimage.binary_opening(a, iterations=2))
    m = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(m)
    bb = m.point(lambda v: 255 if v > 20 else 0).getbbox()
    im = im.crop(bb)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    return im


def _intro_tile_cached(ic, orient):
    k = (json.dumps(ic, sort_keys=True), orient)
    if k not in _INTRO_CACHE:
        _INTRO_CACHE[k] = logotype_tile(ic['logotype']) if ic.get('logotype') else intro_tile(ic, orient)
    return _INTRO_CACHE[k]


def intro_state(ic, orient, t, ts):
    """(scale, alpha, flash, shake_amp) of the logo at video time t (slam at ts), or None when not shown."""
    end = ts + ic['seconds']
    if t < ts - 0.12 or t >= end:
        return None
    if t < ts:   # 4-frame drop-in from the peak size
        k = (t - (ts - 0.12)) / 0.12
        return INTRO_PEAK - (INTRO_PEAK - 1.0) * k * k, k, 0.0, 0.0
    a = 1.0 if t < end - INTRO_FADE else (end - t) / INTRO_FADE
    sc = 1.0   # lands at 100% on the beat
    flash = 0.75 * (1 - (t - ts) / INTRO_FLASH) if t < ts + INTRO_FLASH else 0.0
    shake = 1 - (t - ts) / INTRO_SHAKE if t < ts + INTRO_SHAKE else 0.0
    return sc, a, flash, shake


def intro_rect(ic, orient, scale=1.0):
    """Frame-space rect of the logo tile at `scale` (centred, a little above middle)."""
    W, H = SIZES[orient]
    tile = _intro_tile_cached(ic, orient)
    x0, y0, x1, y1 = SAFE[orient]
    fit = min(1.0, 0.96 * (x1 - x0) / (tile.width * INTRO_PEAK), 0.8 * (y1 - y0) / (tile.height * INTRO_PEAK))
    w, h = tile.width * fit * scale, tile.height * fit * scale
    cy = H * (0.46 if orient == 'landscape' else 0.42)
    return [W / 2 - w / 2, cy - h / 2, w, h]


def intro_shake_box(orient, t, amp, fps=30):
    if amp <= 0:
        return None
    W, H = SIZES[orient]
    A = 0.006 * W * amp; n = t * fps
    zw, zh = W / 1.02, H / 1.02
    x0 = min(max((W - zw) / 2 + A * math.sin(n * 3.1), 0), W - zw)
    y0 = min(max((H - zh) / 2 + A * math.cos(n * 4.3), 0), H - zh)
    return (x0, y0, zw, zh)


def _sparkles(img, rect, t, ts, seed=7):
    """Star sparkles bursting out of the logo for ~1.2 s after the slam."""
    age = t - ts
    if age < 0 or age > 1.2:
        return
    d = ImageDraw.Draw(img)
    rnd = np.random.default_rng(seed)
    x, y, w, h = rect
    for _ in range(36):
        ang = rnd.uniform(0, 2 * math.pi); sp = rnd.uniform(0.25, 0.75); ph = rnd.uniform(0, 0.3)
        a = age - ph
        if a < 0:
            continue
        cx = x + w / 2 + math.cos(ang) * (w * 0.45 + sp * a * w * 0.6)
        cy = y + h / 2 + math.sin(ang) * (h * 0.45 + sp * a * h * 0.9)
        r = max(0.0, (1 - a / 0.9)) * rnd.uniform(8, 18)
        if r < 1:
            continue
        col = (255, 255, 255) if rnd.random() < 0.5 else (255, 240, 140)
        d.polygon([(cx, cy - 2.6 * r), (cx + 0.5 * r, cy - 0.5 * r), (cx + 2.6 * r, cy), (cx + 0.5 * r, cy + 0.5 * r),
                   (cx, cy + 2.6 * r), (cx - 0.5 * r, cy + 0.5 * r), (cx - 2.6 * r, cy), (cx - 0.5 * r, cy - 0.5 * r)], fill=col)


LOGO_RAYS, LOGO_DRAW, LOGO_SHINE, LOGO_GLINT = (0.0, 0.55), (0.12, 0.80), (0.55, 1.15), 1.2


def logotype_intro_frame(base, orient, ic, t, ts):
    """Logotype build-in over the (moving) opening frame, starting on the slam beat ts:
    gold sunburst rays sweep round (0-0.55 s) -> the badge draws on clockwise from 12 o'clock (0.12-0.8 s) ->
    a shine band sweeps across the letters (0.55-1.15 s) -> a light glint pops on the top (1.2 s) -> a slow 3 %
    push for the rest of the hold -> fade. Never static: the push runs the whole hold and the page moves under it."""
    a = t - ts; end = ic['seconds']
    if a < 0 or a >= end:
        return base
    W, H = SIZES[orient]
    img = base.convert('RGB').copy()
    fade = 1.0 if a < end - INTRO_FADE else max(0.0, (end - a) / INTRO_FADE)
    img = Image.blend(img, Image.new('RGB', (W, H), (8, 6, 16)), ic.get('dim', 0.45) * min(1.0, a / 0.25) * fade)
    tile = _intro_tile_cached(ic, orient)
    sc = 0.97 + 0.03 * min(1.0, a / end)              # slow push the whole hold
    r = intro_rect(ic, orient, sc)
    cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
    def sweep_mask(size, ang, cxy):
        w_, h_ = size
        yy, xx = np.mgrid[0:h_, 0:w_].astype(np.float32)
        th = (np.degrees(np.arctan2(xx - cxy[0], -(yy - cxy[1]))) + 360) % 360   # 0 at 12 o'clock, clockwise
        return np.clip((ang - th) / 12.0, 0, 1)
    # 1) rays sweep
    k = min(1.0, max(0.0, (a - LOGO_RAYS[0]) / (LOGO_RAYS[1] - LOGO_RAYS[0])))
    if ic.get('sunburst') is not False and k > 0:
        lay = Image.new('RGB', (W, H), (0, 0, 0))
        col = (ic.get('sunburst') or {}).get('color', [230, 180, 70])
        draw_sunburst(lay, cx, cy, col, 1.0)
        m = sweep_mask((W, H), 360 * ease_io(k) + 12, (cx, cy)) * 0.55 * fade
        arr = np.asarray(img, np.float32); L = np.asarray(lay, np.float32)
        img = Image.fromarray(np.clip(arr + L * m[..., None] * 0.6, 0, 255).astype(np.uint8))
    # 2) badge draws on
    kd = min(1.0, max(0.0, (a - LOGO_DRAW[0]) / (LOGO_DRAW[1] - LOGO_DRAW[0])))
    if kd <= 0:
        return img
    tl = tile.resize((max(1, int(r[2])), max(1, int(r[3]))), Image.LANCZOS)
    al = np.asarray(tl.getchannel('A'), np.float32) / 255
    if kd < 1:
        al = al * sweep_mask(tl.size, 360 * ease_io(kd) + 12, (tl.width / 2, tl.height / 2))
    # 3) shine band (diagonal, additive, inside the badge)
    ks = (a - LOGO_SHINE[0]) / (LOGO_SHINE[1] - LOGO_SHINE[0])
    rgb = np.asarray(tl.convert('RGB'), np.float32)
    if 0 <= ks <= 1:
        yy, xx = np.mgrid[0:tl.height, 0:tl.width].astype(np.float32)
        pos = (xx + 0.45 * yy) / (tl.width + 0.45 * tl.height)
        band = np.exp(-((pos - (-0.15 + 1.3 * ks)) / 0.05) ** 2)
        rgb = rgb + band[..., None] * np.array([255, 235, 170], np.float32) * 0.55
    tlr = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert('RGBA')
    tlr.putalpha(Image.fromarray(np.clip(al * fade * 255, 0, 255).astype(np.uint8)))
    img.paste(tlr, (int(round(r[0])), int(round(r[1]))), tlr)
    # 4) glint: a 4-point star on the badge's top centre (spire), pops and fades
    kg = (a - LOGO_GLINT) / 0.45
    if 0 <= kg <= 1:
        d = ImageDraw.Draw(img, 'RGBA'); gx, gy = cx, r[1] + r[3] * 0.18
        s_ = (1 - abs(2 * kg - 1)) * r[3] * 0.10
        al8 = int(230 * (1 - abs(2 * kg - 1)) * fade)
        d.polygon([(gx, gy - s_), (gx + s_ * 0.16, gy), (gx, gy + s_), (gx - s_ * 0.16, gy)], fill=(255, 250, 225, al8))
        d.polygon([(gx - s_, gy), (gx, gy - s_ * 0.16), (gx + s_, gy), (gx, gy + s_ * 0.16)], fill=(255, 250, 225, al8))
    return img


def intro_frame(base, orient, ic, t, ts, fps=30):
    """Composite the logo intro over a rendered frame (video-relative time t, slam at ts)."""
    if ic.get('logotype'):
        return logotype_intro_frame(base, orient, ic, t, ts)
    st = intro_state(ic, orient, t, ts)
    if not st:
        return base
    sc, a, flash, shake = st
    W, H = SIZES[orient]
    img = base.convert('RGB').copy()
    if ic.get('dim', 0):
        img = Image.blend(img, Image.new('RGB', (W, H), (8, 6, 16)), ic['dim'] * a)
    tile = _intro_tile_cached(ic, orient)
    r = intro_rect(ic, orient, sc)
    if ic.get('sunburst'):
        draw_sunburst(img, r[0] + r[2] / 2, r[1] + r[3] / 2, ic['sunburst'].get('color', [230, 180, 70]), a * ic['sunburst'].get('alpha', 0.8))
    tl = tile if (int(r[2]), int(r[3])) == tile.size else tile.resize((max(1, int(r[2])), max(1, int(r[3]))), Image.BICUBIC)
    if a < 1:
        al = tl.getchannel('A').point(lambda v: int(v * a)); tl = tl.copy(); tl.putalpha(al)
    img.paste(tl, (int(round(r[0])), int(round(r[1]))), tl)
    if ic.get('lightning'):
        flash = lightning_flash(t - ts)
        if flash > 0.3:
            draw_bolt(img, orient, t - ts, seed=ic.get('seed', 13))
    else:
        _sparkles(img, r, t, ts)
    if flash > 0:
        img = Image.blend(img, Image.new('RGB', (W, H), (255, 255, 255)), flash)
    sb = intro_shake_box(orient, t, shake, fps)
    if sb:
        x0, y0, zw, zh = sb
        img = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + zw, y0 + zh))
    return img


# ---------------------------------------------------------------- spooky title styles (FRIGHT NIGHT)
# intro.style "drip": the logo lettering hangs ink drips off its glyph bottoms. intro.lightning: the slam lands
# on a lightning double-flicker (flash, dip, second flash) with a jagged bolt instead of sparkles.
INTRO_DRIP = {'style': 'drip', 'lightning': True, 'glow': [120, 255, 90], 'glow2': [150, 40, 220],
              'chrome': [[235, 255, 210], [170, 230, 120], [90, 150, 60], [20, 40, 18], [120, 190, 80], [215, 250, 180]],
              'subColor': [200, 255, 170], 'rot': -3, 'dim': 0.6}


def lightning_flash(age):
    """White-out strength of a lightning double flicker, age = s since the strike."""
    if age < 0:
        return 0.0
    if age < 0.07:
        return 0.9
    if age < 0.13:
        return 0.12
    if age < 0.33:
        return 0.75 * (1 - (age - 0.13) / 0.2)
    return 0.0


def draw_bolt(img, orient, age, seed=13):
    """Jagged forked lightning bolt from the top edge (pale core, violet glow); a new fork on the second flicker."""
    from PIL import ImageFilter
    W, H = SIZES[orient]
    rnd = np.random.default_rng(seed + (0 if age < 0.1 else 1))
    x = W * rnd.uniform(0.15, 0.35) if rnd.random() < 0.5 else W * rnd.uniform(0.65, 0.85)
    pts = [(x, -10)]
    y = -10
    while y < H * 0.62:
        y += H * rnd.uniform(0.04, 0.09); x += W * rnd.uniform(-0.05, 0.05); pts.append((x, y))
    layer = Image.new('L', (W, H), 0); d = ImageDraw.Draw(layer)
    d.line(pts, fill=255, width=max(4, W // 240), joint='curve')
    k = len(pts) // 2
    fx, fy = pts[k]; fork = [(fx, fy)]
    for _ in range(4):
        fy += H * rnd.uniform(0.03, 0.07); fx += W * rnd.uniform(-0.06, 0.02); fork.append((fx, fy))
    d.line(fork, fill=255, width=max(3, W // 400), joint='curve')
    glow = layer.filter(ImageFilter.GaussianBlur(W / 120)).point(lambda v: min(255, v * 3))
    img.paste(Image.new('RGB', (W, H), (190, 150, 255)), (0, 0), glow)
    img.paste(Image.new('RGB', (W, H), (250, 250, 255)), (0, 0), layer)


# ---------------------------------------------------------------- TO BE CONTINUED card
# spec.tbc: hard cut to black after the last page, a dripping-ink "TO BE CONTINUED..." card, then the end card.
TBC_DEFAULT = {'enabled': False, 'seconds': 2.5, 'text': 'TO BE CONTINUED...'}


def tbc(spec):
    c = dict(TBC_DEFAULT, **(spec.get('tbc') or {}))
    return c if c.get('enabled') and c.get('seconds', 0) > 0 else None


def tbc_ic(c):
    """The card's lettering is an intro-style tile (same overhang-safe recipe, QA'd with intro_ink_lost)."""
    ic = dict(INTRO_DEFAULT); ic.update(INTRO_DRIP)
    ic.update(title=c['text'].upper(), subtitle=None, rot=-2, width=0.86, seed=c.get('seed', 29), lightning=False)
    ic.update(c.get('style') or {})
    return ic


def tbc_frame(orient, c, t, base=None):
    """Card at card-relative time t: lettering eases in (0.45 s) with a slow creep down and a faint flicker, over
    the live last page dimmed to ~18 % (base; still moving underneath) or black when no base is given."""
    W, H = SIZES[orient]
    ic = tbc_ic(c)
    img = Image.new('RGB', (W, H), (4, 3, 6))
    if base is not None:
        img = Image.blend(img, base.convert('RGB').resize((W, H)), 0.18)
    tile = _intro_tile_cached(ic, orient)
    r = intro_rect(ic, orient, 1.0)
    a = min(1.0, max(0.0, t / 0.45))
    a *= 0.88 + 0.12 * (0.5 + 0.5 * math.sin(t * 23.0)) if t > 0.45 else 1.0
    tl = tile.resize((max(1, int(r[2])), max(1, int(r[3]))), Image.BICUBIC) if (int(r[2]), int(r[3])) != tile.size else tile
    tl = tl.copy(); tl.putalpha(tl.getchannel('A').point(lambda v: int(v * a)))
    img.paste(tl, (int(round(r[0])), int(round(r[1] + 6 * min(t, c['seconds']) / c['seconds']))), tl)
    return img


def tbc_rect(c, orient):
    ic = tbc_ic(c); r = intro_rect(ic, orient, 1.0)
    return [r[0], r[1], r[2], r[3] + 7]


# ---------------------------------------------------------------- page transitions (replace hard cuts)
# Each page boundary gets a short (0.3-0.8 s) transition centred on the boundary. Only the ART is transitioned:
# the outgoing page keeps playing past its end (clips freeze), the incoming page shows its landed panels. The
# lettering is laid back on top, unmoved and unmasked: the outgoing page's lettering up to the boundary, the
# incoming page's from the boundary - exactly when a hard cut would swap it - so a caption can never be cut,
# slid off frame or wiped mid-line, and clip timing is unchanged (clips still play full length).
# spec: pages[i].pageTransition = {"type": ..., "dur": ...} (transition INTO page i; "auto" or absent = picked),
# spec.mood / pages[i].mood = "eerie" | "action" | "scare". Never the same type twice in a row.
TRANSITIONS = ['crossfade', 'fade_black', 'slide_left', 'slide_right', 'slide_up', 'wipe_linear', 'wipe_diag', 'iris',
               'whip', 'flash', 'glitch', 'cut']
TRANSITION_FAMILY = {'crossfade': 'dissolve', 'fade_black': 'dissolve', 'slide_left': 'slide', 'slide_right': 'slide',
                     'slide_up': 'slide', 'wipe_linear': 'wipe', 'wipe_diag': 'wipe', 'iris': 'wipe', 'whip': 'whip',
                     'flash': 'flash', 'glitch': 'flash', 'cut': 'cut'}
TRANS_MIN, TRANS_MAX = 0.3, 0.8
MOOD_POOLS = {   # (type, dur) in preference order
    'eerie': [('fade_black', 0.8), ('crossfade', 0.7), ('iris', 0.7), ('wipe_diag', 0.6), ('slide_up', 0.6), ('crossfade', 0.8), ('fade_black', 0.7)],
    'action': [('whip', 0.35), ('flash', 0.3), ('slide_left', 0.4), ('wipe_linear', 0.4), ('whip', 0.4), ('iris', 0.45), ('slide_right', 0.4)],
    'scare': [('glitch', 0.35), ('flash', 0.3), ('whip', 0.35), ('wipe_linear', 0.35)],
}


def page_mood(spec, pg):
    if pg.get('mood'):
        return pg['mood']
    if any(s.get('impact') and abs(s['at'] - pg['start']) < 1.0 for p in pg['panels'] for s in p.get('sfx', [])):
        return 'scare'          # the page opens on an impact: hit it with glitch/flash
    return spec.get('mood', 'eerie')


def page_transitions(spec):
    """[{at, type, dur, into, mood, auto}] for every page boundary (song time), deterministic."""
    pages = spec.get('pages') or []
    out, prev = [], None
    for i in range(1, len(pages)):
        pg = pages[i]
        b = pg['start']
        want = pg.get('pageTransition') or 'auto'
        mood = page_mood(spec, pg)
        if isinstance(want, dict) and want.get('type', 'auto') != 'auto':
            typ, dur, auto = want['type'], want.get('dur', 0.5), False
        else:
            pool = MOOD_POOLS.get(mood, MOOD_POOLS['eerie'])
            k = (i * 3) % len(pool)
            cand = pool[k:] + pool[:k]
            fam_prev = TRANSITION_FAMILY.get(prev) if prev else None
            recent = [x['type'] for x in out[-3:]]
            typ, dur = next(((t_, d_) for t_, d_ in cand if t_ not in recent and TRANSITION_FAMILY[t_] != fam_prev),
                            next(((t_, d_) for t_, d_ in cand if t_ != prev and TRANSITION_FAMILY[t_] != fam_prev),
                                 next(((t_, d_) for t_, d_ in cand if t_ != prev), cand[0])))
            auto = True
        if typ != 'cut':
            # never longer than 40% of either neighbouring page (clips must still read near full length)
            room = min(b - pages[i - 1]['start'], pg['end'] - b) * 0.4
            dur = max(TRANS_MIN, min(TRANS_MAX, dur, room))
        out.append({'at': b, 'type': typ, 'dur': 0.0 if typ == 'cut' else round(dur, 3), 'into': pg['id'], 'mood': mood, 'auto': auto})
        prev = typ
    return out


def _whip_blur(a, n):
    if n < 2:
        return a
    c = np.cumsum(np.pad(a, ((0, 0), (n, 0), (0, 0)), mode='edge'), axis=1, dtype=np.float32)
    return (c[:, n:] - c[:, :-n]) / n


def transition_mix(A, B, typ, p, seed=0):
    """Art composite of outgoing A and incoming B (float32 HxWx3) at progress p in [0, 1]."""
    H, W = A.shape[:2]
    e = ease_io(min(max(p, 0.0), 1.0))
    if typ == 'crossfade':
        return A * (1 - e) + B * e
    if typ == 'fade_black':
        return A * max(0.0, 1 - 2 * p) if p < 0.5 else B * min(1.0, 2 * p - 1)
    if typ in ('slide_left', 'slide_right', 'slide_up', 'whip'):
        out = np.empty_like(A)
        if typ == 'slide_up':
            dy = int(round(e * H))
            out[:H - dy] = A[dy:]; out[H - dy:] = B[:dy]
            return out
        dx = int(round(e * W))
        if typ == 'slide_right':
            out[:, dx:] = A[:, :W - dx]; out[:, :dx] = B[:, W - dx:]
        else:
            out[:, :W - dx] = A[:, dx:]; out[:, W - dx:] = B[:, :dx]
        if typ == 'whip':   # motion blur proportional to the push speed
            out = _whip_blur(out, int(W * 0.09 * math.sin(math.pi * p)))
        return out
    if typ in ('wipe_linear', 'wipe_diag', 'iris'):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        if typ == 'wipe_linear':
            f, soft = xx / W, 0.02
        elif typ == 'wipe_diag':
            f, soft = (xx / W + yy / H) / 2, 0.02
        else:
            f, soft = np.hypot(xx - W / 2, yy - H / 2) / math.hypot(W / 2, H / 2), 0.015
        edge = e * (1 + soft) - soft
        m = np.clip((edge - f) / soft + 0.5, 0, 1)[..., None]
        return A * (1 - m) + B * m
    if typ == 'flash':
        wht = np.full_like(A, 255.0)
        return A + (wht - A) * min(1, p / 0.45) if p < 0.45 else B + (wht - B) * max(0.0, 1 - (p - 0.45) / 0.55)
    if typ == 'glitch':
        src = A if p < 0.5 else B
        rnd = np.random.default_rng(seed + int(p * 40))
        amt = math.sin(math.pi * p)
        out = src.copy()
        sh = int(W * 0.02 * amt) + 1
        out[..., 0] = np.roll(src[..., 0], sh, axis=1); out[..., 2] = np.roll(src[..., 2], -sh, axis=1)
        for _ in range(int(10 * amt) + 1):
            y0 = int(rnd.uniform(0, H)); h = int(rnd.uniform(0.01, 0.06) * H)
            out[y0:y0 + h] = np.roll(out[y0:y0 + h], int(rnd.uniform(-0.12, 0.12) * W * amt), axis=1)
        if 0.42 < p < 0.58:
            out = out + (255 - out) * 0.6
        return out
    return B if p >= 0.5 else A


def lettering_mask(full, art, thr=10):
    """Pixels where the lettered frame differs from its art-only twin = the lettering (captions, SFX)."""
    return np.abs(full.astype(np.int16) - art.astype(np.int16)).max(-1) > thr


def transition_frame(scA, tA, scB, tB, tr, s):
    """Full frame during the page transition `tr` at song time s. scA/scB scenes with scene times tA/tB."""
    p = (s - (tr['at'] - tr['dur'] / 2)) / tr['dur']
    Aart = np.asarray(scA.frame(tA, letters=False), np.float32)
    u0 = min(scB.units, key=lambda u: u['at'])
    Bart = np.asarray(scB.frame(max(tB, T(scB.spec, u0['at']) + entrance_of(u0)['dur'] + 0.02), letters=False), np.float32)
    out = transition_mix(Aart, Bart, tr['type'], p, seed=int(tr['at'] * 10))
    # lettering back on top, unmoved: outgoing up to the boundary, incoming from it (as a hard cut would)
    sc, ts, art = (scA, tA, Aart) if s < tr['at'] else (scB, tB, None)
    full = np.asarray(sc.frame(ts), np.float32)
    if art is None:
        art = np.asarray(sc.frame(ts, letters=False), np.float32)
    m = lettering_mask(full, art)
    out[m] = full[m]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- bg_video (FRIGHT NIGHT "blinking eyes")
# spec.bg_video = {"landscape": path, "vertical": path} (or one path with "{orient}") + "loop": true: a pre-rendered
# seamless loop (scripts/make_eyes_loop.py) plays full-frame behind every page instead of the paper; panels simply
# cover it. Frames are held JPEG-compressed in memory and decoded on demand (looped on the song clock).
_BGV = {}
class BgVideo:
    def __init__(self, path, size, fps):
        import io
        W, H = size
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H},fps={fps}', '-f', 'rawvideo',
                              '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
        n = len(raw) // (W * H * 3)
        self.frames = []
        for k in range(n):
            b = io.BytesIO()
            Image.frombytes('RGB', (W, H), raw[k * W * H * 3:(k + 1) * W * H * 3]).save(b, 'JPEG', quality=92)
            self.frames.append(b.getvalue())
        self.fps, self.last = fps, (None, None)

    def at(self, t, loop=True):
        import io
        k = int(round(t * self.fps))
        k = k % len(self.frames) if loop else min(max(k, 0), len(self.frames) - 1)
        if self.last[0] != k:
            self.last = (k, Image.open(io.BytesIO(self.frames[k])).convert('RGB'))
        return self.last[1]


def bg_video(spec, orient):
    bv = spec.get('bg_video')
    if not bv:
        return None
    path = bv.get(orient) if isinstance(bv, dict) else bv.replace('{orient}', orient)
    path = resolve(spec, path)
    key = (path, orient)
    if key not in _BGV:
        _BGV[key] = BgVideo(path, SIZES[orient], spec.get('fps', 30))
    return _BGV[key]


def eye_shift_image(img, es):
    """Recolour glowing red eyes to ghost-green inside es.boxes (normalised [x0, y0, x1, y1] of the source image),
    so red hair / outfits outside the boxes are untouched. Weight follows how 'hot red' a pixel is."""
    a = np.asarray(img, np.float32).copy()
    H, W = a.shape[:2]
    to = np.array(es.get('color', [110, 255, 160]), np.float32)
    for x0, y0, x1, y1 in es['boxes']:
        X0, Y0, X1, Y1 = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
        r = a[Y0:Y1, X0:X1]
        R, G, B = r[..., 0], r[..., 1], r[..., 2]
        wgt = np.clip((R - np.maximum(G, B) - 50) / 90, 0, 1)[..., None]
        lum = (0.5 * R + 0.5 * np.maximum(G, B))[..., None] / 255.0
        green = np.clip(to * (0.35 + 0.9 * lum), 0, 255)
        a[Y0:Y1, X0:X1] = r * (1 - wgt) + green * wgt
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- panel entrances (rule, 2026-10-13: two-level transitions)
# Every panel animates in with its own entrance when it lands; no two consecutive panels (across the whole video)
# share one. Its captions/SFX appear only after the entrance has finished and are never moved, so they cannot be
# clipped. Spec: panels[i].entrance = {"type": ..., "dur": ...} or omitted for the auto-picker (page mood).
ENTRANCES = ['fade', 'slide_left', 'slide_right', 'slide_up', 'slide_down', 'wipe', 'iris', 'zoom_pop', 'whip', 'glitch']
ENTRANCE_MIN, ENTRANCE_MAX = 0.2, 0.4
ENTRANCE_POOLS = {
    'eerie': [('fade', 0.36), ('iris', 0.34), ('slide_up', 0.32), ('wipe', 0.32), ('zoom_pop', 0.3), ('slide_left', 0.32), ('slide_down', 0.32)],
    'action': [('whip', 0.24), ('zoom_pop', 0.26), ('slide_right', 0.26), ('slide_left', 0.26), ('wipe', 0.26), ('iris', 0.28)],
    'scare': [('glitch', 0.26), ('zoom_pop', 0.24), ('whip', 0.24)],
}


def entrance_of(u):
    e = u.get('entranceUsed') or u.get('entrance') or {'type': 'fade', 'dur': 0.14}
    return {'type': e.get('type', 'fade'), 'dur': min(ENTRANCE_MAX, max(0.05, e.get('dur', 0.3)))}


def assign_entrances(spec):
    """Deterministic entrance per panel (explicit panels[i].entrance wins), never the same type twice in a row."""
    pages = spec.get('pages') or [dict(spec, id=spec.get('page', 'p'), start=spec['song']['start'])]
    prev, i = None, 0
    for pg in pages:
        mood = page_mood(spec, pg) if 'pages' in spec else spec.get('mood', 'eerie')
        mood = 'eerie' if mood == 'scare' else mood
        for u in sorted(pg['panels'], key=lambda u: u['at']):
            e = u.get('entrance')
            if e and e.get('type', 'auto') != 'auto':
                u['entranceUsed'] = {'type': e['type'], 'dur': e.get('dur', 0.3), 'auto': False}
            else:
                pool = ENTRANCE_POOLS['scare'] if any(s.get('impact') for s in u.get('sfx', [])) else ENTRANCE_POOLS.get(mood, ENTRANCE_POOLS['eerie'])
                k = (i * 5) % len(pool)
                cand = pool[k:] + pool[:k]
                typ, dur = next(((t_, d_) for t_, d_ in cand if t_ != prev), cand[0])
                u['entranceUsed'] = {'type': typ, 'dur': dur, 'auto': True}
            prev = u['entranceUsed']['type']; i += 1
    return spec


def panel_entrance(base, painted, bbox, typ, p, seed=0):
    """Composite a panel (painted = base + panel) entering at progress p: only the panel's own pixels move."""
    p = min(max(p, 0.0), 1.0)
    B = np.asarray(base, np.float32); F = np.asarray(painted, np.float32)
    m = (np.abs(F - B).max(-1) > 0).astype(np.float32)
    H, W = m.shape
    x, y, w, h = bbox
    e = ease(p)
    layer, alpha = F, m
    def shift(arr, dx, dy):
        out = np.zeros_like(arr)
        dx, dy = int(round(dx)), int(round(dy))
        xs0, xs1 = max(0, -dx), min(W, W - dx); ys0, ys1 = max(0, -dy), min(H, H - dy)
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = arr[ys0:ys1, xs0:xs1]
        return out
    if typ == 'fade':
        alpha = m * e
    elif typ in ('slide_left', 'slide_right', 'slide_up', 'slide_down', 'whip'):
        d = {'slide_left': (1, 0), 'whip': (1, 0), 'slide_right': (-1, 0), 'slide_up': (0, 1), 'slide_down': (0, -1)}[typ]
        dist = (0.6 if typ == 'whip' else 0.25) * (w if d[0] else h)
        off = (1 - e) * dist
        layer, alpha = shift(F, d[0] * off, d[1] * off), shift(m, d[0] * off, d[1] * off) * min(1.0, 0.3 + e)
        if typ == 'whip':
            n = int(0.06 * w * (1 - e))
            if n > 1:
                c = np.cumsum(np.pad(layer, ((0, 0), (n, 0), (0, 0)), mode='edge'), axis=1, dtype=np.float32)
                layer = (c[:, n:] - c[:, :-n]) / n
    elif typ == 'wipe':
        xx = np.arange(W, dtype=np.float32)[None, :]
        alpha = m * np.clip((x + e * w * 1.05 - xx) / 12, 0, 1)
    elif typ == 'iris':
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot(xx - (x + w / 2), yy - (y + h / 2))
        alpha = m * np.clip((e * math.hypot(w, h) / 2 * 1.02 - r) / 8, 0, 1)
    elif typ == 'zoom_pop':
        sc = 0.7 + 0.3 * e + 0.06 * math.sin(math.pi * e)
        cx, cy = x + w / 2, y + h / 2
        A = (1 / sc, 0, cx - cx / sc, 0, 1 / sc, cy - cy / sc)
        layer = np.asarray(Image.fromarray(F.astype(np.uint8)).transform((W, H), Image.AFFINE, A, Image.BILINEAR), np.float32)
        alpha = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).transform((W, H), Image.AFFINE, A, Image.BILINEAR), np.float32) / 255 * min(1, 0.2 + e)
    elif typ == 'glitch':
        rnd = np.random.default_rng(seed + int(p * 30))
        layer = F.copy(); sh = int(0.02 * w * (1 - p)) + 1
        layer[..., 0] = np.roll(F[..., 0], sh, 1); layer[..., 2] = np.roll(F[..., 2], -sh, 1)
        alpha = m * (1.0 if rnd.random() < 0.3 + 0.7 * p else 0.25)
        if p < 0.3:
            layer = layer + (255 - layer) * (0.7 * (1 - p / 0.3))
    out = B * (1 - alpha[..., None]) + layer * alpha[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- scene-aware cropping (rule, 2026-10-13)
# Every panel carries focus regions (faces + key action) in normalised source-image coords:
#   panels[i].focusRegions = [{"label": "Uno face", "box": [x0, y0, x1, y1], "required": true}, ...]
# Manual regions win; otherwise auto_focus_regions() finds glowing robot-eye pairs (brand: red eyes) and boxes
# the head around them. fit_crop() slides the (largest) cover crop so every required region lands inside the
# cell's clip path (eroded past the ink); QA check_focus() fails a page when a region is clipped, occluded by a
# panel above it or cut by the frame, in landscape and vertical, and writes debug crops. Builders that hit a miss
# pick another layout / slot order (see shots/fright-night-comic/make_spec.py fix_layouts).
FOCUS_TOL = 0.05   # share of a region's sample grid allowed to graze the edge (its outermost row touching the ink)
FOCUS_INSET = 12   # px a focus region keeps from the cell's clip path edge (ink is 7-9 px)
_REG_CACHE_PATH = os.path.join(ROOT, 'out', '.register-cache.json')
_REG_CACHE = None


def register_cached(img_path, clip_path, img, fps):
    """register() of a clip's first frame on its panel, cached on disk by file size + mtime (it costs seconds)."""
    global _REG_CACHE
    if _REG_CACHE is None:
        try:
            _REG_CACHE = json.load(open(_REG_CACHE_PATH))
        except Exception:
            _REG_CACHE = {}
    st = lambda p: f'{os.path.getsize(p)}:{int(os.path.getmtime(p))}'
    key = f'{img_path}|{st(img_path)}|{clip_path}|{st(clip_path)}'
    if key not in _REG_CACHE:
        reg, score = register(img, first_frame(clip_path))
        _REG_CACHE[key] = [list(reg), score]
        os.makedirs(os.path.dirname(_REG_CACHE_PATH), exist_ok=True)
        json.dump(_REG_CACHE, open(_REG_CACHE_PATH, 'w'))
    reg, score = _REG_CACHE[key]
    return tuple(reg), score


def auto_focus_regions(img):
    """Glowing eye pairs (red, or ghost-green) -> head boxes. Heuristic for the chrome-robot cast; unpaired
    glows (lanterns, sparks) are ignored. Returns [{"label", "box", "required", "src"}] in normalised coords."""
    from scipy import ndimage as ndi
    a = np.asarray(img.convert('RGB').resize((640, round(640 * img.height / img.width))), np.int16)
    H, W = a.shape[:2]
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    m = ((R > 190) & (R - G > 70) & (R - B > 70)) | ((G > 190) & (G - R > 50) & (G - B > 20))
    lab, n = ndi.label(ndi.binary_opening(m))
    blobs = []
    for i, sl in enumerate(ndi.find_objects(lab)):
        ys, xs = sl
        area = int((lab[sl] == i + 1).sum())
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if 6 <= area <= 0.01 * W * H and 0.3 < w / max(h, 1) < 3.5:
            blobs.append(((xs.start + xs.stop) / 2, (ys.start + ys.stop) / 2, max(w, h)))
    out, used = [], set()
    for i, (x1, y1, s1) in enumerate(blobs):
        for j, (x2, y2, s2) in enumerate(blobs):
            if j <= i or i in used or j in used:
                continue
            d = math.hypot(x2 - x1, y2 - y1)
            if 1.3 * max(s1, s2) < d < 7 * max(s1, s2) and abs(y2 - y1) < 0.45 * d and 0.5 < s1 / s2 < 2:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                box = [max(0, cx - 1.4 * d) / W, max(0, cy - 1.5 * d) / H, min(W, cx + 1.4 * d) / W, min(H, cy + 1.6 * d) / H]
                out.append({'label': 'face (auto: eye pair)', 'box': [round(v, 3) for v in box], 'required': True, 'src': 'auto', 'size': d})
                used |= {i, j}
    if out:   # background extras (small faces) are optional: the cast are the big ones
        big = max(r['size'] for r in out)
        for r in out:
            r['required'] = r['size'] >= 0.45 * big
            r.pop('size')
    return out


def focus_regions(spec, u, img=None):
    if u.get('focusRegions') is not None:
        return [dict(r, src=r.get('src', 'manual'), required=r.get('required', True)) for r in u['focusRegions']]
    if spec.get('focusAuto', True) and img is not None:
        return auto_focus_regions(img)
    return []


_EMASK = {}
def _eroded_mask(geo, inset=FOCUS_INSET):
    key = (json.dumps(geo['polys']), json.dumps(geo['burst']), tuple(geo['bbox']), inset)
    if key not in _EMASK:
        from PIL import ImageFilter
        m = slot_mask(geo)
        for _ in range(max(1, inset // 2)):
            m = m.filter(ImageFilter.MinFilter(5))
        _EMASK[key] = np.asarray(m) > 127
    return _EMASK[key]


def _region_pts(box, img_w, img_h, n=6):
    x0, y0, x1, y1 = box
    xs = np.linspace(x0 * img_w, x1 * img_w, n); ys = np.linspace(y0 * img_h, y1 * img_h, n)
    return np.array([(x, y) for x in xs for y in ys])


def crop_misses(crop, img_w, img_h, geo, regions, within=None):
    """[(region, fraction of its sample points outside the cell)] for required regions under `crop`."""
    cx, cy, cw, ch = crop
    x, y, w, h = geo['bbox']
    mk = _eroded_mask(geo)
    out = []
    for r in regions:
        if not r.get('required', True):
            continue
        P = _region_pts(r['box'], img_w, img_h)
        if within is not None:   # only what the clip covers exists in the video
            P[:, 0] = np.clip(P[:, 0], within[0], within[0] + within[2]); P[:, 1] = np.clip(P[:, 1], within[1], within[1] + within[3])
        lx = ((P[:, 0] - cx) / cw * w).round().astype(int); ly = ((P[:, 1] - cy) / ch * h).round().astype(int)
        inside = (lx >= 0) & (ly >= 0) & (lx < w) & (ly < h)
        ok = np.zeros(len(P), bool)
        ok[inside] = mk[ly[inside], lx[inside]]
        frac = 1 - ok.mean()
        if frac > FOCUS_TOL:
            out.append((r, round(float(frac), 3)))
    return out


def fit_crop(img_w, img_h, geo, regions, within=None, focus=(0.5, 0.5)):
    """Cover crop (largest at the cell aspect) positioned so every required focus region fits the cell's clip path.
    Returns (crop, misses); misses is empty when everything fits, else the best position's misses."""
    x, y, w, h = geo['bbox']
    base = cover_crop(img_w, img_h, w, h, focus, within)
    if not any(r.get('required', True) for r in regions):
        return base, []
    bx, by, bw, bh = within or (0, 0, img_w, img_h)
    cw, ch = base[2], base[3]
    best = None
    for X in np.linspace(bx, bx + bw - cw, 21) if bw - cw > 1 else [base[0]]:
        for Y in np.linspace(by, by + bh - ch, 21) if bh - ch > 1 else [base[1]]:
            miss = crop_misses((X, Y, cw, ch), img_w, img_h, geo, regions, within)
            key = (round(sum(f for _, f in miss), 3), abs(X - base[0]) + abs(Y - base[1]))
            if best is None or key < best[0]:
                best = (key, (float(X), float(Y), cw, ch), miss)
    return best[1], best[2]


_IMG_CACHE = {}
def unit_fit(spec, u, geo, fps=30):
    """Geometry-only twin of Scene._prep's crop (no clip decoding): (img_size, crop, regions, misses, within)."""
    ip = resolve(spec, u['image'])
    if ip not in _IMG_CACHE:
        _IMG_CACHE[ip] = Image.open(ip).convert('RGB')
    img = _IMG_CACHE[ip]
    x, y, w, h = geo['bbox']
    within = None
    if u.get('clip'):
        reg, _ = register_cached(ip, resolve(spec, u['clip']['src']), img, fps)
        rx, ry, rw, rh = reg
        within = (max(rx, 0), max(ry, 0), min(rx + rw, img.width) - max(rx, 0), min(ry + rh, img.height) - max(ry, 0))
    focus = u.get('focus') or default_focus(img.width, img.height, w, h)
    regions = focus_regions(spec, u, img)
    crop, miss = fit_crop(img.width, img.height, geo, regions, within, tuple(focus))
    return img.size, crop, regions, miss, within


def region_to_frame(box, img_size, crop, geo):
    """Normalised source-image box -> frame-px box through the crop into the cell."""
    iw, ih = img_size; cx, cy, cw, ch = crop; x, y, w, h = geo['bbox']
    f = lambda X, Y: (x + (X * iw - cx) / cw * w, y + (Y * ih - cy) / ch * h)
    (a, b), (c, d) = f(box[0], box[1]), f(box[2], box[3])
    return [a, b, c, d]


def is_reflow(spec):
    return bool(LAYOUTS.get(spec.get('layout', ''), {}).get('reflow'))


FULLFRAME_Z = 5


def fullframe_k(spec, u, t):
    """Full frame <-> panel (panel.fullFrame): 0 = in its cell, 1 = full screen, eased in between.
      {"mode": "open", "hold": 1, "dur": 1}  lands FULL SCREEN, holds `hold` beats, shrinks into its cell over `dur` beats
      {"mode": "grow", "at": 31.2, "dur": 1} grows from its cell to full screen at song time `at` (default: land +
                                              hold beats) and stays full screen ("back": beats -> shrinks back after).
    Beats are the song's beat period; dur is clamped to 0.35-1.2 s so the move always reads and never stalls."""
    ff = u.get('fullFrame')
    if not ff:
        return 0.0
    import reflow as RF
    b = beat_period(spec)
    dur = min(1.2, max(0.35, ff.get('dur', 1.0) * b))
    ta = T(spec, u['at'])
    if ff.get('mode', 'open') == 'open':
        s0 = ta + ff.get('hold', 1.0) * b
        return 1.0 if t < s0 else 1.0 - RF.ease_io((t - s0) / dur)
    s0 = T(spec, ff['at']) if 'at' in ff else ta + ff.get('hold', 1.0) * b
    k = RF.ease_io((t - s0) / dur)
    if 'back' in ff:
        s1 = s0 + dur + ff['back'] * b
        k = min(k, 1.0 - RF.ease_io((t - s1) / dur))
    return k


_ARRIVAL = {}
def arrival_box(spec, orient, u, box):
    """Where a panel sits when it is 'full frame' inside box (x, y, w, h): the whole box, unless its faces cannot
    share a window of the box's shape (a wide two-shot in the 9:16 Short): then a full-WIDTH band at the footage's
    own aspect, centred, so the shot still fills the screen edge to edge and every face stays in."""
    key = (spec.get('page'), u['id'], orient, tuple(box))
    if key not in _ARRIVAL:
        bx, by, bw, bh = box
        G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
        base = G.get(u.get('slot')) or G['splash']
        size, _, regions, _, within = unit_fit(spec, u, base, spec.get('fps', 30))
        plan = unit_plan(spec, u, base, spec.get('fps', 30), regions, size, within)
        wb = within or (0, 0) + tuple(size)
        ok_ = all(not fs or cell_fits_faces(list(fs), bw / bh, wb)
                  for fs in (plan.faces_at(plan.t0 + (plan.t1 - plan.t0) * i / 8) for i in range(9)))
        if ok_ or CAM.REVEAL:   # reveal rule: fill the box and pan face to face instead of letterboxing
            _ARRIVAL[key] = tuple(box)
        else:
            h = min(bh, bw * wb[3] / wb[2])
            _ARRIVAL[key] = (bx, by + (bh - h) / 2, bw, h)
    return _ARRIVAL[key]


def _fullframe(spec, orient, u, t, geo, z):
    k = fullframe_k(spec, u, t)
    if k <= 1e-4:
        return geo, z
    W, H = SIZES[orient]
    x, y, w, h = geo['bbox']
    fx, fy, fw, fh = arrival_box(spec, orient, u, (0, 0, W, H))
    r = (x + (fx - x) * k, y + (fy - y) * k, w + (fw - w) * k, h + (fh - h) * k)
    poly = [(r[0], r[1]), (r[0] + r[2], r[1]), (r[0] + r[2], r[1] + r[3]), (r[0], r[1] + r[3])]
    return dict(geo, bbox=list(r), polys=[poly], inner=r, keyline=False, burst=None, _ff=k), FULLFRAME_Z


def reflow_geo(spec, orient, u, t, G=None):
    """(geo, z) of unit u at scene time t on a living-panel page (None before it lands); static pages: (G[slot], z).
    Either can be overridden by the unit's fullFrame move (full screen <-> its cell)."""
    if G is None:
        G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    if not is_reflow(spec):
        return _fullframe(spec, orient, u, t, G[u['slot']], G[u['slot']]['z'])
    import reflow as RF
    order = sorted(spec['panels'], key=lambda p: p['at'])
    lands = [T(spec, p['at']) for p in order]
    i = next(k for k, p in enumerate(order) if p['id'] == u['id'])
    fam = LAYOUTS[spec['layout']]['family'][orient]
    cx, cy, cw, ch = CONTENT[orient]
    ax, ay, aw, ah = arrival_box(spec, orient, u, CONTENT[orient])
    arr = ((ax - cx) / cw, (ay - cy) / ch, aw / cw, ah / ch)
    r, z = RF.rect_at(i, t, lands, beat_period(spec), spec.get('reflowArrive', 1.0), spec.get('reflowMove', 1.0), family=fam,
                      arrival=arr)
    if r is None:
        return None, 0
    return _fullframe(spec, orient, u, t, _geo(('rect',) + tuple(r), CONTENT[orient]), z)


CELL_SWEEP = 5.0


def cell_fits_faces(faces, aspect, within):
    """Can one window of this aspect, inside the footage, hold every face (6 % margin)?"""
    bx, by, bw, bh = within
    ux0, uy0 = min(f[0] for f in faces), min(f[1] for f in faces); ux1, uy1 = max(f[2] for f in faces), max(f[3] for f in faces)
    w = min(bw, bh * aspect); h = w / aspect
    return (ux1 - ux0) <= 0.88 * w + 1e-6 and (uy1 - uy0) <= 0.88 * h + 1e-6


def cell_window(plan, t, geo, img_size, within):
    """The plan's window at t, re-shaped to the CURRENT cell aspect (living panels change cell shape mid-move):
    same centre and area, then shifted so the faces the plan promises stay inside, clamped to the footage."""
    X, Y, W_, H_ = plan.window(t)
    cw, ch = geo['bbox'][2], geo['bbox'][3]
    a = cw / max(ch, 1)
    if abs(a - W_ / H_) < 1e-3 and all(f[0] >= X - 1 and f[1] >= Y - 1 and f[2] <= X + W_ + 1 and f[3] <= Y + H_ + 1
                                       for f in plan.faces_at(t)):
        return (X, Y, W_, H_)
    iw, ih = img_size
    bx, by, bw, bh = within or (0, 0, iw, ih)
    area = W_ * H_
    w2 = math.sqrt(area * a); h2 = w2 / a
    if w2 > bw: w2, h2 = bw, bw / a
    if h2 > bh: h2, w2 = bh, bh * a
    cx, cy = X + W_ / 2, Y + H_ / 2
    fs = plan.faces_at(t); ex = list(fs)
    if ex and not cell_fits_faces(ex, a, (bx, by, bw, bh)):
        # every face cannot share a window of this cell's shape (e.g. a wide two-shot arriving full frame in the
        # Short): keep the faces the camera plan promises in frame instead of centring on nobody
        ex = [fs[i] for i in plan.expected(t)] or ([] if CAM.REVEAL else ex[:1])
    if ex:
        ux0, uy0 = min(f[0] for f in ex), min(f[1] for f in ex); ux1, uy1 = max(f[2] for f in ex), max(f[3] for f in ex)
        # grow (same aspect) until the faces fit with a 6 % margin, never past the footage
        need = max((ux1 - ux0) / 0.88 / w2, (uy1 - uy0) / 0.88 / h2, 1.0)
        need = min(need, bw / w2, bh / h2)
        w2, h2 = w2 * need, h2 * need
    # never pin the window to the whole footage (a pinned window cannot move = a static frame): keep 8 % room and
    # a slow breathing zoom so the camera keeps moving while the cell changes shape (e.g. a full-frame arrival)
    # the breath runs between kmax (8 % room in the footage) and kmin (10 % tighter, never tighter than the faces need
    # with a 2 % margin), on a cosine, so it only touches either end for an instant
    if CAM.REVEAL:   # reveal rule: no breathing zoom, no sweep; keep the plan's position, clamped to the footage
        if ex and not cell_fits_faces(ex, a, (bx, by, bw, bh)):
            ex = []   # faces spread wider than the cell: follow the plan's one-way pan
        if ex:
            cx = min(max(cx, ux1 - w2 / 2), ux0 + w2 / 2) if ux1 - ux0 < w2 else (ux0 + ux1) / 2
            cy = min(max(cy, uy1 - h2 / 2), uy0 + h2 / 2) if uy1 - uy0 < h2 else (uy0 + uy1) / 2
        return (min(max(cx - w2 / 2, bx), bx + bw - w2), min(max(cy - h2 / 2, by), by + bh - h2), w2, h2)
    kmax = min(1.0, 0.92 * bw / w2, 0.92 * bh / h2)
    kmin = max(kmax * 0.90, min(1.0, max((ux1 - ux0) / 0.96 / w2, (uy1 - uy0) / 0.96 / h2)) if ex else 0.0)
    kmax = max(kmax, kmin)
    k = kmax - (kmax - kmin) * (0.5 - 0.5 * math.cos(2 * math.pi * t / 3.0))
    w2, h2 = w2 * k, h2 * k
    if ex:
        mx, my = min(0.06 * w2, (w2 - (ux1 - ux0)) / 2), min(0.06 * h2, (h2 - (uy1 - uy0)) / 2)
        cx = min(max(cx, ux1 - w2 / 2 + mx), ux0 + w2 / 2 - mx) if ux1 - ux0 < w2 else (ux0 + ux1) / 2
        cy = min(max(cy, uy1 - h2 / 2 + my), uy0 + h2 / 2 - my) if uy1 - uy0 < h2 else (uy0 + uy1) / 2
    x2 = min(max(cx - w2 / 2, bx), bx + bw - w2); y2 = min(max(cy - h2 / 2, by), by + bh - h2)
    # never pinned: when faces + footage edges leave the breathing zoom no room (k clamped), drift the window across
    # whatever slack keeps every face inside (2 % margin) - a slow sweep, period CELL_SWEEP s, so a re-shaped cell
    # (a full-frame arrival / hold) always moves
    lo_x, hi_x, lo_y, hi_y = bx, bx + bw - w2, by, by + bh - h2
    if ex:
        lo_x, hi_x = max(lo_x, ux1 + 0.01 * w2 - w2), min(hi_x, ux0 - 0.01 * w2)
        lo_y, hi_y = max(lo_y, uy1 + 0.01 * h2 - h2), min(hi_y, uy0 - 0.01 * h2)
    ph = 0.5 - 0.5 * math.cos(2 * math.pi * t / CELL_SWEEP)
    if hi_x - lo_x > 2:
        x2 = x2 + (lo_x + (hi_x - lo_x) * ph - x2) * 0.6
    if hi_y - lo_y > 2:
        y2 = y2 + (lo_y + (hi_y - lo_y) * (1 - ph) - y2) * 0.6
    x2 = min(max(x2, bx), bx + bw - w2); y2 = min(max(y2, by), by + bh - h2)
    return (x2, y2, w2, h2)


def _zoom_box(spec, orient, t, G):
    tr = spec.get('transition')
    W, H = SIZES[orient]
    if not tr:
        return None
    t_land = T(spec, tr['at']); dur = tr.get('dur', 0.4)
    if t >= t_land or t < t_land - dur:
        return None
    tu = next((u for u in spec['panels'] if u['id'] == tr['panel']), None)
    if tu is None:
        return None
    tx, ty, tw, th = G[tu['slot']]['bbox']; a = W / H
    if tw / th > a:
        th2 = tw / a; ty -= (th2 - th) / 2; th = th2
    else:
        tw2 = th * a; tx -= (tw2 - tw) / 2; tw = tw2
    tx = min(max(tx, 0), W - tw); ty = min(max(ty, 0), H - th)
    k = ease_io((t - (t_land - dur)) / dur)
    return (tx * k, ty * k, W + (tw - W) * k, H + (th - H) * k)


_FACE_GEO = {}
def scene_faces(spec, orient, t):
    """Frame-px boxes of every visible face / focus region at scene time t (tracked faces through the camera
    window, the cell's live geometry, splash and zoom). Shared by the lyric overlay (avoid faces) and its QA."""
    G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
    tr = spec.get('transition')
    W, H = SIZES[orient]
    units = []
    if tr and spec.get('splash') and t >= T(spec, tr['at']):
        units = [(splash_unit(spec), G['splash'])]
    else:
        for u in spec['panels']:
            if t < T(spec, u['at']):
                continue
            geo, _ = reflow_geo(spec, orient, u, t, G)
            if geo is not None:
                units.append((u, geo))
    out = []
    zb = _zoom_box(spec, orient, t, G)
    for u, geo in units:
        key = (spec.get('page'), u['id'], orient)
        if key not in _FACE_GEO:
            base = G['splash'] if u.get('id') == (spec.get('splash') or {}).get('id', 'splash') and not any(p['id'] == u['id'] for p in spec['panels']) else G.get(u.get('slot'), G['splash'])
            size, crop, regions, _, within = unit_fit(spec, u, base, spec.get('fps', 30))
            plan = unit_plan(spec, u, base, spec.get('fps', 30), regions, size, within)
            extra = [r for r in regions if r.get('face') and not r.get('required', True)]
            _FACE_GEO[key] = (size, within, plan, extra)
        size, within, plan, extra = _FACE_GEO[key]
        iw, ih = size
        win = cell_window(plan, t, geo, size, within)
        bx, by, bw, bh = geo['bbox']
        boxes = list(plan.faces_at(t)) + [[r['box'][0] * iw, r['box'][1] * ih, r['box'][2] * iw, r['box'][3] * ih] for r in extra]
        for b in boxes:
            fx0 = bx + (b[0] - win[0]) / win[2] * bw; fx1 = bx + (b[2] - win[0]) / win[2] * bw
            fy0 = by + (b[1] - win[1]) / win[3] * bh; fy1 = by + (b[3] - win[1]) / win[3] * bh
            fx0, fx1 = max(fx0, bx), min(fx1, bx + bw); fy0, fy1 = max(fy0, by), min(fy1, by + bh)
            if fx1 - fx0 < 4 or fy1 - fy0 < 4:
                continue
            if zb:
                zx, zy, zw, zh = zb
                fx0, fx1 = (fx0 - zx) * W / zw, (fx1 - zx) * W / zw; fy0, fy1 = (fy0 - zy) * H / zh, (fy1 - zy) * H / zh
            out.append([fx0, fy0, fx1, fy1])
    return out


def overlay_on(spec):
    return bool((spec.get('lyricOverlay') or {}).get('enabled'))


def song_faces_fn(spec, orient):
    """faces_fn(song_t) for the lyric overlay: every visible face box of the page(s) on screen (both pages during
    a page turn, so a caption never lands on the incoming page's faces either)."""
    subs = subspecs(spec)
    trs = [tr for tr in page_transitions(spec) if tr['dur'] > 0]
    def fn(s):
        out = []
        on = [x for x in subs if x['song']['start'] - 1e-6 <= s < x['song']['end']]
        for tr in trs:
            if abs(s - tr['at']) < tr['dur'] / 2:
                on += [x for x in subs if abs(x['song']['start'] - tr['at']) < 1e-6 or abs(x['song']['end'] - tr['at']) < 1e-6]
        seen = set()
        for x in on:
            if x['page'] in seen:
                continue
            seen.add(x['page'])
            out += scene_faces(x, orient, max(0.0, s - x['song']['start']))
        return out
    return fn


def song_sfx_fn(spec, orient):
    """obstacles_fn(song_t) for the lyric overlay: SFX boxes on screen (soft cost: the caption steers clear of
    lettering when it can; faces are the hard rule)."""
    subs = subspecs(spec)
    items = []
    for x in subs:
        try:
            for it in text_items(x, orient):
                if it['kind'] == 'sfx':
                    r = it['rect']; s0 = x['song']['start']
                    items.append((s0 + it['from'], s0 + it['to'], [r[0], r[1], r[0] + r[2], r[1] + r[3]]))
        except Exception:
            continue
    return lambda s: [b for a, z, b in items if a <= s < z]


def lyric_overlay(spec, orient, t0=None, t1=None):
    """The planned floating lyric overlay for a render window (None when spec.lyricOverlay is off)."""
    if not overlay_on(spec):
        return None
    import lyric_overlay as LO
    tl = spec['song'].get('timeline')
    path = tl if os.path.isabs(tl) else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', tl)
    lines = json.load(open(path))['lyrics']
    t0 = spec['song']['start'] if t0 is None else t0
    t1 = spec['song']['end'] if t1 is None else t1
    ov = LO.Overlay(orient, SIZES[orient], song_faces_fn(spec, orient), font_path(),
                    spec['lyricOverlay'].get('style', 'deco_gold'), obstacles_fn=song_sfx_fn(spec, orient))
    ov.plan(LO.cues_from_lines(lines, t0, t1))
    return ov


def _plan_misses(plan, req, size, geo, n=10):
    worst = {}; iw, ih = size
    for t in np.linspace(plan.t0, plan.t1, n):
        win = plan.window(t); fs = plan.faces_at(t)
        for i in plan.expected(t):
            b = fs[i]
            r = dict(req[i], box=[b[0] / iw, b[1] / ih, b[2] / iw, b[3] / ih])
            for _, frac in crop_misses(win, iw, ih, geo, [r], None):
                worst[i] = max(worst.get(i, 0.0), frac)
    return worst


def camera_misses(spec, u, geo, size, regions, within, n=10):
    """[(region, worst fraction outside the cell)] for the faces the per-cut camera move promises, sampled over
    the whole time the panel is on screen (tracked faces). A move that cannot hold a face reports it with 1.0
    (\"needs a bigger cell\")."""
    plan = unit_plan(spec, u, geo, spec.get('fps', 30), regions, size, within)
    req = [r for r in regions if r.get('required', True)]
    if not plan.fits:
        return [(dict(req[0], label=req[0]['label'] + ' (needs a bigger cell: ' + plan.why + ')'), 1.0)] if req else []
    worst = _plan_misses(plan, req, size, geo, n)
    return [(req[i], round(f, 3)) for i, f in sorted(worst.items())]


def page_focus_problems(spec, sub, orient):
    """[(unit id, label, kind, fraction)] for one page in one orientation: 'clipped' (outside the cell / frame)
    or 'occluded' (under a panel drawn above it)."""
    W, H = SIZES[orient]
    G = layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
    probs = []
    units = sub['panels']
    masks = {u['id']: clip_path_mask(G[u['slot']], W, H, inset=0) for u in units}
    for u in units:
        geo = G[u['slot']]
        size, crop, regions, miss, within = unit_fit(spec, u, geo, spec.get('fps', 30))
        pv = sub if 'song' in sub and 'panels' in sub else dict({k: v for k, v in spec.items() if k != 'pages'}, panels=sub['panels'],
                 transition=sub.get('transition'), splash=sub.get('splash'), page=sub.get('id', sub.get('page')),
                 song=dict(spec['song'], start=sub.get('start', spec['song']['start']), end=sub.get('end', spec['song']['end'])))
        miss = camera_misses(pv, u, geo, size, regions, within)
        for r, frac in miss:
            probs.append((u['id'], r['label'], 'clipped', frac))
        above = [o for o in units if o is not u and G[o['slot']]['z'] > geo['z']]
        for r in regions:
            if not r.get('required', True) or any(m[0] is r for m in miss):
                continue
            fb = region_to_frame(r['box'], size, crop, geo)
            P = _region_pts([fb[0] / W, fb[1] / H, fb[2] / W, fb[3] / H], W, H)
            px = np.clip(P[:, 0].round().astype(int), 0, W - 1); py = np.clip(P[:, 1].round().astype(int), 0, H - 1)
            off = ((P[:, 0] < 0) | (P[:, 1] < 0) | (P[:, 0] >= W) | (P[:, 1] >= H)).mean()
            if off > 0:
                probs.append((u['id'], r['label'], 'clipped', round(float(off), 3)))
            occ = np.zeros(len(P), bool)
            for o in above:
                occ |= masks[o['id']][py, px]
            if occ.mean() > 0.04:
                probs.append((u['id'], r['label'], 'occluded', round(float(occ.mean()), 3)))
    return probs


# ---------------------------------------------------------------- no-repeat gate (Jason 2026-10-14)
REPEAT_TOL = 0.15   # s a finished clip may linger (one transition frame or two)


def repeat_report(spec, t0=None, t1=None):
    """Every source segment may appear ONCE per video. Returns [(unit id, src, from, to, seconds, why)] for (a) any
    clip/panel source used by two units and (b) any clip still on screen after it has played through once (a loop /
    hold = a replay). Song window [t0, t1]; the title intro and end card are exempt (the end card's live page is not
    counted). Stills with no clip (sequence insets) are a single shot while visible."""
    t0 = spec['song']['start'] if t0 is None else t0
    t1 = spec['song']['end'] if t1 is None else t1
    out, seen = [], {}
    for pg in spec['pages']:
        sp = pg.get('splash'); spat = pg.get('transition', {}).get('at')
        units = [(u, u['at'], min(spat if sp else pg['end'], u.get('until', 1e9))) for u in pg['panels']] + ([(sp, spat, pg['end'])] if sp else [])
        for u, land, exit_ in units:
            if exit_ <= t0 or land >= t1:
                continue
            c = u.get('clip')
            src = (c['src'], round(c['in'], 2), round(c['out'], 2)) if c else (u['image'], None, None)
            if src in seen:
                out.append((u['id'], src[0], max(land, t0), min(exit_, t1), round(min(exit_, t1) - max(land, t0), 2), f'same source as {seen[src]}'))
            seen[src] = u['id']
            if c:
                once = clip_start(spec, dict(u, at=land)) + (c['out'] - c['in']) / c.get('speed', 1.0)
                a, b = max(once, t0), min(exit_, t1)
                if b - a > REPEAT_TOL:
                    out.append((u['id'], c['src'], round(a, 2), round(b, 2), round(b - a, 2), 'clip ends, cell keeps replaying it'))
    return out


def sfx_face_report(spec, orient):
    """[(unit, sfx, problem)] for every SFX whose drawn rect meets a face while it is up (gate), using the shared
    face tracker. Dropped SFX (no open space) are reported as 'dropped' (not a failure)."""
    out = []
    for sub in subspecs(spec):
        L = layout(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
        G = layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
        S = TEXT_SAFE[orient]
        units = [dict(p) for p in sub['panels']] + ([dict(splash_unit(sub), slot='splash')] if splash_unit(sub) else [])
        for u in units:
            if u.get('slot') not in L:
                continue
            for s_ in u.get('sfx', []):
                rect, _ = sfx_place(sub, orient, s_, u, L[u['slot']], G[u['slot']], S)
                if rect is None:
                    out.append((u['id'], s_['text'], 'dropped (no open space clear of faces)')); continue
                if any(_hit(rect, f) for f in sfx_faces(sub, orient, s_)):
                    out.append((u['id'], s_['text'], 'OVER A FACE'))
    return out

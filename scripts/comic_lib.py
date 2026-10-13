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

def song_beats(spec):
    tl = spec['song'].get('timeline')
    if not tl:
        return []
    with open(resolve(spec, tl)) as f:
        return json.load(f).get('beats', [])

def T(spec, song_t):
    return song_t - spec['song']['start']

DEFAULT_HOLD_BEATS = 1     # Jason's rule: static hold of ~one beat (0.3-0.5 s) before the clip plays
MIN_HOLD = 0.25            # ...but keep the anticipation beat (Jason likes it)
MAX_HOLD = 0.6             # QA fails if clip start - panel land > this


def subspecs(spec):
    """A spec is one page (panels/transition/splash) or a whole song ("pages": [...]).
    Returns one page-level spec per page with song.start/end set to the page's span."""
    if 'pages' not in spec:
        return [spec]
    out = []
    for pg in spec['pages']:
        sub = {k: v for k, v in spec.items() if k != 'pages'}
        sub.update(panels=pg['panels'], transition=pg.get('transition'), splash=pg.get('splash'), page=pg['id'],
                   layout=pg.get('layout', 'three'), splashStyle=pg.get('splashStyle', 'full'),
                   song=dict(spec['song'], start=pg['start'], end=pg['end']))
        out.append(sub)
    return out


def clip_start(spec, u):
    """Song time the clip starts: explicit clip.at, else DEFAULT_HOLD_BEATS beats after the panel lands."""
    c = u['clip']
    if c.get('at') is not None:
        return c['at']
    beats = [b for b in song_beats(spec) if b > u['at'] + 0.05]
    hold = spec.get('defaults', {}).get('holdBeats', DEFAULT_HOLD_BEATS)
    return beats[hold - 1] if len(beats) >= hold else u['at'] + 0.45


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
    'tilt-three': {'n': 3, 'vert': 'T', 'slots': {
        'a': ('rot', 0.40, 0.50, 0.78, 0.94, 1.5, {'inner': (0.04, 0.06, 0.55, 0.88)}),
        'b': ('rot', 0.81, 0.27, 0.36, 0.48, -4, {'z': 1, 'keyline': True}),
        'c': ('rot', 0.80, 0.74, 0.37, 0.47, 3, {'z': 2, 'keyline': True})}},
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
def read_clip(path, t_in, t_out, fps):
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                    'stream=width,height', '-of', 'csv=p=0', path],
                                   capture_output=True, text=True).stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t_in:.3f}', '-i', path, '-t', f'{t_out - t_in:.3f}',
                          '-vf', f'fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
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
        for c in p.get('captions', []):
            items.append({'who': f"{p['id']} caption '{c['text']}'", 'rect': caption_box(c, slot, geo, S)[0], 'geo': geo, 'unit': p['id'],
                          'from': T(spec, c.get('at', p['at'])), 'to': min(page_end, T(spec, c['until'])) if 'until' in c else page_end, 'slot': slot, 'kind': 'caption', 'obj': c})
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


class Scene:
    """Builds frames for one orientation."""
    def __init__(self, spec, orient, fps=None):
        self.spec, self.orient = spec, orient
        self.W, self.H = SIZES[orient]
        self.fps = fps or spec.get('fps', 30)
        self.G = layout_geo(orient, spec.get('layout', 'three'), spec.get('splashStyle', 'full'))
        self.paper = Image.fromarray(paper(self.W, self.H))
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
        if u['geo']['burst']:
            g = dict(u['geo'], polys=[]); u['burstMask'] = slot_mask(g)
        within = None
        if u.get('clip'):
            c = u['clip']
            path = resolve(self.spec, c['src'])
            frames = read_clip(path, c['in'], c['out'], self.fps)
            reg, score = register(img, read_clip(path, 0.0, 0.05, self.fps)[0])
            u['reg'], u['regScore'] = reg, score
            # keep the crop inside the area the clip covers so static -> clip lines up exactly
            rx, ry, rw, rh = reg
            within = (max(rx, 0), max(ry, 0), min(rx + rw, img.width) - max(rx, 0), min(ry + rh, img.height) - max(ry, 0))
        focus = u.get('focus')
        if focus is None:
            focus = default_focus(img.width, img.height, w, h)
        u['focusUsed'] = focus
        crop = cover_crop(img.width, img.height, w, h, tuple(focus), within)
        u['crop'] = crop
        u['static'] = comic_finish(upscale(img, crop, (w, h), sharpen=False))
        if u.get('clip'):
            rx, ry, rw, rh = u['reg']
            fw, fh = frames[0].size
            cbox = ((crop[0] - rx) * fw / rw, (crop[1] - ry) * fh / rh, crop[2] * fw / rw, crop[3] * fh / rh)
            u['clipbox'] = cbox
            u['raw'] = frames            # small source frames; upscaled + finished lazily (6 s clips at 1080p would not fit in RAM)
            u['size'] = (w, h)
            u['_cache'] = (None, None)

    def art(self, u, t):
        """Panel art at scene time t: static hold -> clip (3-frame crossfade in) -> freeze on last frame."""
        if not u.get('clip'):
            return u['static']
        t0 = T(self.spec, clip_start(self.spec, u))
        if t < t0:
            return u['static']
        i = min(int((t - t0) * self.fps), len(u['raw']) - 1)
        if u['_cache'][0] != i:
            u['_cache'] = (i, comic_finish(upscale(u['raw'][i], u['clipbox'], u['size'])))
        fr = u['_cache'][1]
        xf = 3 / self.fps
        if t - t0 < xf:
            return Image.blend(u['static'], fr, (t - t0) / xf)
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
        geo = u['geo']
        art = self.art(u, t)
        x0, y0 = geo['bbox'][:2]
        if geo['keyline']:   # keyline first so it sits under the art edge and over the panel below
            for p in geo['polys']:
                self._outline(img, p, w, keyline=True)
        fl = self._flash(u, t)
        if fl > 0:   # impact flash: the panel art blows out to white on the hit, then decays
            art = Image.blend(art, Image.new('RGB', art.size, (255, 252, 235)), fl)
        img.paste(art, (x0, y0), u['mask'])
        for p in geo['polys']:
            self._outline(img, p, w, keyline=geo['keyline'])
        if geo['burst']:     # the action breaks out over the border
            img.paste(art, (x0, y0), u['burstMask'])
            self._outline(img, geo['burst'], w)

    def _letter(self, img, u, t):
        slot = u['slotrect']
        S = TEXT_SAFE[self.orient]
        for c in u.get('captions', []):
            if t >= T(self.spec, c.get('at', u['at'])) and ('until' not in c or t < T(self.spec, c['until'])):
                draw_caption(img, c, slot, u['geo'], S)
        for s in u.get('sfx', []):
            ts = T(self.spec, s['at'])
            if t >= ts:
                k = min((t - ts) * self.fps / 3, 1.0)
                scale = 1.25 - 0.25 * ease(k)          # quick 3-frame stamp, then still
                rect, tile = sfx_rect(s, slot, scale, u['geo'], S, unit_caption_rects(u, slot, u['geo'], S))
                if (rect[2], rect[3]) != tile.size:
                    tile = tile.resize((rect[2], rect[3]), Image.BICUBIC)
                img.paste(tile, rect[:2], tile)

    def page(self, t, letters_only=None):
        img = self.paper.copy()
        for u in sorted(self.units, key=lambda u: u['geo']['z']):
            ta = T(self.spec, u['at'])
            if t < ta:
                continue
            k = ease((t - ta) / 0.14)
            if k < 1:
                fr = img.copy(); self._paint(fr, u, t)
                img = Image.blend(img, fr, k)
            else:
                self._paint(img, u, t)
        for u in self.units:
            if t >= T(self.spec, u['at']) and (letters_only is None or u['id'] == letters_only):
                self._letter(img, u, t)
        return img

    def splash_frame(self, t):
        img = self.paper.copy()
        u = self.splash
        self._paint(img, u, t, 9)
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

    def frame(self, t):
        img = self._frame(t)
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

    def _frame(self, t):
        tr = self.spec.get('transition')
        if not tr:
            return self.page(t)
        t_land = T(self.spec, tr['at'])
        dur = tr.get('dur', 0.4)
        if t >= t_land:
            return self.splash_frame(t)
        if t < t_land - dur:
            return self.page(t)
        # zoom into the target panel, then hard cut to the splash on the beat
        key = round(t_land - dur, 4)
        if key not in self._page_cache:
            # only the zoom target keeps its lettering: other panels' words would be sliced by the frame edge
            self._page_cache[key] = self.page(t_land - dur, letters_only=tr['panel'])
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
    fills = [CAPTION_FILL, (255, 70, 90)]
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


def endcard_frame(base, orient, ec):
    """Final frame: the last page dimmed under halftone, with the two lettering boxes on top."""
    W, H = SIZES[orient]
    if isinstance(base, np.ndarray):
        base = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGB')
    img = Image.blend(base.convert('RGB'), Image.new('RGB', (W, H), (20, 8, 40)), 0.62)
    dots = dot_field(W, H, 9.0)
    arr = np.asarray(img, np.float32)
    arr = arr * (1 - 0.25 * (dots < 0.22)[..., None])
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    for it in endcard_layout(ec, orient):
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
    return ic if ic.get('enabled', True) and ic.get('seconds', 0) > 0 else None


def intro_slam(spec, t0=None):
    """Video-relative time of the slam: the first downbeat at/after the video's first song second."""
    s0 = spec['song']['start'] if t0 is None else t0
    beats = [b for b in song_beats(spec) if b >= s0 + 0.15]
    return round(beats[0] - s0, 3) if beats else 0.4


def _intro_fonts(ic, orient):
    W, H = SIZES[orient]
    maxw = W * ic.get('width', 0.78) / INTRO_PEAK
    words = ic['title'].split()
    lines = [ic['title']] if orient == 'landscape' or len(words) < 2 else [' '.join(words[:len(words) // 2]), ' '.join(words[len(words) // 2:])]
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
    th = (sb[3] - sb[1] + gap if sub else 0) + sum(lh) + gap * (len(lines) - 1) + 2 * P
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
        m = (np.arange(th) >= y0 - sw) & (np.arange(th) <= y1 + sw)
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
def _intro_tile_cached(ic, orient):
    k = (json.dumps(ic, sort_keys=True), orient)
    if k not in _INTRO_CACHE:
        _INTRO_CACHE[k] = intro_tile(ic, orient)
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


def intro_frame(base, orient, ic, t, ts, fps=30):
    """Composite the logo intro over a rendered frame (video-relative time t, slam at ts)."""
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
    tl = tile if (int(r[2]), int(r[3])) == tile.size else tile.resize((max(1, int(r[2])), max(1, int(r[3]))), Image.BICUBIC)
    if a < 1:
        al = tl.getchannel('A').point(lambda v: int(v * a)); tl = tl.copy(); tl.putalpha(al)
    img.paste(tl, (int(round(r[0])), int(round(r[1]))), tl)
    _sparkles(img, r, t, ts)
    if flash > 0:
        img = Image.blend(img, Image.new('RGB', (W, H), (255, 255, 255)), flash)
    sb = intro_shake_box(orient, t, shake, fps)
    if sb:
        x0, y0, zw, zh = sb
        img = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + zw, y0 + zh))
    return img

#!/usr/bin/env python3
"""Music-mode FX engine: beat-snapped edits, still-panel parallax, looping procedural overlays, typography.

Deterministic: every random source is seeded from (preset seed, layer name), every timing comes from the
analysis timeline (scripts/analyze_music.py: beats, downbeats, kicks, snares, drops). Same inputs -> same frames.

CLI
  python3 scripts/music_fx.py snap      <timeline.json> --cuts 33.1,40.5,43.2 [--preset hard]      # print snapped times
  python3 scripts/music_fx.py layers    <panel.png> -o <dir> [--model isnet-general-use]          # fg.png / bg.png (inpainted)
  python3 scripts/music_fx.py render    <spec.json>                                                # mp4 (+ contact sheet)

Features (see docs/MUSIC_MODE.md, "FX engine"):
  a) SNAP_PRESETS     'hard' | 'beats' | 'drops_only' | 'loose'  -> snap_time(), snap_shots()
  b) PARALLAX_PRESETS 'locked_subtle' | 'locked_drift' | 'still'  -> make_layers(), Parallax
  c) OVERLAY_PRESETS  'crypt' | 'desert_night' | 'tomb_embers'    -> layers: sand, mist, dust, torch, embers
  d) TYPE_PRESETS     'comic_caption' | 'lyric_gold' | 'sfx'      -> Caption / LyricSnippet / SFX, auto-placed off faces
"""
import argparse, json, math, os, subprocess, sys, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = '/usr/share/fonts/truetype/sand-box/google'
FONT = {'caption': f'{FONTS}/Comic Relief/ComicRelief-Bold.ttf', 'lyric': f'{FONTS}/Cinzel Decorative/CinzelDecorative-Bold.ttf',
        'lyric_fallback': f'{FONTS}/Cinzel/Cinzel-VariableFont_wght.ttf', 'sfx': f'{FONTS}/Bangers/Bangers-Regular.ttf'}


def rng(seed, name):
    return np.random.default_rng(zlib.crc32(f'{seed}:{name}'.encode()))


def ease(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- a) beat-synced editing
SNAP_PRESETS = {
    # targets in priority order; window = max distance (s) a cut may move; prio_bonus favours earlier targets
    'hard':       {'targets': ['drops', 'snares', 'kicks'], 'window': 0.30, 'prio_bonus': 0.06, 'snap_shots_to_beats': False},
    'beats':      {'targets': ['drops', 'downbeats', 'beats'], 'window': 0.40, 'prio_bonus': 0.08, 'snap_shots_to_beats': True},
    'drops_only': {'targets': ['drops'], 'window': 1.20, 'prio_bonus': 0.0, 'snap_shots_to_beats': False},
    'loose':      {'targets': ['drops', 'kicks', 'snares', 'beats'], 'window': 0.15, 'prio_bonus': 0.03, 'snap_shots_to_beats': False},
}


def _targets(tl, key):
    v = tl.get(key, [])
    return [x['t'] if isinstance(x, dict) else x for x in v]


def snap_time(t, tl, preset='hard', **over):
    """Snap t to the nearest transient. Returns (snapped_t, kind). Within the window, a higher-priority
    target wins if it is no more than prio_bonus*rank further away (drops beat snares beat kicks)."""
    p = {**SNAP_PRESETS[preset], **over}
    best = (None, 'none', 1e9)
    for rank, key in enumerate(p['targets']):
        ts = _targets(tl, key)
        if not ts: continue
        a = np.asarray(ts); i = int(np.abs(a - t).argmin()); d = abs(a[i] - t)
        if d > p['window']: continue
        score = d + rank * p['prio_bonus']
        if score < best[2]: best = (float(a[i]), key, score)
    return (round(best[0], 3), best[1]) if best[0] is not None else (round(t, 3), 'none')


def snap_shots(shots, tl, preset='hard', fps=30, **over):
    """shots: [{'t':start,'end':end,...}] in song seconds. Every boundary (and every 'hits' punch time) is
    snapped; with snap_shots_to_beats the boundary snaps to the beat grid instead. Frame-quantised."""
    p = {**SNAP_PRESETS[preset], **over}
    out = [dict(s) for s in shots]
    q = lambda t: round(round(t * fps) / fps, 4)
    for i in range(1, len(out)):
        t = out[i]['t']
        if p['snap_shots_to_beats']:
            nt, kind = snap_time(t, tl, preset, targets=['drops', 'beats'])
        else:
            nt, kind = snap_time(t, tl, preset)
        out[i]['t'] = out[i - 1]['end'] = q(nt); out[i]['cut_on'] = kind
    for s in out:
        s['hits'] = [dict(h, t=q(snap_time(h['t'], tl, preset)[0]), on=snap_time(h['t'], tl, preset)[1]) for h in s.get('hits', [])]
    return out


# ---------------------------------------------------------------- b) parallax depth
PARALLAX_PRESETS = {
    # amplitude in px at 1280-wide output per layer (far, mid, fg), period s; locked camera: no zoom, ever
    'locked_subtle': {'amp': [7.0, 3.5, 1.2], 'period': 9.0, 'vert': 0.35},
    'locked_drift':  {'amp': [12.0, 6.0, 2.0], 'period': 7.0, 'vert': 0.25},
    'still':         {'amp': [0, 0, 0], 'period': 9.0, 'vert': 0},
}


def solid_mask(alpha, thr=40):
    """rembg alpha on stringy subjects (bandages, hair) is see-through; make it a solid silhouette:
    threshold, close, fill enclosed holes, feather 1.5 px."""
    import cv2
    m = (alpha > thr).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    cs, h = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if h is not None:
        for i, c in enumerate(cs):
            if h[0][i][3] >= 0 and cv2.contourArea(c) < 0.004 * m.size: cv2.drawContours(m, [c], -1, 255, -1)
    # keep the largest components only (drops stray mist blobs)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        big = st[1:, cv2.CC_STAT_AREA].max()
        keep = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 0.05 * big]
        m = np.isin(lab, keep).astype(np.uint8) * 255
    return cv2.GaussianBlur(m, (0, 0), 1.5)


def make_layers(panel_path, out_dir, model='isnet-general-use', solid=True):
    """Still panel -> fg.png (RGBA subject), bg.png (subject removed, hole inpainted), mask.png. Cached."""
    import cv2
    os.makedirs(out_dir, exist_ok=True)
    fg_p, bg_p, m_p = (os.path.join(out_dir, n) for n in ('fg.png', 'bg.png', 'mask.png'))
    if all(os.path.exists(p) and os.path.getmtime(p) > os.path.getmtime(panel_path) for p in (fg_p, bg_p, m_p)):
        return fg_p, bg_p, m_p
    from rembg import remove, new_session
    im = Image.open(panel_path).convert('RGB')
    cut = remove(im, session=new_session(model))
    a = np.asarray(cut)[:, :, 3]
    m = solid_mask(a) if solid else a
    rgb = np.asarray(im)
    Image.fromarray(np.dstack([rgb, m])).save(fg_p); Image.fromarray(m).save(m_p)
    hole = cv2.dilate((m > 8).astype(np.uint8) * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    # inpaint at half res (big holes: Telea smears; downscale-inpaint-upscale keeps it soft and fast) then blur the fill
    s = 0.5; small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    hs = cv2.resize(hole, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    fill = cv2.inpaint(small, hs, 9, cv2.INPAINT_TELEA)
    fill = cv2.GaussianBlur(cv2.resize(fill, (bgr.shape[1], bgr.shape[0])), (0, 0), 6)
    k = (cv2.GaussianBlur(hole, (0, 0), 6) / 255.0)[..., None]
    out = (bgr * (1 - k) + fill * k).astype(np.uint8)
    cv2.imwrite(bg_p, out)
    return fg_p, bg_p, m_p


class Parallax:
    """Locked-camera drift: each layer translates by amp*sin(phase) (sub-pixel, via affine warp).
    Far moves most against fg so depth reads, fg barely moves. No scale change -> no push-in on faces."""
    def __init__(self, preset='locked_subtle', seed=1, scale=1.0):
        self.p = PARALLAX_PRESETS[preset]; self.scale = scale
        r = rng(seed, 'parallax'); self.ph = r.uniform(0, 2 * math.pi, 3)

    def offset(self, layer, t):
        a = self.p['amp'][layer] * self.scale; w = 2 * math.pi / self.p['period']
        sign = -1 if layer == 2 else 1
        return (sign * a * math.sin(w * t + self.ph[0]), sign * a * self.p['vert'] * math.sin(0.7 * w * t + self.ph[1]))


def shift(img, dx, dy):
    import cv2
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ---------------------------------------------------------------- c) localized looping overlays
def region_mask(W, H, spec):
    """spec: 'full' | 'floor' (bottom 35 %, feathered) | 'top' | {'ellipse':[cx,cy,rx,ry]} | {'rect':[x0,y0,x1,y1]}
    (fractions of frame). Returns float32 HxW 0..1."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if spec == 'full': return np.ones((H, W), np.float32)
    if spec == 'floor': return np.clip((yy / H - 0.70) / 0.2, 0, 1)
    if spec == 'top': return np.clip((0.35 - yy / H) / 0.2, 0, 1)
    if 'ellipse' in spec:
        cx, cy, rx, ry = spec['ellipse']
        d = ((xx / W - cx) / rx) ** 2 + ((yy / H - cy) / ry) ** 2
        return np.clip(1.2 - d, 0, 1).astype(np.float32)
    if 'rect' in spec:
        x0, y0, x1, y1 = spec['rect']; m = np.zeros((H, W), np.float32)
        m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = 1
        import cv2; return cv2.GaussianBlur(m, (0, 0), 0.04 * W)
    raise ValueError(spec)


def blend(base, layer, alpha, mode):
    """base, layer float32 0..1 HxWx3; alpha HxW. Modes: screen, add, multiply, normal, softlight."""
    a = alpha[..., None]
    if mode == 'screen': mix = 1 - (1 - base) * (1 - layer)
    elif mode == 'add': mix = np.minimum(1, base + layer)
    elif mode == 'multiply': mix = base * layer
    elif mode == 'softlight': mix = (1 - 2 * layer) * base * base + 2 * layer * base
    else: mix = layer
    return base * (1 - a) + mix * a


class Particles:
    """Seeded particle field that loops with period `loop` s (positions are a pure function of t mod loop).
    kind: sand (fast low horizontal streaks), dust (slow motes, bokeh), embers (rise, flicker, orange)."""
    CFG = {
        'sand':   {'n': 420, 'vel': (260, -6), 'jit': 40, 'size': (1, 2.2), 'color': (0.86, 0.72, 0.48), 'alpha': 0.55, 'streak': 9},
        'dust':   {'n': 90, 'vel': (6, -4), 'jit': 10, 'size': (1.5, 4.5), 'color': (0.9, 0.85, 0.7), 'alpha': 0.35, 'streak': 0},
        'embers': {'n': 46, 'vel': (8, -70), 'jit': 25, 'size': (1.4, 3.2), 'color': (1.0, 0.55, 0.15), 'alpha': 0.9, 'streak': 3},
    }

    def __init__(self, kind, W, H, region='full', seed=1, loop=6.0, density=1.0, color=None, mode='screen', strength=1.0):
        import cv2
        c = self.CFG[kind]; self.k, self.W, self.H, self.loop, self.mode, self.strength = kind, W, H, loop, mode, strength
        r = rng(seed, kind); n = int(c['n'] * density * (W * H) / (1280 * 720))
        self.mask = region_mask(W, H, region)
        self.p0 = r.uniform(0, 1, (n, 2)) * [W, H]
        # velocities chosen so every particle travels an integer number of wraps per loop -> seamless loop
        v = np.asarray(c['vel'], np.float32) + r.normal(0, c['jit'], (n, 2))
        self.v = np.round(v * loop / [W, H]) * [W, H] / loop
        self.v[np.all(self.v == 0, axis=1)] = [W / loop, 0] if kind == 'sand' else [0, -H / loop]
        self.size = r.uniform(*c['size'], n); self.ph = r.uniform(0, 2 * math.pi, n)
        self.color = np.asarray(color or c['color'], np.float32); self.alpha = c['alpha']; self.streak = c['streak']
        self.cv2 = cv2

    def render(self, t):
        cv2 = self.cv2; W, H = self.W, self.H
        tt = t % self.loop
        pos = (self.p0 + self.v * tt) % [W, H]
        acc = np.zeros((H, W), np.float32)
        tw = 0.6 + 0.4 * np.sin(2 * math.pi * tt / self.loop * 3 + self.ph)  # integer cycles per loop
        for (x, y), s, (vx, vy), a in zip(pos, self.size, self.v, tw):
            if self.streak:
                L = self.streak * s / max(1e-3, math.hypot(vx, vy)) * 3
                cv2.line(acc, (int(x), int(y)), (int(x - vx * L * 0.01), int(y - vy * L * 0.01)), float(a), max(1, int(s)), cv2.LINE_AA)
            cv2.circle(acc, (int(x), int(y)), max(1, int(round(s))), float(a), -1, cv2.LINE_AA)
        acc = cv2.GaussianBlur(acc, (0, 0), 0.8 if self.k != 'dust' else 1.6)
        if self.k == 'embers': acc += cv2.GaussianBlur(acc, (0, 0), 5) * 1.5
        al = np.clip(acc * self.alpha * self.strength, 0, 1) * self.mask
        return np.broadcast_to(self.color, (H, W, 3)), al


class Mist:
    """Green mist: two octaves of seeded value noise scrolled on a loop, masked to a region, screen blend."""
    def __init__(self, W, H, region='floor', seed=1, loop=8.0, color=(0.35, 1.0, 0.45), strength=0.55, mode='screen'):
        import cv2
        r = rng(seed, 'mist'); self.W, self.H, self.loop, self.mode, self.strength = W, H, loop, mode, strength
        self.mask = region_mask(W, H, region); self.color = np.asarray(color, np.float32)
        def tile(cell):
            g = r.uniform(0, 1, (H // cell + 2, W // cell + 2)).astype(np.float32)
            g[:, -1] = g[:, 0]; return cv2.resize(g, (W + 2 * cell, H + 2 * cell), interpolation=cv2.INTER_CUBIC)[:H, :W]
        self.a = cv2.GaussianBlur(tile(160), (0, 0), 30); self.b = cv2.GaussianBlur(tile(60), (0, 0), 12)

    def render(self, t):
        f = (t % self.loop) / self.loop
        a = np.roll(self.a, int(f * self.W), axis=1); b = np.roll(self.b, -int(f * self.W), axis=1)
        n = np.clip((0.65 * a + 0.35 * b - 0.35) * 2.2, 0, 1)
        return np.broadcast_to(self.color, (self.H, self.W, 3)), n * self.mask * self.strength


class TorchLight:
    """Flickering light pools at torch positions (fractions). Flicker = sum of 3 sines with seeded
    incommensurate-but-looping freqs (integer cycles per loop). Additive-ish (screen) warm or green light."""
    def __init__(self, W, H, torches, seed=1, loop=4.0, color=(1.0, 0.62, 0.25), radius=0.28, strength=0.55, mode='screen'):
        r = rng(seed, 'torch'); self.W, self.H, self.loop, self.mode, self.strength = W, H, loop, mode, strength
        self.color = np.asarray(color, np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.pools = [np.exp(-(((xx / W - x) / radius) ** 2 + ((yy / H - y) / (radius * 1.2)) ** 2) * 2.2) for x, y in torches]
        self.f = r.integers(3, 11, (len(torches), 3)); self.ph = r.uniform(0, 6.28, (len(torches), 3))

    def render(self, t):
        u = 2 * math.pi * (t % self.loop) / self.loop
        al = np.zeros((self.H, self.W), np.float32)
        for p, f, ph in zip(self.pools, self.f, self.ph):
            k = 0.72 + 0.12 * math.sin(f[0] * u + ph[0]) + 0.09 * math.sin(f[1] * u + ph[1]) + 0.07 * math.sin(f[2] * u + ph[2])
            al += p * k
        return np.broadcast_to(self.color, (self.H, self.W, 3)), np.clip(al * self.strength, 0, 1)


OVERLAY_PRESETS = {
    'crypt': [
        {'type': 'torch', 'torches': [[0.12, 0.42], [0.88, 0.42]], 'color': [0.45, 1.0, 0.4], 'strength': 0.45},
        {'type': 'mist', 'region': 'floor', 'strength': 0.3},
        {'type': 'dust', 'region': 'full', 'density': 1.0},
        {'type': 'embers', 'region': {'ellipse': [0.12, 0.38, 0.09, 0.35]}, 'color': [0.5, 1.0, 0.35]},
        {'type': 'embers', 'region': {'ellipse': [0.88, 0.38, 0.09, 0.35]}, 'color': [0.5, 1.0, 0.35]},
        {'type': 'sand', 'region': 'floor', 'density': 0.6},
    ],
    'desert_night': [
        {'type': 'sand', 'region': {'rect': [0, 0.45, 1, 1]}, 'density': 1.4},
        {'type': 'dust', 'region': 'full', 'density': 0.6},
    ],
    'tomb_embers': [
        {'type': 'torch', 'torches': [[0.5, 0.95]], 'strength': 0.5},
        {'type': 'embers', 'region': {'rect': [0.1, 0.3, 0.9, 1]}, 'density': 2.0},
        {'type': 'mist', 'region': 'floor', 'strength': 0.35},
    ],
}


def build_overlays(spec, W, H, seed=1):
    """spec: preset name or list of layer dicts. Every layer accepts region, mode (blend), strength/density, loop."""
    layers = OVERLAY_PRESETS[spec] if isinstance(spec, str) else spec
    out = []
    for i, L in enumerate(layers):
        L = dict(L); typ = L.pop('type'); s = seed * 100 + i
        if typ == 'torch': out.append(TorchLight(W, H, L.pop('torches'), seed=s, **L))
        elif typ == 'mist': out.append(Mist(W, H, seed=s, **L))
        else: out.append(Particles(typ, W, H, seed=s, **L))
    return out


def apply_overlays(frame, layers, t):
    f = frame.astype(np.float32) / 255
    for L in layers:
        col, al = L.render(t); f = blend(f, col, al, L.mode)
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)


# ---------------------------------------------------------------- d) typography
TYPE_PRESETS = {
    'comic_caption': {'font': 'caption', 'size': 30, 'fill': (255, 236, 160), 'ink': (20, 16, 10), 'pad': 16, 'border': 3, 'max_w': 0.34, 'upper': True},
    'lyric_gold':    {'font': 'lyric', 'size': 58, 'ink': (238, 196, 92), 'stroke': (30, 12, 0), 'stroke_w': 4, 'glow': (80, 255, 120), 'max_w': 0.42, 'upper': True},
    'sfx':           {'font': 'sfx', 'size': 130, 'ink': (255, 222, 0), 'stroke': (0, 0, 0), 'stroke_w': 8, 'burst': (220, 30, 20)},
}


def detect_faces(rgb, fg_mask=None):
    """Faces in frame px. OpenCV Haar (frontal) first; stylised heads (skulls, masks, robots) usually fail Haar,
    so fall back to the subject mask: the head box = top 16 % of the silhouette bbox, widened 20 %."""
    import cv2
    faces = []
    if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):  # OpenCV 5 dropped Haar: mask fallback only
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        cc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = [[x, y, x + w, y + h] for x, y, w, h in cc.detectMultiScale(g, 1.1, 6, minSize=(40, 40))]
    if not faces and fg_mask is not None and (fg_mask > 128).any():
        ys, xs = np.where(fg_mask > 128); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        hh = (y1 - y0) * 0.16; cx = (x0 + x1) / 2; hw = max(hh * 0.8, (x1 - x0) * 0.22)
        faces = [[int(cx - hw * 1.2), int(y0), int(cx + hw * 1.2), int(y0 + hh * 1.2)]]
    return faces


def _font(key, size):
    p = FONT.get(key)
    if not p or not os.path.exists(p): p = FONT['lyric_fallback'] if key == 'lyric' else FONT['caption']
    return ImageFont.truetype(p, size)


def _wrap(draw, text, font, max_px):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= max_px or not cur: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur] if cur else lines


def place(box_wh, W, H, avoid, prefer=('top_left', 'top_right', 'bottom_left', 'bottom_right', 'top', 'bottom'), margin=0.04,
          busy=None):
    """Pick the first preferred slot whose rect does not touch any avoid rect (faces + subject), else the one
    with least overlap. busy: optional HxW 0..1 map (subject mask) also scored."""
    w, h = box_wh; m = int(margin * W)
    slots = {'top_left': (m, m), 'top_right': (W - w - m, m), 'bottom_left': (m, H - h - m), 'bottom_right': (W - w - m, H - h - m),
             'top': ((W - w) // 2, m), 'bottom': ((W - w) // 2, H - h - m), 'left': (m, (H - h) // 2), 'right': (W - w - m, (H - h) // 2)}
    best = None
    for k in prefer:
        x, y = slots[k]; r = [x, y, x + w, y + h]
        ov = sum(max(0, min(r[2], a[2]) - max(r[0], a[0])) * max(0, min(r[3], a[3]) - max(r[1], a[1])) for a in avoid) * 10
        if busy is not None: ov += float(busy[max(0, y):y + h, max(0, x):x + w].sum())
        if ov == 0: return r, k
        if best is None or ov < best[0]: best = (ov, r, k)
    return best[1], best[2]


def ease_out_back(x):
    x = min(1, max(0, x)); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


class TypeLayer:
    """Caption boxes, lyric snippets and SFX, drawn in an RGBA PIL layer per frame.
    cues: [{'kind':'caption'|'lyric'|'sfx', 't':, 'end':, 'text':, 'preset':?, 'cue':? (sfx only), 'at':? [x,y] fractions}]
    Rules enforced: SFX needs an explicit 'cue' (what motivates it); text 'BAM' at most once per video;
    placement never overlaps faces (detect_faces) and avoids the subject mask."""
    def __init__(self, W, H, cues):
        bams = [c for c in cues if c['kind'] == 'sfx' and 'BAM' in c['text'].upper()]
        if len(bams) > 1: raise ValueError('BAM at most once per video')
        for c in cues:
            if c['kind'] == 'sfx' and not c.get('cue'): raise ValueError(f"SFX '{c['text']}' has no motivating cue")
        self.W, self.H, self.cues, self.slot = W, H, cues, {}

    def draw(self, frame, t, faces, busy=None):
        img = Image.fromarray(frame).convert('RGBA'); W, H = self.W, self.H
        for i, c in enumerate(self.cues):
            if not (c['t'] <= t < c['end']): continue
            p = TYPE_PRESETS[c.get('preset') or {'caption': 'comic_caption', 'lyric': 'lyric_gold', 'sfx': 'sfx'}[c['kind']]]
            age, left = t - c['t'], c['end'] - t
            fade = min(1, age / 0.18, left / 0.22)
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
            text = c['text'].upper() if p.get('upper') else c['text']
            if c['kind'] == 'sfx':
                s = ease_out_back(age / 0.22); f = _font('sfx', int(p['size'] * max(0.2, s)))
                tw = d.textlength(text, font=f); th = f.size
                if i not in self.slot:
                    r, _ = place((int(tw * 1.5), int(th * 1.6)), W, H, faces, prefer=('top_right', 'top_left', 'right', 'left'), busy=busy)
                    self.slot[i] = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
                cx, cy = self.slot[i]
                R = rng(7, text); n = 14; pts = []
                for k in range(2 * n):
                    a = math.pi * k / n; rr = (1.0 if k % 2 == 0 else 0.62 + 0.1 * R.random())
                    pts.append((cx + math.cos(a) * tw * 0.78 * rr * s, cy + math.sin(a) * th * 1.0 * rr * s))
                d.polygon(pts, fill=p['burst'] + (255,), outline=(0, 0, 0, 255), width=5)
                d.text((cx, cy), text, font=f, fill=p['ink'], stroke_width=p['stroke_w'], stroke_fill=p['stroke'], anchor='mm')
            else:
                f = _font(p['font'], p['size']); lines = _wrap(d, text, f, p['max_w'] * W)
                lh = int(f.size * 1.18); tw = max(d.textlength(l, font=f) for l in lines); th = lh * len(lines)
                pad = p.get('pad', 10)
                if i not in self.slot:
                    pref = c.get('prefer') or (('top_left', 'top_right', 'bottom_left') if c['kind'] == 'caption' else ('left', 'right', 'bottom_left', 'bottom_right', 'top'))
                    self.slot[i] = place((int(tw + 2 * pad), int(th + 2 * pad)), W, H, faces, prefer=pref, busy=busy)[0]
                x0, y0, x1, y1 = self.slot[i]
                if c['kind'] == 'caption':
                    d.rectangle([x0 + 6, y0 + 6, x1 + 6, y1 + 6], fill=(0, 0, 0, 150))
                    d.rectangle([x0, y0, x1, y1], fill=p['fill'] + (255,), outline=p['ink'] + (255,), width=p['border'])
                    for k, l in enumerate(lines): d.text((x0 + pad, y0 + pad + k * lh), l, font=f, fill=p['ink'])
                else:
                    # lettering reveal: words appear in sequence over the first 40 % of the cue
                    words = text.split(); nshow = max(1, int(len(words) * min(1, age / max(0.3, (c['end'] - c['t']) * 0.4)) + 0.999))
                    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
                    shown, k = 0, 0
                    for li, l in enumerate(lines):
                        ws = l.split(); vis = ' '.join(ws[:max(0, nshow - shown)]); shown += len(ws)
                        if vis:
                            pos = (x0 + pad, y0 + pad + li * lh)
                            gd.text(pos, vis, font=f, fill=p['glow'] + (200,))
                            d.text(pos, vis, font=f, fill=p['ink'], stroke_width=p['stroke_w'], stroke_fill=p['stroke'])
                    glow = glow.filter(ImageFilter.GaussianBlur(10)); img.alpha_composite(glow)
            if fade < 1: layer.putalpha(layer.getchannel('A').point(lambda v: int(v * fade)))
            img.alpha_composite(layer)
            c.setdefault('_rects', []).append(self.slot[i] if c['kind'] != 'sfx' else None)
        return np.asarray(img.convert('RGB'))


# ---------------------------------------------------------------- render (composes a, b, c, d)
def crypt_background(W, H, seed=3):
    """Dark generated crypt: vertical gradient, stone block courses, an arch, carved glyph marks, vignette."""
    import cv2
    r = rng(seed, 'crypt')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.dstack([0.05 + 0.05 * (1 - yy / H), 0.07 + 0.07 * (1 - yy / H), 0.06 + 0.04 * (1 - yy / H)])
    img = (base * 255).astype(np.uint8).copy()
    bh = H // 9
    for row in range(10):
        off = (row % 2) * 70
        for x in range(-140 + off, W + 140, 140):
            v = int(r.integers(-6, 10)); y = row * bh
            cv2.rectangle(img, (x + 2, y + 2), (x + 138, y + bh - 2), tuple(max(0, int(c) + v) for c in img[min(H - 1, y + 4), max(0, min(W - 1, x + 4))]), -1)
            cv2.rectangle(img, (x, y), (x + 140, y + bh), (6, 8, 7), 2)
    for _ in range(60):  # glyph marks
        x, y = int(r.uniform(0.02, 0.98) * W), int(r.uniform(0.05, 0.6) * H); s = int(r.uniform(6, 14))
        k = int(r.integers(0, 3))
        if k == 0: cv2.circle(img, (x, y), s, (20, 30, 24), 2)
        elif k == 1: cv2.line(img, (x, y - s), (x, y + s), (20, 30, 24), 2); cv2.line(img, (x - s, y), (x + s, y), (20, 30, 24), 2)
        else: cv2.ellipse(img, (x, y), (s, s // 2), 0, 0, 360, (22, 32, 26), 2)
    arch = np.zeros((H, W), np.uint8)
    cv2.ellipse(arch, (W // 2, int(H * 0.42)), (int(W * 0.2), int(H * 0.3)), 0, 180, 360, 255, -1)
    cv2.rectangle(arch, (int(W * 0.3), int(H * 0.42)), (int(W * 0.7), H), 255, -1)
    arch = cv2.GaussianBlur(arch, (0, 0), 6) / 255.0
    img = (img * (1 - 0.8 * arch[..., None])).astype(np.uint8)
    floor = np.clip((yy / H - 0.8) / 0.2, 0, 1)[..., None]
    img = (img * (1 - floor) + np.array([10, 18, 14]) * floor).astype(np.uint8)
    vig = 1 - 0.65 * np.clip(((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2.2, 0, 1)
    img = (img * vig[..., None]).astype(np.uint8)
    for tx in (0.12, 0.88):  # torch sconces
        cx, cy = int(tx * W), int(0.47 * H)
        cv2.rectangle(img, (cx - 9, cy), (cx + 9, cy + 40), (40, 42, 38), -1)
        cv2.ellipse(img, (cx, cy - 8), (14, 26), 0, 0, 360, (90, 255, 110), -1)
        cv2.ellipse(img, (cx, cy - 4), (7, 14), 0, 0, 360, (210, 255, 210), -1)
    return cv2.GaussianBlur(img, (0, 0), 0.7)


def _paste(dst, rgba, x, y, scale):
    """alpha-composite rgba (np HxWx4) scaled onto dst float RGB at x,y (top-left, can be fractional/offscreen)."""
    import cv2
    h, w = rgba.shape[:2]; nw, nh = int(w * scale), int(h * scale)
    s = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    M = np.float32([[1, 0, x - int(x)], [0, 1, y - int(y)]]); s = cv2.warpAffine(s, M, (nw, nh))
    X, Y = int(x), int(y); H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(0, X), max(0, Y), min(W, X + nw), min(H, Y + nh)
    if x1 <= x0 or y1 <= y0: return np.zeros((H, W), np.float32)
    sub = s[y0 - Y:y1 - Y, x0 - X:x1 - X].astype(np.float32) / 255
    a = sub[..., 3:4]; dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * a
    m = np.zeros((H, W), np.float32); m[y0:y1, x0:x1] = a[..., 0]; return m


def render(spec_path):
    """spec JSON: {timeline, audio, t0, t1, out, size:[W,H], fps, seed, snap:'hard', parallax:'locked_subtle',
    overlays:'crypt', background:'crypt'|path, panel, layers_dir,
    shots:[{t,end,frame:{x,y,h}(subject placement: center x frac, feet y frac, height frac), mid_opacity, expand:true,
            hits:[{t, kind:'punch'}]}], type:[cues]}. All times are song seconds."""
    import cv2
    S = json.load(open(spec_path)); base = os.path.dirname(os.path.abspath(spec_path))
    P = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    tl = json.load(open(P(S['timeline']))); W, H = S.get('size', [1280, 720]); fps = S.get('fps', 30); seed = S.get('seed', 1)
    t0, t1 = S['t0'], S['t1']
    shots = snap_shots(S['shots'], tl, S.get('snap', 'hard'), fps)
    shots[0]['t'] = t0; shots[-1]['end'] = t1
    for c in S.get('type', []):
        if c.get('snap'):
            c['t'] = snap_time(c['t'], tl, S.get('snap', 'hard'))[0]
    fg_p, bg_p, _ = make_layers(P(S['panel']), P(S.get('layers_dir', 'layers')))
    fg = np.asarray(Image.open(fg_p).convert('RGBA')); midbg = np.asarray(Image.open(bg_p).convert('RGB'))
    far = crypt_background(W, H, seed) if S.get('background', 'crypt') == 'crypt' else np.asarray(Image.open(P(S['background'])).convert('RGB').resize((W, H)))
    # mid layer: inpainted panel background, feathered into the far layer (oval alpha)
    mh, mw = midbg.shape[:2]; yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    moval = np.clip(1.4 - (((xx / mw - 0.5) / 0.5) ** 2 + ((yy / mh - 0.45) / 0.55) ** 2), 0, 1)
    mid = np.dstack([midbg, (moval * 255).astype(np.uint8)])
    par = Parallax(S.get('parallax', 'locked_subtle'), seed, W / 1280)
    ovs = build_overlays(S.get('overlays', 'crypt'), W, H, seed)
    typ = TypeLayer(W, H, S.get('type', []))
    out = P(S['out']); os.makedirs(os.path.dirname(out), exist_ok=True)
    n = int(round((t1 - t0) * fps))
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                           '-ss', str(t0), '-t', str(t1 - t0), '-i', P(S['audio']), '-map', '0:v', '-map', '1:a',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k',
                           '-af', f'afade=t=in:d=0.15,afade=t=out:st={t1 - t0 - 0.4}:d=0.4', '-shortest', out], stdin=subprocess.PIPE)
    log, samples = [], []
    sample_at = [t0 + (t1 - t0) * (k + 0.5) / 12 for k in range(12)]
    for k in range(n):
        t = t0 + k / fps
        sh = next(s for s in shots if s['t'] <= t < s['end'] + 1e-6) if any(s['t'] <= t < s['end'] + 1e-6 for s in shots) else shots[-1]
        fr = sh.get('frame', {'x': 0.5, 'y': 0.97, 'h': 0.9}); lt = t - t0
        canvas = shift(far, *par.offset(0, lt)).astype(np.float32) / 255
        sc = fr['h'] * H / fg.shape[0]
        cx, fy = fr['x'] * W, fr['y'] * H
        ox, oy = par.offset(1, lt)
        msc = sc * 1.08
        m2 = mid.copy(); m2[..., 3] = (m2[..., 3] * sh.get('mid_opacity', 0.75)).astype(np.uint8)
        _paste(canvas, m2, cx - mid.shape[1] * msc / 2 + ox, fy - mid.shape[0] * msc + oy + mid.shape[0] * msc * 0.03, msc)
        fx, fyo = par.offset(2, lt)
        fgm = _paste(canvas, fg, cx - fg.shape[1] * sc / 2 + fx, fy - fg.shape[0] * sc + fyo, sc)
        frame = (np.clip(canvas, 0, 1) * 255).astype(np.uint8)
        frame = apply_overlays(frame, ovs, lt)
        # punch-ins / panel expansion, hard on the snapped transient (frame scale, not a face push; 3-frame snap, 8-frame settle)
        z = 1.0
        for h in sh.get('hits', []):
            dt = t - h['t']
            if 0 <= dt < 0.35: z = max(z, 1 + h.get('amount', 0.035) * (1 - ease(dt / 0.35)))
        if sh.get('expand', True) and sh is not shots[0]:
            dt = t - sh['t']; inset = 0.07 * (1 - ease(dt / 0.2)) if dt < 0.2 else 0
        else: inset = 0
        if z > 1.0001:
            cw, ch = int(W / z), int(H / z); x0, y0 = (W - cw) // 2, (H - ch) // 2
            frame = cv2.resize(frame[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_LINEAR)
            fgm = cv2.resize(fgm[y0:y0 + ch, x0:x0 + cw], (W, H))
        if inset > 0:  # new panel expands from a bordered inset to full frame
            iw, ih = int(W * (1 - inset)), int(H * (1 - inset)); small = cv2.resize(frame, (iw, ih))
            fr2 = np.full_like(frame, 8); x0, y0 = (W - iw) // 2, (H - ih) // 2
            fr2[y0:y0 + ih, x0:x0 + iw] = small; cv2.rectangle(fr2, (x0 - 3, y0 - 3), (x0 + iw + 2, y0 + ih + 2), (235, 230, 215), 5)
            frame = fr2
        faces = detect_faces(frame, (fgm * 255).astype(np.uint8))
        busy = cv2.resize(fgm, (W, H)) if fgm.shape != (H, W) else fgm
        frame = typ.draw(frame, t, faces, busy)
        ff.stdin.write(frame.tobytes())
        if any(abs(t - s) < 0.5 / fps for s in sample_at): samples.append((t, frame.copy()))
        if k % fps == 0: log.append({'t': round(t, 3), 'shot': shots.index(sh), 'faces': faces})
    ff.stdin.close(); ff.wait()
    if S.get('contact'):
        tw, th = W // 4, H // 4; sheet = Image.new('RGB', (tw * 4, th * 3), (0, 0, 0)); d = ImageDraw.Draw(sheet)
        for i, (t, f) in enumerate(samples[:12]):
            sheet.paste(Image.fromarray(f).resize((tw, th)), ((i % 4) * tw, (i // 4) * th)); d.text(((i % 4) * tw + 6, (i // 4) * th + 4), f'{t:.2f}s', fill=(255, 255, 0))
        sheet.save(P(S['contact']), quality=90)
    plan = {'shots': [{k: v for k, v in s.items()} for s in shots], 'type': [{k: v for k, v in c.items() if k != '_rects'} for c in S.get('type', [])], 'log': log}
    json.dump(plan, open(os.path.splitext(out)[0] + '.plan.json', 'w'), indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    print(f'rendered {out} ({n} frames)'); return plan


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('snap'); a.add_argument('timeline'); a.add_argument('--cuts', required=True); a.add_argument('--preset', default='hard')
    b = sp.add_parser('layers'); b.add_argument('panel'); b.add_argument('-o', required=True); b.add_argument('--model', default='isnet-general-use')
    c = sp.add_parser('render'); c.add_argument('spec')
    x = ap.parse_args()
    if x.cmd == 'snap':
        tl = json.load(open(x.timeline))
        for t in map(float, x.cuts.split(',')): print(t, '->', *snap_time(t, tl, x.preset))
    elif x.cmd == 'layers': print(*make_layers(x.panel, x.o, x.model))
    else: render(x.spec)


if __name__ == '__main__':
    main()

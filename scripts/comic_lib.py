"""Comic mode: shared layout, timing and drawing code for comic_render.py and comic_qa.py.

A comic scene is a JSON spec (shots/<name>/<name>.comic.json) listing panels in reading
order. Each panel lands on a beat in a slot of a page layout, holds as a static panel,
optionally plays a short trimmed Grok Imagine clip inside its frame, then freezes on the
clip's last frame. A transition (zoom into a panel) leads to a full-frame splash.
All "at" times in the spec are SONG seconds; scene time = song time - song.start.
"""
import json, math, os, subprocess, shutil, urllib.request
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

def layout(orient):
    """Slot rects (x, y, w, h) for each orientation. 'splash' is the full-frame splash slot."""
    W, H = SIZES[orient]
    if orient == 'landscape':
        m, g = 36, 24
        tw = (W - 2 * m - g) // 2
        th = round(tw * 9 / 16)
        by = m + th + g
        return {'top-left': (m, m, tw, th), 'top-right': (m + tw + g, m, tw, th),
                'bottom': (m, by, W - 2 * m, H - m - by), 'splash': (14, 14, W - 28, H - 28)}
    w = 1000
    h = round(w * 9 / 16)
    g = 28
    top = (H - (3 * h + 2 * g)) // 2
    x = (W - w) // 2
    return {'top-left': (x, top, w, h), 'top-right': (x, top + h + g, w, h),
            'bottom': (x, top + 2 * (h + g), w, h), 'splash': (x, 400, w, 1120)}

def base_px(slot):
    return math.sqrt(slot[2] * slot[3]) * 0.75

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

def caption_box(cap, slot):
    """Returns (rect, lines, font) for a caption box pinned to a slot corner."""
    px = int(min(max(base_px(slot) * cap.get('size', 0.072), 32), 52))
    f = font(px)
    pad = int(px * 0.45)
    lines = wrap(cap['text'], f, slot[2] * cap.get('maxw', 0.6) - 2 * pad)
    lh = int(px * 1.08)
    w = int(max(f.getlength(l) for l in lines) + 2 * pad)
    h = int(lh * len(lines) + 2 * pad - (lh - px) + 4)
    a = cap.get('anchor', 'tl')
    x = slot[0] if a[1] == 'l' else slot[0] + slot[2] - w
    y = slot[1] if a[0] == 't' else slot[1] + slot[3] - h
    return (x, y, w, h), lines, f, pad, lh

def draw_caption(img, cap, slot):
    (x, y, w, h), lines, f, pad, lh = caption_box(cap, slot)
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=cap.get('fill') and tuple(cap['fill']) or CAPTION_FILL,
                outline=INK, width=5)
    for i, l in enumerate(lines):
        d.text((x + pad, y + pad + i * lh), l, font=f, fill=INK)

def sfx_tile(sfx, slot):
    px = int(base_px(slot) * sfx.get('size', 0.2))
    f = font(px)
    while f.getlength(sfx['text']) > slot[2] * 0.8 and px > 30:
        px -= 4; f = font(px)
    sw = max(4, px // 14)
    tw = int(f.getlength(sfx['text'])) + 4 * sw + 8
    th = int(px * 1.25) + 4 * sw
    tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    # outer white keyline, then black ink stroke, then colour fill
    d.text((2 * sw + 4, 2 * sw), sfx['text'], font=f, fill=(255, 255, 255, 255), stroke_width=2 * sw, stroke_fill=(255, 255, 255, 255))
    d.text((2 * sw + 4, 2 * sw), sfx['text'], font=f, fill=tuple(sfx.get('color', [255, 214, 0])) + (255,),
           stroke_width=sw, stroke_fill=INK + (255,))
    tile = tile.rotate(sfx.get('rot', -6), resample=Image.BICUBIC, expand=True)
    bb = tile.getbbox()
    return tile.crop(bb)

def sfx_rect(sfx, slot, scale=1.0):
    tile = sfx_tile(sfx, slot)
    w, h = int(tile.width * scale), int(tile.height * scale)
    cx = slot[0] + sfx['pos'][0] * slot[2]
    cy = slot[1] + sfx['pos'][1] * slot[3]
    m = 18  # keep the SFX inside its panel (layouts differ per orientation)
    cx = min(max(cx, slot[0] + m + w / 2), slot[0] + slot[2] - m - w / 2)
    cy = min(max(cy, slot[1] + m + h / 2), slot[1] + slot[3] - m - h / 2)
    return (int(cx - w / 2), int(cy - h / 2), w, h), tile

# ---------------------------------------------------------------- scene model
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3

def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def text_items(spec, orient):
    """Every caption / SFX with its page rect and visible interval (scene seconds). Used by QA."""
    L = layout(orient)
    items = []
    tr = spec.get('transition')
    end = scene_len(spec)
    page_end = T(spec, tr['at']) - tr.get('dur', 0.4) if tr else end
    splash_t0 = T(spec, tr['at']) if tr else end
    for p in spec['panels']:
        slot = L[p['slot']]
        for c in p.get('captions', []):
            items.append({'who': f"{p['id']} caption '{c['text']}'", 'rect': caption_box(c, slot)[0],
                          'from': T(spec, c.get('at', p['at'])), 'to': page_end, 'slot': slot})
        for s in p.get('sfx', []):
            items.append({'who': f"{p['id']} sfx '{s['text']}'", 'rect': sfx_rect(s, slot)[0],
                          'from': T(spec, s['at']), 'to': page_end, 'slot': slot})
    sp = splash_unit(spec) or {}
    slot = L['splash']
    for c in sp.get('captions', []):
        items.append({'who': f"{sp['id']} caption '{c['text']}'", 'rect': caption_box(c, slot)[0],
                      'from': max(splash_t0, T(spec, c.get('at', tr['at']))), 'to': end, 'slot': slot})
    for s in sp.get('sfx', []):
        items.append({'who': f"{sp['id']} sfx '{s['text']}'", 'rect': sfx_rect(s, slot)[0],
                      'from': T(spec, s['at']), 'to': end, 'slot': slot})
    return items


class Scene:
    """Builds frames for one orientation."""
    def __init__(self, spec, orient, fps=None):
        self.spec, self.orient = spec, orient
        self.W, self.H = SIZES[orient]
        self.fps = fps or spec.get('fps', 30)
        self.L = layout(orient)
        self.paper = Image.fromarray(paper(self.W, self.H))
        self.units = [dict(p, slotrect=self.L[p['slot']]) for p in spec['panels']]
        sp = splash_unit(spec)
        self.splash = sp and dict(sp, slotrect=self.L['splash'])
        for u in self.all_units():
            self._prep(u)
        self._page_cache = {}

    def all_units(self):
        return self.units + ([self.splash] if self.splash else [])

    def _prep(self, u):
        img = Image.open(resolve(self.spec, u['image'])).convert('RGB')
        x, y, w, h = u['slotrect']
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
        crop = cover_crop(img.width, img.height, w, h, tuple(u.get('focus', (0.5, 0.5))), within)
        u['crop'] = crop
        u['static'] = comic_finish(upscale(img, crop, (w, h), sharpen=False))
        if u.get('clip'):
            rx, ry, rw, rh = u['reg']
            fw, fh = frames[0].size
            cbox = ((crop[0] - rx) * fw / rw, (crop[1] - ry) * fh / rh, crop[2] * fw / rw, crop[3] * fh / rh)
            u['clipbox'] = cbox
            u['frames'] = [comic_finish(upscale(f, cbox, (w, h))) for f in frames]

    def art(self, u, t):
        """Panel art at scene time t: static hold -> clip (3-frame crossfade in) -> freeze on last frame."""
        if not u.get('clip'):
            return u['static']
        t0 = T(self.spec, clip_start(self.spec, u))
        if t < t0:
            return u['static']
        i = min(int((t - t0) * self.fps), len(u['frames']) - 1)
        fr = u['frames'][i]
        xf = 3 / self.fps
        if t - t0 < xf:
            return Image.blend(u['static'], fr, (t - t0) / xf)
        return fr

    def _ink(self, img, r, w=7):
        x, y, ww, hh = r
        ImageDraw.Draw(img).rectangle([x - w + 1, y - w + 1, x + ww + w - 2, y + hh + w - 2], outline=INK, width=w)

    def _letter(self, img, u, t):
        slot = u['slotrect']
        for c in u.get('captions', []):
            if t >= T(self.spec, c.get('at', u['at'])):
                draw_caption(img, c, slot)
        for s in u.get('sfx', []):
            ts = T(self.spec, s['at'])
            if t >= ts:
                k = min((t - ts) * self.fps / 3, 1.0)
                scale = 1.25 - 0.25 * ease(k)          # quick 3-frame stamp, then still
                rect, tile = sfx_rect(s, slot, scale)
                if scale != 1.0:
                    tile = tile.resize((rect[2], rect[3]), Image.BICUBIC)
                img.paste(tile, rect[:2], tile)

    def page(self, t):
        img = self.paper.copy()
        for u in self.units:
            ta = T(self.spec, u['at'])
            if t < ta:
                continue
            k = ease((t - ta) / 0.14)
            x, y, w, h = u['slotrect']
            dy = int(round((1 - k) * 16))
            art = self.art(u, t)
            if k < 1:
                bg = img.crop((x - 8, y + dy - 8, x + w + 8, y + dy + h + 8))
                fr = bg.copy(); fr.paste(art, (8, 8)); self._ink(fr, (8, 8, w, h))
                img.paste(Image.blend(bg, fr, k), (x - 8, y + dy - 8))
            else:
                img.paste(art, (x, y)); self._ink(img, (x, y, w, h))
        for u in self.units:
            if t >= T(self.spec, u['at']):
                self._letter(img, u, t)
        return img

    def splash_frame(self, t):
        img = self.paper.copy()
        u = self.splash
        x, y, w, h = u['slotrect']
        img.paste(self.art(u, t), (x, y)); self._ink(img, (x, y, w, h), 9)
        self._letter(img, u, t)
        return img

    def frame(self, t):
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
            self._page_cache[key] = self.page(t_land - dur)
        src = self._page_cache[key]
        target = next(u for u in self.units if u['id'] == tr['panel'])['slotrect']
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

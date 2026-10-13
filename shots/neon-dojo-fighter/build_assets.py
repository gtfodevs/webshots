#!/usr/bin/env python3
"""Neon Dojo fighter: build stage/assets/px/ (placeholder pass: only the 1-bit 8px pixel font).
python3 shots/neon-dojo-fighter/build_assets.py   (run from the repo root)
Font: Press Start 2P (OFL) from channels/progressiveslop/assets/kingdom-come-16bit/fonts/. Media is not committed (ASSETS.md)."""
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage', 'assets', 'px'); os.makedirs(OUT, exist_ok=True)
fnt = ImageFont.truetype(os.path.join(ROOT, 'channels/progressiveslop/assets/kingdom-come-16bit/fonts/PressStart2P-Regular.ttf'), 8)
gl = Image.new('L', (8 * 95, 8), 0); gd = ImageDraw.Draw(gl); gd.fontmode = '1'
for i, c in enumerate(range(32, 127)): gd.text((i * 8, 0), chr(c), font=fnt, fill=255)
g = np.asarray(gl) > 127
Image.fromarray(np.dstack([np.full(g.shape + (3,), 255, np.uint8), (g * 255).astype(np.uint8)]), 'RGBA').save(os.path.join(OUT, 'font8.png'))
print('font ok ->', OUT)

# ---------- stage art -> parallax layers at 960x540 (shared builder, used by EVERY stage) ----------
# RULE (Jason): every animated background figure (crowd, monks, spectators...) is cut out INDIVIDUALLY and the
# stage is rebuilt on an INPAINTED CLEAN PLATE, so a figure that bobs never drags or duplicates scenery.
# Bands that bob are not allowed. fighter_qa.mjs checks every stage json for this automatically.
from scipy import ndimage
SD = os.path.join(ROOT, 'channels/progressiveslop/assets/neon-dojo-fighter/source/stages')

def inpaint(im, mask, iters=400):
    """Clean plate: fill masked pixels by normalized diffusion from the surrounding scenery (no OpenCV needed)."""
    out = im.astype(np.float32).copy(); known = (~mask).astype(np.float32)
    acc = out * known[..., None]; w = known.copy(); k = np.ones((5, 5), np.float32)
    fill = mask.copy()
    for _ in range(iters):
        if not fill.any(): break
        num = np.stack([ndimage.convolve(acc[..., c], k, mode='nearest') for c in range(3)], -1); den = ndimage.convolve(w, k, mode='nearest')
        ok = fill & (den > 0.5)
        out[ok] = num[ok] / den[ok, None]; acc[ok] = out[ok]; w[ok] = 1; fill &= ~ok
    return np.clip(out, 0, 255).astype(np.uint8)

def find_figures(im, box, keep=(), min_area=250, min_h=24, lum=70):
    """Silver robot figures (low saturation, bright) inside box -> one mask per figure; wide merged blobs are split."""
    x0, y0, x1, y1 = box; sub = im[y0:y1, x0:x1].astype(int); mx, mn = sub.max(2), sub.min(2)
    m = (mx > lum) & (mx - mn < 60)
    m = ndimage.binary_closing(m, iterations=2); m = ndimage.binary_fill_holes(m); m = ndimage.binary_opening(m, iterations=1)
    lab, n = ndimage.label(m); objs = ndimage.find_objects(lab); comps = []
    for i, sl in enumerate(objs):
        cm = lab[sl] == i + 1; h, w = cm.shape
        if cm.sum() < min_area or h < min_h: continue
        cx, cy = x0 + (sl[1].start + sl[1].stop) / 2, y0 + (sl[0].start + sl[0].stop) / 2
        if any(k[0] <= cx <= k[2] and k[1] <= cy <= k[3] for k in keep): continue   # declared static scenery
        px = sub[sl][cm]
        if px[:, 0].mean() > px[:, 2].mean() - 2: continue   # warm stone statues (lions) are static scenery, not figures
        comps.append((sl, cm))
    if not comps: return []
    med = float(np.median([c[1].shape[1] for c in comps if c[1].shape[1] < 90] or [40]))
    figs = []
    for sl, cm in comps:
        h, w = cm.shape; n_ = max(1, int(round(w / med)))
        for j in range(n_):
            cs = cm[:, j * w // n_:(j + 1) * w // n_]
            if cs.sum() < min_area * 0.6: continue
            ys, xs = np.where(cs); fx0 = sl[1].start + j * w // n_ + x0; fy0 = sl[0].start + y0
            fm = np.zeros(im.shape[:2], bool); fm[fy0 + ys, fx0 + xs] = True
            # extend down through the railing gaps: the figure's dimmer lower body is part of the same cutout
            lx0, lx1 = fx0 + xs.min(), fx0 + xs.max() + 1; ly = fy0 + ys.max()
            seg = im[ly:y1, lx0:lx1].astype(int)
            fm[ly:y1, lx0:lx1] |= (seg.max(2) > 35) & (seg.max(2) - seg.min(2) < 45) & (seg[..., 0] <= seg[..., 2] + 6)
            figs.append(ndimage.binary_dilation(fm, iterations=3))
    return figs

def rembg_figures(im, rects, y0, y1):
    """Dark figures on a dark set (colour keys fail): one matte per declared figure rect via rembg isnet, hardened."""
    from rembg import remove, new_session
    ses = new_session('isnet-general-use'); figs = []
    for x0, x1 in rects:
        c = Image.fromarray(im[y0:y1, x0:x1]); m = remove(c.resize((c.width * 4, c.height * 4), Image.LANCZOS), session=ses, only_mask=True)
        m = np.asarray(m.resize(c.size, Image.BILINEAR)) > 12
        m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=3)); lb, n = ndimage.label(m)
        if n: m = lb == 1 + int(np.argmax(ndimage.sum(m, lb, range(1, n + 1))))
        for yy in range(m.shape[0]):   # standing armour is solid: fill each row between its outer edges
            xs_ = np.where(m[yy])[0]
            if len(xs_) and xs_.max() - xs_.min() < m.shape[1] * 0.8: m[yy, xs_.min():xs_.max() + 1] = True
        f = np.zeros(im.shape[:2], bool); f[y0:y1, x0:x1] = ndimage.binary_dilation(m, iterations=2); figs.append(f)
    return figs

def build_stage(key, srcname, cfg):
    src = os.path.join(SD, srcname)
    if not os.path.exists(src): return
    im = np.asarray(Image.open(src).convert('RGB').resize((960, 540), Image.LANCZOS))
    Y, X = np.mgrid[0:540, 0:960]
    figs = [f for box in cfg.get('figure_boxes', []) for f in find_figures(im, box, cfg.get('static', []), lum=cfg.get('figure_lum', 70))]
    if cfg.get('figure_rects'): figs += rembg_figures(im, *cfg['figure_rects'])
    for k in cfg.get('static', []):   # static scenery is never part of a figure cutout
        for f in figs: f[k[1]:k[3], k[0]:k[2]] = False
    allf = np.zeros(im.shape[:2], bool)
    for f in figs: f &= ~allf; allf |= f   # exclusive masks: each pixel belongs to exactly one figure
    plate = inpaint(im, ndimage.binary_dilation(allf, iterations=1)) if figs else im
    def save(arr_rgb, mask, name):
        out = np.zeros((540, 960, 4), np.uint8); out[..., :3] = arr_rgb; out[..., 3] = mask * 255
        Image.fromarray(out).save(os.path.join(OUT, f'stage-{key}-{name}.png'))
    layers = []
    for name, sp, mask in cfg['layers'](X, Y):
        if mask is None: Image.fromarray(plate).save(os.path.join(OUT, f'stage-{key}-{name}.png'))
        else: save(im, mask & ~allf, name) if name in cfg.get('occluders', []) else save(plate, mask, name)   # occluders keep the original art
        layers.append([name, sp])
    meta_f = []
    for i, f in enumerate(figs):   # each figure: its own crop of the ORIGINAL art + rect, drawn over the clean plate
        ys, xs = np.where(f); fx0, fy0, fx1, fy1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        out = np.zeros((fy1 - fy0, fx1 - fx0, 4), np.uint8); out[..., :3] = im[fy0:fy1, fx0:fx1]; out[..., 3] = f[fy0:fy1, fx0:fx1] * 255
        Image.fromarray(out).save(os.path.join(OUT, f'stage-{key}-fig{i}.png'))
        meta_f.append([int(fx0), int(fy0), int(fx1 - fx0), int(fy1 - fy0), i % 2])
    glows = []   # additive glow layers (original pixels under a mask): crest pulse, torch flicker, window lightning flash
    for name, fn, mode in cfg.get('glows', []):
        gm = fn(im, X, Y) & ~allf; out = np.zeros((540, 960, 4), np.uint8); out[..., :3] = im; out[..., 3] = gm * 255
        Image.fromarray(out).save(os.path.join(OUT, f'stage-{key}-glow-{name}.png')); glows.append([name, mode])
    meta = dict(cfg['meta'], layers=layers, glows=glows, figure_mode=cfg.get('figure_mode', 'bob'), plate=True, figures=meta_f, figure_layer=cfg['figure_layer'], figure_speed=cfg['figure_speed'],
                occluders=cfg.get('occluders', []))
    json.dump(meta, open(os.path.join(OUT, f'stage-{key}.json'), 'w'), indent=1)
    print(f'stage {key} ok: {len(figs)} figures cut out over an inpainted plate')

def rooftop_layers(X, Y):
    gate = ((X >= 286) & (X <= 690) & (Y >= 95) & (Y < 300) & ~((X > 410) & (X < 560) & (Y > 222))) | (((X < 84) | (X > 876)) & (Y >= 30) & (Y < 300)) | ((Y >= 222) & (Y < 300) & ((X < 140) | (X > 820) | ((X > 280) & (X < 345)) | ((X > 630) & (X < 690))))
    return [('sky', 0.1, None), ('skyline', 0.3, (Y >= 120) & (Y < 300) & ~gate), ('gate', 0.6, gate | ((Y >= 300) & (Y < 422))),
            ('rail', 0.6, (Y >= 368) & (Y < 422)), ('floor', 1.0, Y >= 422)]
build_stage('rooftop', 'rooftop_dojo.jpg', dict(layers=rooftop_layers, figure_boxes=[[20, 296, 940, 420]], figure_layer='gate', figure_speed=0.6,
            occluders=['rail'], static=[[246, 300, 302, 420], [660, 300, 708, 420]],   # stone lions don't move   # drawn after the figures: the railing stays in front of the crowd
            meta={'ground': 476, 'floor_top': 422, 'lanterns': [[33, 258, 16], [77, 284, 12], [117, 289, 11], [315, 254, 17], [657, 254, 17], [843, 288, 11], [882, 284, 12], [927, 258, 16]]}))

def temple_layers(X, Y):
    mid = (Y >= 225) & (Y < 425)
    trees = ((Y < 262) & ((X < 240) | (X > 640))) | ((Y >= 120) & (Y < 262)) | ((X > 330) & (X < 680) & (Y >= 40) & (Y < 262))
    return [('sky', 0.1, None), ('trees', 0.3, trees & ~mid), ('mid', 0.6, mid), ('floor', 1.0, Y >= 425)]
build_stage('temple', 'lotus_temple.jpg', dict(layers=temple_layers, figure_boxes=[[312, 236, 642, 314]], figure_layer='mid', figure_speed=0.6,
            meta={'ground': 476, 'floor_top': 425, 'shimmer': [0, 330, 960, 92, 0.6], 'petals': 22,
                  'lanterns': [[127, 235, 10], [281, 231, 8], [504, 204, 9], [775, 244, 10], [856, 244, 10]]}))

def palace_layers(X, Y):
    floor = Y >= 392
    pillars = ((X < 200) | ((X > 760))) & ~floor
    hall = ((X >= 370) & (X <= 650) & (Y >= 40)) & ~floor   # crest + throne + dais
    return [('sky', 0.1, None), ('pillars_back', 0.3, ((Y < 392) & (Y >= 0) & ((X < 260) | (X > 700)) & ~pillars) | ((Y < 60) & ~pillars)),
            ('hall', 0.6, hall | ((Y >= 300) & ~floor)), ('pillars', 0.6, pillars), ('floor', 1.0, floor)]
def _red(im): r, g, b = [im[..., i].astype(int) for i in range(3)]; return r, g, b
def crest_glow(im, X, Y):
    r, g, b = _red(im); return ((X - 516) ** 2 + (Y - 178) ** 2 < 92 ** 2) & (r > 150) & (r - g > 70)
def torch_glow(im, X, Y):
    r, g, b = _red(im); m = np.zeros(X.shape, bool)
    for x, y in [(53, 281), (209, 281), (750, 281), (902, 281)]: m |= (abs(X - x) < 26) & (Y > y - 40) & (Y < y + 12)
    return m & (r > 140) & (r - b > 50)
def window_flash(im, X, Y):   # lightning bolts + violet storm sky in the arched windows
    r, g, b = _red(im); win = (Y < 340) & (Y > 80) & ~((X > 380) & (X < 640))
    return win & (((b > g + 12) & (b > 45)) | ((r > 150) & (b > 90) & (g < 140)))
build_stage('palace', 'shogun_palace.jpg', dict(layers=palace_layers, figure_rects=([(222, 296), (304, 380), (576, 650), (669, 744)], 255, 398),
            figure_layer='hall', figure_speed=0.6, figure_mode='breathe', figure_lum=38,
            glows=[('crest', crest_glow, 'pulse'), ('torch', torch_glow, 'flicker'), ('win', window_flash, 'flash')],
            meta={'ground': 476, 'floor_top': 392, 'lanterns': [[53, 270, 14], [209, 270, 14], [750, 270, 14], [902, 270, 14]]}))

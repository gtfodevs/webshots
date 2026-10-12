"""v4 frame-by-frame walk: per-pose AI frames -> ONE master upper body + per-pose lower body/limbs,
shared palette, bob table, fixed ground row, pinned planted foot.  (see docs/MUSIC_MODE.md 'THE sprite method')"""
import os, sys, json, math
import numpy as np
from PIL import Image
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from pixel_sprites import quantize, outline, despeckle, build_palette

def key(rgb):
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    bgk = (g - np.maximum(r, b) > 50) & (g > 110)
    m = ~bgk
    m = ndimage.binary_opening(m, iterations=1)
    lab, n = ndimage.label(m); sz = ndimage.sum(m, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(sz > sz.max() * 0.02)[0])
    keep = ndimage.binary_fill_holes(keep) & ~bgk | keep
    keep = ndimage.binary_erosion(keep, iterations=1)      # drop the green fringe ring
    out = rgb.copy().astype(int)
    spill = keep & (g > np.maximum(r, b))                  # despill: green never exceeds max(r, b)
    out[..., 1] = np.where(spill, np.maximum(r, b), g)
    return np.dstack([np.clip(out, 0, 255), keep * 255]).astype(np.uint8)

def gold(a):
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    return (a[..., 3] > 0) & (r > 140) & (g > 90) & (b < 90) & (r - b > 80)

def landmarks(a):
    """top / bottom / belt row / head-centre x. Belt = the widest gold row in the torso column band."""
    m = a[..., 3] > 0; ys, xs = np.where(m); top, bot = ys.min(), ys.max(); H = bot - top
    head = m[top: top + int(H * 0.10)]; hx = np.where(head.any(0))[0].mean()
    gm = gold(a).copy(); X = np.arange(a.shape[1]); gm[:, (X < hx - 40) | (X > hx + 60)] = False
    y0 = top + int(H * 0.36); band = gm[y0: top + int(H * 0.47)]
    rows = band.sum(1); belt = y0 + int(np.argmax(rows))
    return dict(top=int(top), bot=int(bot), belt=int(belt), hx=float(hx))

SRC = os.path.join(ROOT, 'channels/progressiveslop/assets/kingdom-come-16bit/source/uno-walk-v4')
FINAL_H = 72

def load_frames(src=SRC, n=8):
    ks = [key(np.array(Image.open(f'{src}/f{i}.jpg').convert('RGB'))) for i in range(n)]
    Ls = [landmarks(a) for a in ks]
    f = FINAL_H / float(np.median([L['bot'] - L['top'] for L in Ls]))
    return ks, Ls, f

def to_final(a, L, f, hx_ref, W=64, H=80, ground=None):
    """shift so the head x sits at hx_ref (source px), scale to final with BOX, keep RGBA."""
    im = Image.fromarray(a); w, h = im.size
    im = im.resize((round(w * f), round(h * f)), Image.BOX)
    b = np.array(im); al = b[..., 3:4].astype(float) / 255
    rgb = np.where(al > 0, b[..., :3] / np.maximum(al, 1e-6), 0)
    b = np.dstack([np.clip(rgb, 0, 255), (al[..., 0] >= 0.5) * 255]).astype(np.uint8)
    return b, {k: (v * f if k != 'hx' else v * f) for k, v in L.items()}

def scale_final(a, f):
    im = Image.fromarray(a); w, h = im.size
    b = np.array(im.resize((round(w * f), round(h * f)), Image.BOX)); al = b[..., 3:4].astype(float) / 255
    rgb = np.where(al > 0, b[..., :3] / np.maximum(al, 1e-6), 0)
    return np.dstack([np.clip(rgb, 0, 255), (al[..., 0] >= 0.5) * 255]).astype(np.uint8)

def poly_mask(shape, pts):
    from PIL import ImageDraw
    m = Image.new('L', (shape[1], shape[0]), 0); ImageDraw.Draw(m).polygon(pts, fill=255); return np.array(m) > 0

def blit(dst, src, dx, dy, mask=None):
    h, w = src.shape[:2]; m = src[..., 3] > 0 if mask is None else (mask & (src[..., 3] > 0))
    for y in range(h):
        Y = y + dy
        if not 0 <= Y < dst.shape[0]: continue
        xs = np.where(m[y])[0]; X = xs + dx; ok = (X >= 0) & (X < dst.shape[1])
        dst[Y, X[ok]] = src[y, xs[ok]]

# core polygon (head, headphones, torso, pendant, belt, shoulder cape), relative to (head x, belt row)
CORE = [(-5.4, -32.1), (7.6, -32.1), (7.6, -18), (8.6, -6), (6.6, 2.4), (-7.4, 2.4), (-8.4, -6), (-14.4, -10), (-15.4, -20), (-7.4, -23)]
BOB = [1, 2, -1, 0, 1, 2, -1, 0]          # + = down (final px): low on contact/down, high on passing (triangle)
HOLDS = [140, 100, 100, 100, 140, 100, 100, 100]   # ms per frame: contacts held longer

def build_walk(W=76, H=84, HX=36, G=81, master=0, cut_off=2, bob=BOB):
    ks, Ls, f = load_frames()
    fin = []
    for a, L in zip(ks, Ls):
        b = scale_final(a, f); fin.append((b, {k: v * f for k, v in L.items()}))
    mb, mL = fin[master]
    mcut = int(round(mL['belt'])) + cut_off
    core = poly_mask(mb.shape, [(mL['hx'] + x, mL['belt'] + y) for x, y in CORE]); core[mcut:] = False
    legs_med = float(np.median([L['bot'] - L['belt'] for _, L in fin]))
    out, log = [], []
    for i, (b, L) in enumerate(fin):
        cnv = np.zeros((H, W, 4), np.uint8)
        cut = int(round(L['belt'])) + cut_off
        dx = int(round(HX - L['hx']))
        # lower body (hips/belt down: legs, feet, sword blade, cloak hem): grounded on row G
        lower = b.copy(); lower[:cut] = 0
        dyl = int(G - round(L['bot']))
        # master torso target: belt row = G - legs_med + bob
        mbelt = int(round(G - legs_med)) + bob[i]
        top_lower = cut + dyl                                  # first lower row on the canvas
        gap = top_lower - (mbelt + cut_off)                    # >0: hips sit too low -> stretch the hip rows up
        if gap > 0:
            hip = lower[cut:cut + 1].copy()
            for k in range(gap): lower[cut - 1 - k] = hip[0]
        # arms + sword hilt + cloak above the cut: from THIS pose, riding with the master torso
        upper = b.copy(); upper[cut:] = 0
        dyu = mbelt - int(round(L['belt']))
        # the pose's own torso inside the core region is replaced by the master
        pcore = poly_mask(b.shape, [(L['hx'] + x, L['belt'] + y) for x, y in CORE])
        upper[pcore] = 0
        blit(cnv, lower, dx, dyl)
        blit(cnv, upper, dx, dyu)
        mdx = int(round(HX - mL['hx'])); mdy = mbelt - int(round(mL['belt']))
        blit(cnv, mb, mdx, mdy, core)
        out.append(cnv); log.append({'bob': bob[i], 'gap': gap, 'core_dx': mdx, 'core_dy': mdy})
    return out, log, (core, mb, int(round(HX - mL['hx'])), int(round(mL['belt'])))

def finish(frames, pal):
    return [outline(despeckle(quantize(f, pal), 3)) for f in frames]

def save_gif(frames, path, durations, scale=4, bg=(40, 24, 70), ground=None):
    ims = []
    for f in frames:
        c = np.zeros(f.shape[:2] + (3,), np.uint8); c[...] = bg
        if ground is not None: c[ground + 1:, :] = (24, 14, 44); c[ground + 1, :] = (255, 63, 210)
        m = f[..., 3] > 0; c[m] = f[..., :3][m]
        ims.append(Image.fromarray(c).resize((c.shape[1] * scale, c.shape[0] * scale), Image.NEAREST))
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=durations, loop=0, disposal=2)

def onion_rgb(frames, scale=6):
    h, w = frames[0].shape[:2]; out = np.full((h, w, 3), 20.0)
    tints = [(255, 80, 80), (255, 200, 60), (80, 255, 120), (80, 160, 255), (220, 90, 255), (255, 255, 255), (60, 230, 230), (255, 120, 200)]
    for i, f in enumerate(frames):
        m = f[..., 3] > 0; out[m] = out[m] * 0.55 + np.array(tints[i]) * 0.45 * (0.35 + 0.65 * f[..., :3][m].mean(1, keepdims=True) / 255)
    return Image.fromarray(out.astype(np.uint8)).resize((w * scale, h * scale), Image.NEAREST)

# timing + scroll tables (per step of 4 frames). Contacts held longer; the world scrolls by the measured
# planted-foot travel of each frame so the stance foot stays pinned (halves averaged so both legs share it).
STEP_FRAC = [0.31, 0.23, 0.23, 0.23]
def foot_travel(frames, g_rows=(78, 82)):
    """planted-foot x per frame (the foot on the ground that is moving back), measured from the art."""
    xs = []
    for f in frames:
        band = (f[g_rows[0]:g_rows[1], :, 3] > 0).any(0); lab, n = ndimage.label(band)
        xs.append([float(np.where(lab == k)[0].mean()) for k in range(1, n + 1)])
    return xs

def idle_frames(master=0, base=2, W=76, H=84, HX=36, G=81):
    """breathing idle: lower body + arms from the standing-ish passing frame, master torso;
    chest/shoulders rise 1 px with the head lagging a frame, cloak hem sways 1 px."""
    ks, Ls, f = load_frames()
    mb = scale_final(ks[master], f); mL = {k: v * f for k, v in Ls[master].items()}
    b = scale_final(ks[base], f); L = {k: v * f for k, v in Ls[base].items()}
    cut = int(round(L['belt'])) + 2; mcut = int(round(mL['belt'])) + 2
    core = poly_mask(mb.shape, [(mL['hx'] + x, mL['belt'] + y) for x, y in CORE]); core[mcut:] = False
    neck = int(round(mL['belt'] - 20))                       # rows above this = head block
    head = core.copy(); head[neck:] = False; chest = core.copy(); chest[:neck] = False
    dx = int(round(HX - L['hx'])); dyl = int(G - round(L['bot']))
    lower = b.copy(); lower[:cut] = 0
    upper = b.copy(); upper[cut:] = 0; upper[poly_mask(b.shape, [(L['hx'] + x, L['belt'] + y) for x, y in CORE])] = 0
    mbelt = cut - 2 + dyl
    mdx = int(round(HX - mL['hx'])); mdy = mbelt - int(round(mL['belt']))
    h, s_, v = None, None, None
    pur = lambda a: (a[..., 2].astype(int) > a[..., 1].astype(int) + 40) & (a[..., 0].astype(int) > a[..., 1].astype(int) + 20)
    out = []
    for chest_dy, head_dy, sway in ((0, 0, 0), (-1, 0, 0), (-1, -1, 1), (0, -1, 1)):
        cnv = np.zeros((H, W, 4), np.uint8)
        lw = lower.copy()
        if sway:   # cloak hem: shift the purple pixels of the lower layer 1 px back
            pm = pur(lw); pm[:cut + 12] = False; tmp = np.zeros_like(lw); tmp[:, :-1][pm[:, 1:]] = lw[:, 1:][pm[:, 1:]]
            lw[pm] = 0; m2 = tmp[..., 3] > 0; lw[m2] = tmp[m2]
        blit(cnv, lw, dx, dyl)
        blit(cnv, upper, dx, dyl + chest_dy)
        blit(cnv, mb, mdx, mdy + chest_dy, chest)
        blit(cnv, mb, mdx, mdy + head_dy, head)
        out.append(cnv)
    return out, [300, 180, 340, 180]

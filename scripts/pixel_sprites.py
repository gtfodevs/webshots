"""Pixel-game helpers for music mode (the "pixel game" style).

Turns a design-reference sprite sheet on a flat chroma background into true low-res sprites:
chroma key -> crop per frame -> box downscale -> alpha threshold -> shared limited palette ->
1 px dark outline. Also: pixel edits for extra loop frames, an atlas packer, and background
downscale/quantize/band split for parallax.

Library, used by shots/<name>/build_assets.py. Everything here is integer-pixel; nothing blurs.
"""
import json
import numpy as np
from PIL import Image

OUTLINE = (18, 6, 36, 255)


def key_frames(path, rows, thresh=120, erode=2):
    """rows: [(y0, y1, [x cuts...])]. Returns a list (per row) of RGBA crops keyed against the corner colour."""
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(int)
    key = a[4, 4]
    alpha = (np.abs(a - key).sum(2) > thresh)
    # erode the matte (removes the chroma fringe that would otherwise become magenta edge pixels)
    for _ in range(erode):
        e = alpha.copy(); e[1:] &= alpha[:-1]; e[:-1] &= alpha[1:]; e[:, 1:] &= alpha[:, :-1]; e[:, :-1] &= alpha[:, 1:]; alpha = e
    # despill: pull magenta fringe toward neutral
    rgba = np.dstack([a, alpha * 255]).astype(np.uint8)
    out = []
    for y0, y1, cuts in rows:
        row = []
        for x0, x1 in zip(cuts[:-1], cuts[1:]):
            c = rgba[y0:y1, x0:x1].copy()
            ys, xs = np.where(c[..., 3] > 0)
            # drop tiny specks (jpeg noise): keep columns/rows with real content
            c = c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            row.append(c)
        out.append(row)
    return out


def downscale(rgba, scale):
    """Premultiplied box downscale, hard alpha (>=50%), returns uint8 RGBA."""
    h, w = rgba.shape[:2]
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    f = rgba.astype(float) / 255
    pm = np.dstack([f[..., :3] * f[..., 3:4], f[..., 3:4]])
    im = Image.fromarray((pm * 255).astype(np.uint8), 'RGBA')
    sm = np.asarray(im.resize((nw, nh), Image.BOX)).astype(float) / 255
    al = sm[..., 3:4]
    rgb = np.where(al > 0, sm[..., :3] / np.maximum(al, 1e-6), 0)
    a = (al[..., 0] >= 0.5)
    return np.dstack([np.clip(rgb * 255, 0, 255), a * 255]).astype(np.uint8)


def build_palette(frames, n=28, fixed=()):
    """Median-cut palette over all opaque pixels of all frames (+ fixed colours kept exact)."""
    px = np.concatenate([f[f[..., 3] > 0][:, :3] for f in frames])
    im = Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8), 'RGB')
    q = im.quantize(colors=n - len(fixed), method=Image.MEDIANCUT)
    pal = np.array(q.getpalette()[: 3 * (n - len(fixed))]).reshape(-1, 3)
    if fixed:
        pal = np.concatenate([pal, np.array(fixed)])
    return pal


def quantize(rgba, pal):
    rgb = rgba[..., :3].astype(int)
    d = ((rgb[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
    q = pal[d.argmin(-1)]
    return np.dstack([q, rgba[..., 3]]).astype(np.uint8)


def despeckle(rgba, min_px=10):
    """Drop tiny opaque islands (bits of neighbouring reference frames, jpeg specks)."""
    from scipy.ndimage import label
    lab, n = label(rgba[..., 3] > 0, structure=np.ones((3, 3)))
    out = rgba.copy()
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < min_px: out[m] = 0
    return out


def outline(rgba, color=OUTLINE):
    """1 px outer outline (4-neighbour) around opaque pixels. Pads by 1 px."""
    p = np.pad(rgba, ((1, 1), (1, 1), (0, 0)))
    a = p[..., 3] > 0
    n = np.zeros_like(a)
    n[1:] |= a[:-1]; n[:-1] |= a[1:]; n[:, 1:] |= a[:, :-1]; n[:, :-1] |= a[:, 1:]
    edge = n & ~a
    p[edge] = color
    return p


def flip(rgba):
    return rgba[:, ::-1].copy()


def shift_rows(rgba, y0, y1, dx=0, dy=0):
    """Move the opaque pixels of rows [y0,y1) by (dx,dy) (pixel edit for bob/sway/limb loops)."""
    out = rgba.copy()
    band = rgba[y0:y1].copy()
    out[y0:y1] = 0
    h, w = rgba.shape[:2]
    for yy in range(band.shape[0]):
        ty = y0 + yy + dy
        if 0 <= ty < h:
            src = band[yy]
            row = np.zeros_like(src)
            if dx >= 0: row[dx:] = src[:w - dx]
            else: row[:dx] = src[-dx:]
            m = row[..., 3] > 0
            out[ty][m] = row[m]
    return out


def shift_region(rgba, box, dx=0, dy=0):
    """Move the opaque pixels inside box=(x0,y0,x1,y1) by (dx,dy); the vacated area is cleared first."""
    x0, y0, x1, y1 = box
    out = rgba.copy()
    reg = rgba[y0:y1, x0:x1].copy()
    out[y0:y1, x0:x1][reg[..., 3] > 0] = 0
    h, w = rgba.shape[:2]
    ys, xs = np.where(reg[..., 3] > 0)
    ty, tx = ys + y0 + dy, xs + x0 + dx
    ok = (ty >= 0) & (ty < h) & (tx >= 0) & (tx < w)
    out[ty[ok], tx[ok]] = reg[ys[ok], xs[ok]]
    return out


def pad_to(rgba, w, h):
    """Bottom-centre a sprite on a w x h canvas (feet anchor)."""
    out = np.zeros((h, w, 4), np.uint8)
    sh, sw = rgba.shape[:2]
    x = (w - sw) // 2
    y = h - sh
    xs0, ys0 = max(0, -x), max(0, -y)
    out[max(0, y):max(0, y) + sh - ys0, max(0, x):max(0, x) + sw - xs0] = rgba[ys0:, xs0:][: h, : w]
    return out


def feet_of(f):
    """(feet centre x, lowest opaque row) of a frame: the anchor for grounded sprites."""
    ys, xs = np.where(f[..., 3] > 0)
    yb = ys.max(); sel = ys >= yb - 2
    return float(xs[sel].mean()), int(yb)


def pack(anims, path_png, path_json, gap=1):
    """anims: {name: {"fps": n, "frames": [rgba...], ...}} -> atlas png + json.
    Frames of one animation share a canvas; every frame is aligned by its FEET (centre of the lowest
    opaque rows) at x = w/2 and its lowest opaque pixel on the canvas bottom row, unless the anim sets
    "air": True (flyers/jump arcs keep their own vertical placement, aligned by the frame bottom)."""
    rows, W, H = [], 0, 0
    for name, a in anims.items():
        fr = a['frames']; air = a.get('air', False)
        info = [feet_of(f) for f in fr]
        lefts = [fx for fx, _ in info]; rights = [f.shape[1] - fx for f, (fx, _) in zip(fr, info)]
        half = int(np.ceil(max(max(lefts), max(rights)))) + 1
        if air: hgt = max(f.shape[0] for f in fr)
        else: hgt = max(yb + 1 for _, yb in info)
        placed = []
        for f, (fx, yb) in zip(fr, info):
            c = np.zeros((hgt, 2 * half, 4), np.uint8)
            x = int(round(half - fx)); y = (hgt - f.shape[0]) if air else (hgt - 1 - yb)
            sy0, dy0 = max(0, -y), max(0, y); sx0, dx0 = max(0, -x), max(0, x)
            hh = min(f.shape[0] - sy0, hgt - dy0); ww = min(f.shape[1] - sx0, 2 * half - dx0)
            src = f[sy0:sy0 + hh, sx0:sx0 + ww]; m = src[..., 3] > 0
            c[dy0:dy0 + hh, dx0:dx0 + ww][m] = src[m]
            placed.append(c)
        rows.append((name, a, placed, 2 * half, hgt))
        W = max(W, (2 * half + gap) * len(placed)); H += hgt + gap
    atlas = np.zeros((H, W, 4), np.uint8)
    meta, y = {}, 0
    for name, a, placed, fw, fh in rows:
        rects = []
        for i, f in enumerate(placed):
            x = i * (fw + gap); atlas[y:y + fh, x:x + fw] = f; rects.append([x, y, fw, fh])
        meta[name] = {k: v for k, v in a.items() if k != 'frames'}
        meta[name].update({'fps': a.get('fps', 10), 'w': fw, 'h': fh, 'frames': rects})
        y += fh + gap
    Image.fromarray(atlas, 'RGBA').save(path_png)
    json.dump(meta, open(path_json, 'w'), indent=0)
    return atlas, meta


def bg_lowres(path, w, h, colors=48):
    """Downscale a painted background to the internal resolution and quantize (no dithering)."""
    im = Image.open(path).convert('RGB').resize((w, h), Image.BOX)
    return im.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')


def mirror_tile(im):
    """Seamless horizontal loop: image + its mirror (for scrolling parallax bands)."""
    w, h = im.size
    out = Image.new(im.mode, (w * 2, h))
    out.paste(im, (0, 0)); out.paste(im.transpose(Image.FLIP_LEFT_RIGHT), (w, 0))
    return out

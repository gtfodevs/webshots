#!/usr/bin/env python3
"""Stamp a clean gold "1" medallion over a character's pendant (brand fix for Uno, whose generated
pendant reads like a cross). Finds the gold pendant under the chin automatically; --at u,v overrides.

  python3 scripts/pendant_one.py cutouts/uno-*.png [--size 0.07]
"""
import argparse, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rig_actor import rig

FONT = ['/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def find(im, r):
    a = np.asarray(im).astype(int); H, W = a.shape[:2]
    R, G, B, A = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    gold = (A > 128) & (R > 120) & (R - B > 45) & (G - B > 20) & (R >= G - 5)
    ex = np.mean([e[0] for e in r['eyes']]) * W; neck = r['head']['neck'] * H; hgt = (r['feet'] - r['head']['top']) * H
    win = np.zeros_like(gold); win[int(neck + hgt * 0.02): int(neck + hgt * 0.2), int(max(0, ex - hgt * 0.07)): int(ex + hgt * 0.07)] = True
    g = gold & win
    if g.sum() < 20: return None
    lab, n = ndimage.label(ndimage.binary_dilation(g, iterations=3))
    sizes = ndimage.sum(g, lab, range(1, n + 1)); k = int(np.argmax(sizes)) + 1
    ys, xs = np.nonzero((lab == k) & g)
    # the pendant hangs at the bottom of the chain: use the lower 60% of that cluster
    lo = ys > ys.min() + (ys.max() - ys.min()) * 0.4
    return xs[lo].mean(), ys[lo].mean(), max(ys.max() - ys[lo].min(), hgt * 0.05)


def stamp(path, size, at=None):
    im = Image.open(path).convert('RGBA'); r = rig(path); W, H = im.size
    f = (at[0] * W, at[1] * H, size * H) if at else find(im, r)
    if not f: print('no pendant found', path); return
    cx, cy, h = f; rad = max(h * 0.62, size * H * 0.5)
    S = 4; d = int(rad * 2 * S + 8)
    med = Image.new('RGBA', (d, d)); dr = ImageDraw.Draw(med); c = d / 2; R = rad * S
    dr.ellipse([c - R, c - R, c + R, c + R], fill=(40, 22, 8, 255))
    for i in range(int(R * 0.9), 0, -1):  # radial gold gradient
        t = i / (R * 0.9); col = (int(255 - 70 * t), int(222 - 90 * t), int(120 - 90 * t), 255)
        dr.ellipse([c - i - R * 0.03, c - i - R * 0.06, c + i - R * 0.03, c + i - R * 0.06], fill=col)
    font = ImageFont.truetype(next(p for p in FONT if __import__('os').path.exists(p)), int(R * 1.45))
    dr.text((c + R * 0.04, c + R * 0.08), '1', font=font, anchor='mm', fill=(70, 38, 6, 255))
    dr.text((c, c), '1', font=font, anchor='mm', fill=(255, 236, 160, 255), stroke_width=int(R * 0.05), stroke_fill=(120, 70, 10, 255))
    dr.ellipse([c - R * 0.5, c - R * 0.75, c - R * 0.1, c - R * 0.45], fill=(255, 255, 230, 170))  # gloss
    med = med.resize((d // S, d // S), Image.LANCZOS)
    im.alpha_composite(med, (int(cx - med.width / 2), int(cy - med.height / 2)))
    im.save(path); print('stamped', path, int(cx), int(cy), int(rad))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--size', type=float, default=0.06)
    ap.add_argument('--at'); a = ap.parse_args()
    for p in a.files: stamp(p, a.size, [float(v) for v in a.at.split(',')] if a.at else None)

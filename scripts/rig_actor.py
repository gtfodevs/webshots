#!/usr/bin/env python3
"""Auto-rig transparent character cutouts for the music-mode actor layer (lib/actor-kit.js).

  python3 scripts/rig_actor.py cutouts/*.png -o rig.json [--overrides rig.overrides.json]

For each PNG it measures, in 0..1 image coordinates (u = x / width, v = y / height):
  eyes        glowing eye centroids (small saturated red/orange blobs in the head band)
  head        {cx, top, neck}: head centre x, top of the silhouette, neck line
  shoulders   v of the shoulder line; hip: v of the hip line; feet: v of the lowest pixels
  ears        headphone centres (left/right of the eyes at eye height)
  glow        extra light sources: {"magic": [u, v]} (cyan blobs, e.g. a spell), {"gold": [u, v]}
  bodyW       silhouette half-width at chest height (for arm/side weights)
Overrides (same keys) are merged per file stem, so a human can fix any guess.
The runtime turns these into vertex weights (head, chest, arms, hem) for mesh warping, so
parts move independently without ever cutting the image into seams.
"""
import argparse, json, os
import numpy as np
from PIL import Image
from scipy import ndimage


def blobs(mask, min_px=4, max_px=4000):
    lab, n = ndimage.label(mask)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if min_px <= len(xs) <= max_px:
            out.append((xs.mean(), ys.mean(), len(xs)))
    return out


def rig(path):
    im = np.asarray(Image.open(path).convert('RGBA')).astype(int)
    H, W = im.shape[:2]
    r, g, b, a = im[..., 0], im[..., 1], im[..., 2], im[..., 3]
    solid = a > 128
    rows = np.nonzero(solid.any(axis=1))[0]
    top, bottom = rows[0], rows[-1]
    hgt = bottom - top
    # eyes: very red, bright, small, in the upper part of the figure
    red = solid & (r > 190) & (g < 110) & (b < 120) & (r - g > 110)
    band = np.zeros_like(red); band[top: top + int(hgt * 0.3)] = True
    cand = blobs(red & band, 3, int(W * H * 0.002))
    eyes = []
    if cand:
        cand.sort(key=lambda c: -c[2])
        best = None
        for i in range(len(cand)):
            for j in range(i + 1, len(cand)):
                (x1, y1, s1), (x2, y2, s2) = cand[i], cand[j]
                if abs(y1 - y2) < hgt * 0.03 and hgt * 0.015 < abs(x1 - x2) < hgt * 0.12:
                    score = s1 + s2 - abs(y1 - y2) * 4
                    if best is None or score > best[0]: best = (score, sorted([(x1, y1), (x2, y2)]))
        if best: eyes = best[1]
        else: eyes = [cand[0][:2]]
    if eyes:
        ey = np.mean([e[1] for e in eyes]); ex = np.mean([e[0] for e in eyes])
    else:
        ey = top + hgt * 0.07; ex = np.nonzero(solid[int(ey)])[0].mean()
    # head width at eye level -> ears
    row = np.nonzero(solid[int(ey)])[0]
    near = row[np.abs(row - ex) < hgt * 0.09] if len(row) else np.array([ex])
    hl, hr = near.min(), near.max()
    neck = min(bottom, ey + hgt * 0.07)
    shoulders = neck + hgt * 0.04
    hip = top + hgt * 0.5
    chest = int(neck + hgt * 0.1)
    crow = np.nonzero(solid[chest])[0]
    body_w = (np.percentile(crow, 85) - np.percentile(crow, 15)) / 2 if len(crow) else W * 0.2
    # extra glows
    glow = {}
    cyan = solid & (b > 200) & (g > 190) & (r < 170)
    if cyan.sum() > W * H * 0.002:
        ys, xs = np.nonzero(cyan); glow['magic'] = [xs.mean() / W, ys.mean() / H]
    gold = solid & (r > 150) & (g > 105) & (b < 95) & (r - b > 80)
    gb = gold.copy(); gb[: int(neck)] = False; gb[int(top + hgt * 0.42):] = False
    if gb.sum() > 30:
        lab, n = ndimage.label(ndimage.binary_dilation(gb, iterations=2))
        # the pendant: the gold component whose lowest pixel is lowest near the centre line
        best = None
        for i in range(1, n + 1):
            ys, xs = np.nonzero(lab == i)
            if abs(xs.mean() - ex) < body_w * 0.6 and (best is None or ys.max() > best[1]): best = (i, ys.max())
        if best:
            ys, xs = np.nonzero((lab == best[0]) & gb)
            # pendant = lower part of that component
            lo = ys > ys.max() - hgt * 0.07
            glow['gold'] = [xs[lo].mean() / W, ys[lo].mean() / H, (ys.max() - ys[lo].min()) / H]
    return {
        'w': W, 'h': H,
        'eyes': [[x / W, y / H] for x, y in eyes],
        'ears': [[hl / W, ey / H], [hr / W, ey / H]],
        'head': {'cx': ex / W, 'top': top / H, 'neck': neck / H, 'r': (hr - hl) / 2 / W},
        'shoulders': shoulders / H, 'hip': hip / H, 'feet': bottom / H, 'bodyW': body_w / W,
        'glow': glow,
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--overrides')
    a = ap.parse_args()
    ov = json.load(open(a.overrides)) if a.overrides and os.path.exists(a.overrides) else {}
    res = {}
    for f in a.files:
        k = os.path.splitext(os.path.basename(f))[0]
        res[k] = rig(f)
        for kk, vv in ov.get(k, {}).items():
            if isinstance(vv, dict) and isinstance(res[k].get(kk), dict): res[k][kk].update(vv)
            else: res[k][kk] = vv
        o = ov.get(k, {})
        if 'eyes' in o and res[k]['eyes'] and 'neck' not in o.get('head', {}):
            r = res[k]; ey = sum(e[1] for e in r['eyes']) / len(r['eyes'])
            r['head']['neck'] = ey + (r['feet'] - r['head']['top']) * 0.07
            r['head']['cx'] = sum(e[0] for e in r['eyes']) / len(r['eyes'])
        print(k, 'eyes', len(res[k]['eyes']), 'glow', list(res[k]['glow']))
    json.dump(res, open(a.out, 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()

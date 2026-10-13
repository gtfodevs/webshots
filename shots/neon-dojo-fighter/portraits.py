#!/usr/bin/env python3
"""Neon Dojo: VS portraits + super cut-ins.  python3 shots/neon-dojo-fighter/portraits.py  (repo root)
portraits/<c>.jpg: busts on #00FF00 facing left -> key + despill (edge band and interior spill clamp) -> crop -> 340 px tall
                   -> stage/assets/px/portrait-<c>.png (the page mirrors the left-side fighter so the pair face each other)
cutins/<c>.jpg:    full-frame 16:9 -> 960x540 -> stage/assets/px/cutin-<c>.png (the page shows a horizontal band of it)"""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = f'{ROOT}/channels/progressiveslop/assets/neon-dojo-fighter/source'
PX = f'{os.path.dirname(os.path.abspath(__file__))}/stage/assets/px'
rep = {'portraits': {}, 'cutins': {}}
for f in sorted(os.listdir(f'{SRC}/portraits')):
    c = f.split('.')[0]; im = np.asarray(Image.open(f'{SRC}/portraits/{f}').convert('RGB')).astype(int); r, g, b = im[..., 0], im[..., 1], im[..., 2]
    green = (g > 110) & (g > r + 40) & (g > b + 40)
    a = ~green; lab, n = ndimage.label(a); sz = ndimage.sum(a, lab, range(1, n + 1))
    a = np.isin(lab, 1 + np.where(sz >= max(300, sz.max() * 0.01))[0]); a = ndimage.binary_opening(a, iterations=1)
    a = ndimage.binary_erosion(a, iterations=1) | (a & (im.max(2) < 60))   # eat the 1px green-mixed rim
    out = im.copy(); m = np.maximum(r, b)
    edge = a & ~ndimage.binary_erosion(a, iterations=4); sp = edge & (g > m); out[..., 1][sp] = m[sp]
    gs = a & (g > m + 20); out[..., 1][gs] = m[gs] + 20
    ys, xs = np.where(a); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([np.clip(out, 0, 255), a * 255]).astype(np.uint8)[y0:y1, x0:x1]
    p = Image.fromarray(rgba); k = 340 / p.height; p = p.resize((round(p.width * k), 340), Image.LANCZOS)
    q = np.asarray(p).copy(); q[..., 3] = np.where(q[..., 3] > 127, 255, 0); Image.fromarray(q).save(f'{PX}/portrait-{c}.png')
    rep['portraits'][c] = list(q.shape[:2][::-1])
for f in sorted(os.listdir(f'{SRC}/cutins')):
    c = f.split('.')[0]; Image.open(f'{SRC}/cutins/{f}').convert('RGB').resize((960, 540), Image.LANCZOS).save(f'{PX}/cutin-{c}.png'); rep['cutins'][c] = [960, 540]
json.dump(rep, open(f'{PX}/portraits.json', 'w'), indent=1); print(rep)

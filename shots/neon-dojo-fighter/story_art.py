#!/usr/bin/env python3
"""Neon Dojo: story close-ups, ending panels, world map, logo -> stage/assets/px.  python3 shots/neon-dojo-fighter/story_art.py
Panels are full-frame 16:9 stored at 1056x594 (1.1x the 960x540 world) so the Ken Burns move never upscales past the source.
The logo is keyed off #00FF00 and despilled. Map pins are measured from the magenta rings (960x540 coordinates)."""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = f'{ROOT}/channels/progressiveslop/assets/neon-dojo-fighter/source'
PX = f'{os.path.dirname(os.path.abspath(__file__))}/stage/assets/px'
meta = {'panels': []}
for d in ('story', 'ending'):
    for f in sorted(os.listdir(f'{SRC}/{d}')):
        n = f.split('.')[0]; Image.open(f'{SRC}/{d}/{f}').convert('RGB').resize((1056, 594), Image.LANCZOS).save(f'{PX}/panel-{n}.png'); meta['panels'].append(n)
mp = Image.open(f'{SRC}/ui/world_map.jpg').convert('RGB').resize((960, 540), Image.LANCZOS); mp.save(f'{PX}/world-map.png')
im = np.asarray(mp).astype(int); r, g, b = im[..., 0], im[..., 1], im[..., 2]
m = (r > 160) & (b > 130) & (g < 130) & (r > b - 40); lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=6))
sz = ndimage.sum(m, lab, range(1, n + 1)); pins = []
for i in np.argsort(-sz)[:5]:
    ys, xs = np.where((lab == i + 1) & m); pins.append([int((xs.min() + xs.max()) // 2), int((ys.min() + ys.max()) // 2), int(xs.max() - xs.min())])
meta['pins'] = pins
L = np.asarray(Image.open(f'{SRC}/ui/logo.jpg').convert('RGB')).astype(int); r, g, b = L[..., 0], L[..., 1], L[..., 2]
a = ~((g > 110) & (g > r + 40) & (g > b + 40)); lb, n = ndimage.label(a); s_ = ndimage.sum(a, lb, range(1, n + 1))
a = np.isin(lb, 1 + np.where(s_ >= 200)[0]); a = ndimage.binary_erosion(ndimage.binary_opening(a, iterations=1), iterations=1)
out = L.copy(); mx = np.maximum(r, b); sp = a & (g > mx); out[..., 1][sp] = mx[sp]
ys, xs = np.where(a); rgba = np.dstack([np.clip(out, 0, 255), a * 255]).astype(np.uint8)[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
lg = Image.fromarray(rgba); k = 560 / lg.width; lg = lg.resize((560, round(lg.height * k)), Image.LANCZOS)
q = np.asarray(lg).copy(); q[..., 3] = np.where(q[..., 3] > 127, 255, 0); Image.fromarray(q).save(f'{PX}/logo.png'); meta['logo'] = list(q.shape[:2][::-1])
gr = (q[..., 3] > 0) & (q[..., 1].astype(int) > np.maximum(q[..., 0], q[..., 2]).astype(int) + 30); meta['logo_green_px'] = int(gr.sum())
json.dump(meta, open(f'{PX}/story.json', 'w'), indent=1); print(meta)

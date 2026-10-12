#!/usr/bin/env python3
"""Light maps for animated backgrounds (music mode, lib/actor-kit.js ActorKit.bgfx).

  python3 scripts/bg_lightmap.py bg-lair.jpg -o layers/bg-lair [--keys red,cyan,purple,white] [--points 40]

Writes <out>-glow-<key>.png (only the pixels that glow in that colour family, on black, so the
stage can screen-blend them and pulse or sweep their opacity without repainting the art) and
<out>.fx.json with sparkle points (bright, well-separated local maxima) for twinkles and glints.
"""
import argparse, json
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

KEYS = {
    'red': lambda h, s, v: ((h < 0.04) | (h > 0.95)) & (s > 0.55) & (v > 0.45),
    'cyan': lambda h, s, v: (h > 0.45) & (h < 0.56) & (s > 0.35) & (v > 0.55),
    'purple': lambda h, s, v: (h > 0.70) & (h < 0.90) & (s > 0.4) & (v > 0.45),
    'magenta': lambda h, s, v: (h > 0.86) & (h < 0.97) & (s > 0.4) & (v > 0.5),
    'white': lambda h, s, v: (s < 0.18) & (v > 0.9),
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--keys', default='red,cyan,purple,white'); ap.add_argument('--points', type=int, default=40)
    a = ap.parse_args()
    im = Image.open(a.src).convert('RGB'); rgb = np.asarray(im).astype(float) / 255
    hsv = np.asarray(im.convert('HSV')).astype(float) / 255
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    fx = {'size': im.size, 'glow': {}, 'points': {}}
    for k in a.keys.split(','):
        m = KEYS[k](h, s, v).astype(float)
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(float) / 255
        out = (rgb * m[..., None] * 255).clip(0, 255).astype(np.uint8)
        path = f'{a.out}-glow-{k}.png'; Image.fromarray(out).save(path, optimize=True)
        fx['glow'][k] = {'file': path.rsplit('/', 1)[-1], 'coverage': round(float(m.mean()), 4)}
        # sparkle points of this colour: local maxima of brightness inside the mask
        lum = (v * m)
        mx = ndimage.maximum_filter(lum, size=41)
        ys, xs = np.nonzero((lum == mx) & (lum > 0.6))
        order = np.argsort(-lum[ys, xs])[: a.points]
        fx['points'][k] = [[int(xs[i]), int(ys[i])] for i in order]
    json.dump(fx, open(a.out + '.fx.json', 'w'), indent=1)
    print(a.out, {k: g['coverage'] for k, g in fx['glow'].items()})


if __name__ == '__main__':
    main()

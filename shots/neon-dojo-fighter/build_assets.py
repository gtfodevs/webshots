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

# ---------- stage art: rooftop dojo (fight 1) -> parallax layers at 960x540 ----------
# Layers (back to front): sky (full picture, also fills any edge a nearer layer exposes), skyline band,
# gate + side pagodas + railing/crowd, crowd band (bobs 1px on the beat), railing band (covers the bob gap), floor.
SD = os.path.join(ROOT, 'channels/progressiveslop/assets/neon-dojo-fighter/source/stages')
src = os.path.join(SD, 'rooftop_dojo.jpg')
if os.path.exists(src):
    im = np.asarray(Image.open(src).convert('RGB').resize((960, 540), Image.LANCZOS))
    def layer(mask, name):
        out = np.zeros((540, 960, 4), np.uint8); out[..., :3] = im; out[..., 3] = mask * 255
        Image.fromarray(out).save(os.path.join(OUT, f'stage-rooftop-{name}.png'))
    Y, X = np.mgrid[0:540, 0:960]
    gate = ((X >= 286) & (X <= 690) & (Y >= 95) & (Y < 300) & ~((X > 410) & (X < 560) & (Y > 222))) | (((X < 84) | (X > 876)) & (Y >= 30) & (Y < 300)) | ((Y >= 222) & (Y < 300) & ((X < 140) | (X > 820) | ((X > 280) & (X < 345)) | ((X > 630) & (X < 690))))
    front = (Y >= 300) & (Y < 422)
    floor = Y >= 422
    skyline = (Y >= 120) & (Y < 300) & ~gate
    np.asarray(Image.fromarray(im)).copy()
    Image.fromarray(im).save(os.path.join(OUT, 'stage-rooftop-sky.png'))
    layer(skyline, 'skyline'); layer(gate | front, 'gate'); layer(floor, 'floor')
    crowd = (Y >= 300) & (Y < 372) & ~((X > 240) & (X < 308)) & ~((X > 650) & (X < 722)); layer(crowd, 'crowd')
    layer((Y >= 368) & (Y < 422), 'rail')
    json.dump({'ground': 476, 'floor_top': 422, 'lanterns': [[33, 258, 16], [77, 284, 12], [117, 289, 11], [315, 254, 17], [657, 254, 17], [843, 288, 11], [882, 284, 12], [927, 258, 16]],
               'speeds': {'sky': 0.1, 'skyline': 0.3, 'gate': 0.6, 'floor': 1.0}}, open(os.path.join(OUT, 'stage-rooftop.json'), 'w'), indent=1)
    print('stage rooftop ok')

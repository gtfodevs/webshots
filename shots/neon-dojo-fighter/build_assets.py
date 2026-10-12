#!/usr/bin/env python3
"""Neon Dojo fighter: build stage/assets/px/ (placeholder pass: only the 1-bit 8px pixel font).
python3 shots/neon-dojo-fighter/build_assets.py   (run from the repo root)
Font: Press Start 2P (OFL) from channels/progressiveslop/assets/kingdom-come-16bit/fonts/. Media is not committed (ASSETS.md)."""
import os
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

#!/usr/bin/env python3
"""Preview GIFs for one sprite character: python3 shots/neon-dojo-fighter/tools_gifs.py uno OUTDIR
One GIF per anim (frames + durations from stage/fight.js SPRITE_ANIMS), anchored on a ground line, 2x nearest (= 1080p size)."""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw
c, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
D = os.path.dirname(os.path.abspath(__file__)); M = json.load(open(f'{D}/stage/assets/px/{c}.json')); A = Image.open(f'{D}/stage/assets/px/{c}.png')
js = subprocess.run(['node', '-e', f"const vm=require('vm'),fs=require('fs');const x={{}};vm.createContext(x);vm.runInContext(fs.readFileSync('{D}/stage/fight.js','utf8'),x);console.log(JSON.stringify(x.FIGHT.SPRITE_ANIMS['{c}']))"], capture_output=True, text=True, check=True)
AN = json.loads(js.stdout); S = 2
# single-pose anims are previewed in context (from / back to the stance) so the GIF shows the motion
AN['block'] = {'frames': ['idle_a', 'block'], 'durations': [400, 700]}
AN['hit'] = {'frames': ['idle_a', 'hit', 'idle_a'], 'durations': [400, 350, 300]}
AN['ko'] = {'frames': ['hit', 'ko_fall', 'ko_down'], 'durations': [200, 450, 1200]}
for k in ('ko_fall', 'ko_down'): AN.pop(k)
for name, a in AN.items():
    fr = [M['frames'][p] for p in a['frames']]
    left = max(f['ax'] for f in fr) + 20; right = max(f['rect'][2] - f['ax'] for f in fr) + 20; top = max(f['ay'] for f in fr) + 16
    W, H = left + right, top + 14; ims = []
    for p, f in zip(a['frames'], fr):
        im = Image.new('RGBA', (W, H), (26, 12, 54, 255)); d = ImageDraw.Draw(im); d.rectangle([0, top + 1, W, H], fill=(18, 8, 40, 255)); d.line([0, top + 1, W, top + 1], fill=(255, 63, 210, 255))
        d.rectangle([left - 40, top - 1, left + 40, top + 2], fill=(0, 0, 0, 120))
        x, y, w, h = f['rect']; spr = A.crop((x, y, x + w, y + h)); lift = 20 if f.get('air') else 0
        im.alpha_composite(spr, (left - f['ax'], top - f['ay'] - lift)); ims.append(im.convert('RGB').resize((W * S, H * S), Image.NEAREST))
    ims[0].save(f'{OUT}/{c}_{name}.gif', save_all=True, append_images=ims[1:], duration=a['durations'], loop=0, disposal=2)
    print(name, len(ims), 'frames')

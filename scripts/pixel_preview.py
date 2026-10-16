"""Export sprite loops as 4x strips (PNG) and animated GIFs for review.
   python3 scripts/pixel_preview.py <atlas.png> <atlas.json> <outdir> anim[:fps] ..."""
import sys, json, os
from PIL import Image
png, js, out, *names = sys.argv[1:]
A = Image.open(png).convert('RGBA'); M = json.load(open(js)); os.makedirs(out, exist_ok=True)
BG = (58, 36, 92, 255)
for spec in names:
    n, _, fps = spec.partition(':'); m = M[n]; fps = float(fps or m['fps'])
    fr = [A.crop((x, y, x + w, y + h)) for x, y, w, h in m['frames']]
    w, h = m['w'], m['h']; ground = Image.new('RGBA', (w + 8, h + 4), BG)
    tiles = []
    for f in fr:
        t = ground.copy(); t.alpha_composite(f, (4, 2))
        for x in range(0, w + 8, 4): t.putpixel((x, h + 2), (20, 10, 40, 255))  # ground ticks (foot-slide check)
        tiles.append(t)
    strip = Image.new('RGBA', ((w + 9) * len(tiles), h + 4), (20, 10, 40, 255))
    for i, t in enumerate(tiles): strip.paste(t, (i * (w + 9), 0))
    strip.resize((strip.width * 4, strip.height * 4), Image.NEAREST).save(f'{out}/{n}-strip-4x.png')
    big = [t.resize((t.width * 4, t.height * 4), Image.NEAREST).convert('P', palette=Image.ADAPTIVE) for t in tiles]
    big[0].save(f'{out}/{n}.gif', save_all=True, append_images=big[1:], duration=int(1000 / fps), loop=0, disposal=2)
    print(out + '/' + n)

"""Build the 16-bit sprite atlas + low-res backgrounds for kingdom-come-16bit.
   python3 shots/kingdom-come-16bit/build_assets.py   (reads channels/progressiveslop/assets/kingdom-come-16bit/source)
Writes stage/assets/px/{sprites.png,sprites.json,bg-*.png} and the contact sheet out/kingdom-come-16bit/sprites.png."""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from pixel_sprites import *  # noqa

SRC = os.path.join(ROOT, 'channels/progressiveslop/assets/kingdom-come-16bit/source')
OUT = os.path.join(os.path.dirname(__file__), 'stage/assets/px'); os.makedirs(OUT, exist_ok=True)
W, H = 480, 270
SCALE = 0.25

# ---------- hero frames from the reference sheet ----------
rows = key_frames(os.path.join(SRC, 'sprites-ref.jpg'), [
    (20, 320, [0, 157, 297, 444, 617, 827, 962, 1103, 1280]),
    (380, 640, [0, 145, 281, 421, 563, 715, 959, 1114, 1280])])
small = [[downscale(f, SCALE) for f in r] for r in rows]
CYAN = (94, 231, 255); GOLD = (242, 196, 64); RED = (255, 40, 60)
pal = build_palette([f for r in small for f in r], n=30, fixed=[CYAN, GOLD, RED, (250, 250, 255)])
U = [outline(despeckle(quantize(f, pal))) for f in small[0]]
A = [outline(despeckle(quantize(f, pal))) for f in small[1]]

def same(frames):
    w = max(f.shape[1] for f in frames); h = max(f.shape[0] for f in frames)
    return [pad_to(f, w, h) for f in frames]

def walk_from(f, legs_frac=0.32):
    """4-frame front walk: alternate foot lift + 1px body bob (pixel edits)."""
    f = pad_to(f, f.shape[1], f.shape[0] + 2)
    h, w = f.shape[:2]; ly = int(h * (1 - legs_frac)); mid = w // 2
    up = shift_rows(f, 0, ly, dy=-1)
    l = shift_region(up, (0, ly, mid, h), dy=-2)
    r = shift_region(up, (mid, ly, w, h), dy=-2)
    return [f, l, f, r]

def bob(f, top_frac=0.55, n=1):
    f = pad_to(f, f.shape[1], f.shape[0] + 1)
    y = int(f.shape[0] * top_frac)
    return shift_rows(f, 0, y, dy=n)

anims = {}
def bobf(f, n=3):  # off-beat squash: upper body drops n px (pixel edit), same canvas
    return shift_rows(f, 0, int(f.shape[0] * 0.62), dy=n)
ui = same(U)
anims['uno_idle'] = {'fps': 8, 'frames': [ui[0], ui[1], ui[2], ui[1]]}
anims['uno_walk'] = {'fps': 8, 'frames': walk_from(U[0])}
anims['uno_slash'] = {'fps': 10, 'frames': [ui[0], ui[3], ui[3], ui[4], ui[4], ui[4], ui[7], ui[0]]}
anims['uno_cheer'] = {'fps': 8, 'frames': [ui[5], bobf(ui[5]), ui[7], bobf(ui[7])]}
# one bar = 8 half-beat frames: pose on the beat, squash on the off-beat
anims['uno_dance'] = {'fps': 8, 'frames': [ui[6], bobf(ui[6]), ui[5], bobf(ui[5]), ui[6], bobf(ui[6]), ui[7], bobf(ui[7])]}
ai = same(A)
anims['aura_idle'] = {'fps': 8, 'frames': same([A[0], bob(A[0]), bob(A[0]), A[0]])}
anims['aura_walk'] = {'fps': 8, 'frames': [ai[0], ai[1], ai[2], ai[1]]}
anims['aura_cast'] = {'fps': 10, 'frames': [ai[3], ai[4], ai[5], ai[5], ai[4]]}
anims['aura_twirl'] = {'fps': 8, 'frames': [ai[7], ai[0], flip(ai[7]), flip(ai[0])]}
anims['aura_dance'] = {'fps': 8, 'frames': [ai[6], bobf(ai[6]), ai[7], bobf(ai[7]), flip(ai[6]), bobf(flip(ai[6])), flip(ai[7]), bobf(flip(ai[7]))]}

# ---------- NPCs: derived from the same reference frames (same shading, outline, chrome) ----------
# Each NPC is a hero frame re-sampled at its own size, recoloured by hue (cloak/gown/gold), with
# shaded pixel accessories (hats, helmets, horns, staffs). Same palette => same detail level as the heroes.
import colorsys
SIL, SIL2, SIL3, HI = (196, 202, 220), (140, 146, 170), (92, 96, 124), (240, 244, 255)
PUR, PUR2, MAG, DARK = (122, 52, 200), (74, 28, 130), (255, 63, 210), (40, 20, 60)
EYE = RED
def canvas(w, h): return Image.new('RGBA', (w, h), (0, 0, 0, 0))

def frames_at(row, scale):
    return [despeckle(quantize(downscale(f, scale), pal)) for f in rows[row]]

def hsv(a):
    f = a[..., :3].astype(float) / 255
    mx, mn = f.max(-1), f.min(-1); d = mx - mn + 1e-9
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, (mx - mn) / (mx + 1e-9), mx

def ramp(rgb):  # 4-step shade ramp from one base colour
    r, g, b = [c / 255 for c in rgb]; h, l, s_ = colorsys.rgb_to_hls(r, g, b)
    return [tuple(int(255 * c) for c in colorsys.hls_to_rgb(h, ll, s_)) for ll in (0.16, 0.30, 0.46, 0.64)]

def recolor(f, hues, base, y0=0.22, min_sat=0.28):
    """Map pixels whose hue is in any (lo, hi) range (below y0 of the height: keeps the red eyes) onto a shade ramp of base."""
    h, s_, v = hsv(f); out = f.copy(); R4 = np.array(ramp(base))
    m = np.zeros(h.shape, bool)
    for lo, hi in hues: m |= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
    m &= (s_ > min_sat) & (f[..., 3] > 0)
    m[: int(f.shape[0] * y0)] = False
    idx = np.clip((v * 4.2).astype(int), 0, 3)
    out[m, :3] = R4[idx[m]]
    return out

CLOAK = [(250, 320)]; GOLDH = [(30, 60)]; GOWN = [(335, 20)]
def head_of(f):
    ys, xs = np.where(f[..., 3] > 0); top = ys.min()
    band = xs[ys < top + 6]; return int(band.mean()), top

def pad(f, l=0, r=0, t=0):
    return np.pad(f, ((t, 0), (l, r), (0, 0)))

def draw_on(f, fn):
    im = Image.fromarray(f, 'RGBA'); fn(ImageDraw.Draw(im), *head_of(f)); return np.asarray(im).copy()

def hop(f, n):
    f = pad(f, t=4); return shift_rows(f, 0, f.shape[0], dy=-n) if n else f

# --- Wizard: robe recoloured deep blue, pointed hat with gold band + star, staff with a cyan orb
def wizard_frames():
    base = frames_at(0, 0.235)
    out = []
    for k, i in enumerate([0, 1, 2, 1]):
        f = recolor(recolor(base[i], CLOAK, (60, 70, 200)), GOLDH, (200, 205, 225), min_sat=0.15)
        f = pad(f, l=4, r=10, t=16)
        def acc(d, cx, top, k=k):
            d.polygon([(cx - 9, top + 4), (cx + 9, top + 4), (cx + 3, top - 15), (cx + 6, top - 17)], fill=(70, 30, 150))
            d.polygon([(cx - 9, top + 4), (cx - 1, top + 4), (cx + 2, top - 13)], fill=(110, 56, 210))
            d.line([(cx - 9, top + 2), (cx + 9, top + 2)], fill=GOLD, width=2)
            d.point([(cx + 2, top - 6), (cx + 1, top - 5), (cx + 3, top - 5), (cx + 2, top - 4)], fill=(255, 240, 150))
            sx = cx + 15; d.line([(sx, top + 2), (sx, top + 58)], fill=(150, 110, 70), width=2); d.line([(sx + 1, top + 2), (sx + 1, top + 58)], fill=(200, 160, 110))
            gl = [CYAN, (190, 250, 255), CYAN, (40, 160, 220)][k]
            d.ellipse([sx - 3, top - 5, sx + 4, top + 2], fill=gl); d.point([(sx - 1, top - 3)], fill=(255, 255, 255))
        out.append(outline(draw_on(f, acc)))
    return out

# --- Jester: cloak magenta, chain cyan, two-point hat with bells; hop loop
def jester_frames():
    base = frames_at(0, 0.215)
    out = []
    for k, (i, n) in enumerate([(0, 0), (1, 2), (2, 3), (1, 1)]):
        f = recolor(recolor(base[i], CLOAK, (230, 40, 180)), GOLDH, (200, 205, 225), min_sat=0.15)
        f = pad(f, l=8, r=8, t=12)
        def acc(d, cx, top, k=k):
            sw = [0, 1, 2, 1][k]
            d.polygon([(cx - 7, top + 5), (cx, top + 1), (cx - 14, top - 6 + sw)], fill=(230, 40, 180))
            d.polygon([(cx - 7, top + 5), (cx - 3, top + 3), (cx - 14, top - 6 + sw)], fill=(150, 20, 120))
            d.polygon([(cx + 7, top + 5), (cx, top + 1), (cx + 14, top - 6 + 2 - sw)], fill=(60, 210, 240))
            d.polygon([(cx + 7, top + 5), (cx + 3, top + 3), (cx + 14, top - 6 + 2 - sw)], fill=(20, 130, 180))
            d.ellipse([cx - 16, top - 8 + sw, cx - 13, top - 5 + sw], fill=GOLD); d.ellipse([cx + 13, top - 6 - sw, cx + 16, top - 3 - sw], fill=GOLD)
            d.line([(cx - 7, top + 5), (cx + 7, top + 5)], fill=GOLD)
        out.append(hop(outline(draw_on(f, acc)), n))
    return out

# --- Knight guard: cloak steel-navy, chain red, helmet crest plume, spear; idle + walk
def knight_dress(f, k=0):
    f = recolor(recolor(f, CLOAK, (50, 60, 110)), GOLDH, (200, 205, 225), min_sat=0.15)
    f = pad(f, l=2, r=10, t=10)
    def acc(d, cx, top):
        d.polygon([(cx - 1, top + 1), (cx + 2, top + 1), (cx + 6, top - 7), (cx + 1, top - 6)], fill=MAG)
        d.line([(cx + 1, top - 6), (cx + 5, top - 7)], fill=(255, 160, 230))
        d.line([(cx - 6, top + 6), (cx + 6, top + 6)], fill=SIL3)
        sx = cx + 16; d.line([(sx, top - 6), (sx, top + 56)], fill=SIL3, width=2); d.line([(sx, top - 6), (sx, top + 56)], fill=SIL)
        d.polygon([(sx - 2, top - 5), (sx + 2, top - 5), (sx, top - 11)], fill=HI)
    return outline(draw_on(f, acc))
def knight_frames():
    base = frames_at(0, 0.23)
    return [knight_dress(base[i]) for i in [0, 1, 2, 1]]

# --- Sorcerer boss: big (~85 px), black-crimson cloak, magenta chain, horns, orb staff
def boss_frames():
    base = frames_at(0, 0.35)
    out = []
    for k, i in enumerate([0, 1, 2, 1]):
        f = recolor(recolor(base[i], CLOAK, (120, 10, 50)), GOLDH, (200, 205, 225), min_sat=0.15)
        f = pad(f, l=6, r=14, t=18)
        def acc(d, cx, top, k=k):
            for sgn in (-1, 1):
                pts = [(cx + sgn * 8, top + 8), (cx + sgn * 12, top + 1), (cx + sgn * 13, top - 8), (cx + sgn * 10, top - 14), (cx + sgn * 9, top - 6), (cx + sgn * 6, top + 3)]
                d.polygon(pts, fill=SIL3); d.line(pts[1:4], fill=SIL)
            sx = cx + 23; d.line([(sx, top - 4), (sx, top + 84)], fill=(60, 40, 70), width=3); d.line([(sx, top - 4), (sx, top + 84)], fill=SIL3)
            d.polygon([(sx - 5, top - 2), (sx, top + 4), (sx + 5, top - 2)], fill=SIL3)
            gl = [MAG, (255, 160, 240), MAG, (180, 30, 150)][k]
            d.ellipse([sx - 6, top - 14, sx + 6, top - 2], fill=gl); d.ellipse([sx - 3, top - 11, sx, top - 8], fill=(255, 230, 250))
        out.append(outline(draw_on(f, acc)))
    return out

# --- Crowd: two designs (mini-Uno, mini-Aura) x palette variants; 4-frame dance (pose / squash)
def crowd_frames(v):
    if v % 2 == 0:
        b = frames_at(0, 0.19); col = [(60, 210, 240), (240, 190, 60)][v // 2]
        fr = [recolor(recolor(x, GOLDH, (200, 205, 225), min_sat=0.15), CLOAK, col) for x in (b[5], b[6])]
    else:
        b = frames_at(1, 0.19); col = [(230, 40, 180), (60, 210, 240)][v // 2]
        fr = [recolor(x, GOWN, col, y0=0.3) for x in (b[6], b[7])]
    fr = [outline(x) for x in fr]
    w = max(x.shape[1] for x in fr); h = max(x.shape[0] for x in fr) + 3
    fr = [pad_to(x, w, h) for x in fr]
    sq = lambda x: shift_rows(x, 0, int(h * 0.6), dy=2)
    if v % 2: return [fr[0], sq(fr[0]), fr[1], sq(flip(fr[1]))]
    return [fr[0], sq(fr[0]), fr[1], sq(fr[1])]

anims['wizard_idle'] = {'fps': 6, 'frames': wizard_frames()}
anims['jester_hop'] = {'fps': 8, 'frames': jester_frames()}
anims['knight_idle'] = {'fps': 6, 'frames': knight_frames()}
anims['knight_walk'] = {'fps': 8, 'frames': [knight_dress(x) for x in walk_from(frames_at(0, 0.23)[0])]}
anims['boss_idle'] = {'fps': 8, 'frames': boss_frames()}
anims['boss_hurt'] = {'fps': 8, 'frames': anims['boss_idle']['frames'][:2]}
for v in range(4):
    anims[f'crowd{v}'] = {'fps': 4, 'frames': crowd_frames(v)}

# fx: spark burst (4 frames), coin (4 frames)
def spark(i):
    im = canvas(17, 17); d = ImageDraw.Draw(im); c = 8; r = 2 + i * 2
    col = [(255, 255, 255), CYAN, MAG, PUR][i]
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
        d.point([(c + dx * r, c + dy * r)], fill=col)
        if i < 2: d.point([(c + dx * (r - 1), c + dy * (r - 1))], fill=(255, 255, 255))
    if i == 0: d.rectangle([c - 1, c - 1, c + 1, c + 1], fill=(255, 255, 255))
    return np.asarray(im)
anims['spark'] = {'fps': 12, 'frames': [spark(i) for i in range(4)]}
def coin(i):
    im = canvas(10, 10); d = ImageDraw.Draw(im); w = [4, 3, 1, 3][i]
    d.ellipse([4 - w, 0, 5 + w, 9], fill=GOLD); d.line([(4, 2), (4, 7)], fill=(255, 245, 180)) if w > 1 else None
    return outline(np.asarray(im))
anims['coin'] = {'fps': 12, 'frames': [coin(i) for i in range(4)]}

exec(open(os.path.join(os.path.dirname(__file__), 'sprites_v2.py')).read())
atlas, meta = pack(anims, os.path.join(OUT, 'sprites.png'), os.path.join(OUT, 'sprites.json'))

# ---------- backgrounds: 480x270 quantized, split into sky (far) + ground (near) bands ----------
SPLIT = {'kingdom': 174, 'forest': 178, 'lair': 200, 'hall': 200}
for k, sy in SPLIT.items():
    im = bg_lowres(os.path.join(SRC, f'bg-{k}.jpg'), W, H, colors=64)
    im.save(os.path.join(OUT, f'bg-{k}.png'))
    mirror_tile(im.crop((0, 0, W, sy))).save(os.path.join(OUT, f'bg-{k}-far.png'))
    mirror_tile(im.crop((0, sy, W, H))).save(os.path.join(OUT, f'bg-{k}-near.png'))
json.dump(SPLIT, open(os.path.join(OUT, 'bg.json'), 'w'))


# ---------- forest parallax: 5 depth layers, seamless (wrap crossfade / periodic placement, no mirroring) ----------
from pixel_robots import Painter as _P, ramp_of as _ramp
def wrap_tile(im, ov=40):
    """Seamless horizontal tile without mirroring: crossfade the last ov px into the first ov px."""
    a = np.asarray(im.convert('RGBA')).astype(float); w = a.shape[1]
    t = np.linspace(0, 1, ov)[None, :, None]
    head = a[:, :ov] * t + a[:, w - ov:] * (1 - t)
    out = np.concatenate([head, a[:, ov:w - ov]], 1)
    return Image.fromarray(out[..., :3].astype(np.uint8), 'RGB').quantize(64, method=Image.MEDIANCUT, dither=Image.Dither.NONE).convert('RGBA')
def periodic_layer(period, h, items, seed, pal_):
    """Paint items (fn(fig, x)) at x positions, repeated at +-period so the tile wraps exactly."""
    fig = _P(period, h, K=3)
    for x, fn in items:
        for dx in (-period, 0, period): fn(fig, x + dx)
    a = fig.im.resize((period, h), Image.BOX); arr = np.asarray(a).astype(float)
    al = arr[..., 3:4] / 255; rgb = np.where(al > 0, arr[..., :3] / np.maximum(al, 1e-6), 0)
    o = np.dstack([np.clip(rgb, 0, 255), (al[..., 0] >= 0.45) * 255]).astype(np.uint8)
    return Image.fromarray(quantize(o, pal_), 'RGBA')
rng = np.random.default_rng(7)
fbg = Image.open(os.path.join(OUT, 'bg-forest.png'))
L0 = wrap_tile(fbg)                                   # 0.1x: the painted forest (sky/canopy/far trees)
GY = SPLIT['forest']
L3 = wrap_tile(fbg.crop((0, GY, W, H)))               # 1.0x: walkway floor
HAZE = [(28, 14, 52), (44, 26, 78), (66, 44, 108), (92, 68, 140), (120, 96, 170), (150, 130, 200)]
FGD = [(10, 6, 20), (22, 12, 38), (36, 22, 58), (52, 34, 80), (70, 50, 104), (90, 70, 130)]
CRM, CRC = _ramp((200, 60, 200)), _ramp((70, 170, 220))
FG_PAL = np.array(HAZE + FGD + CRM + CRC)
def trunk(fig, x, hz=HAZE, top=30, bot=GY + 2, w=6):
    r = np.random.default_rng(int(x) % 97 + 3)   # same tree for every repeat of x (seamless)
    pts = [(x + math.sin(k * 1.3 + x) * 5, bot - k * (bot - top - 30) / 6) for k in range(7)]
    for a, b in zip(pts, pts[1:]): fig.capsule(a, b, w - 0.3 * pts.index(a), hz)
    tx, ty = pts[-1]
    for side in (-1, 1): fig.capsule((tx, ty), (tx + side * 18, ty - 14), 2.4, hz)
    for k in range(14):   # crystal canopy: little shaded shards
        cx, cy = tx + r.uniform(-30, 30), ty - 14 + r.uniform(-16, 10); s_ = r.uniform(3, 6)
        fig.poly([(cx, cy - s_), (cx + s_ * 0.6, cy), (cx, cy + s_), (cx - s_ * 0.6, cy)], CRM if k % 2 else CRC)
P1 = 640
L1 = periodic_layer(P1, GY + 4, [(x, (lambda f, xx, x0=x: trunk(f, xx))) for x in range(40, P1, 110)], 1, FG_PAL)    # 0.3x mid trees
def crystals(fig, x, base=GY + 3):
    for k in range(3):
        cx = x + k * 7 - 7; hgt = rng.uniform(8, 20)
        rmp = _ramp((60, 200, 235)) if (k + int(x)) % 2 else _ramp((230, 50, 180))
        fig.poly([(cx - 3, base), (cx + 3, base), (cx + 1, base - hgt), (cx - 1, base - hgt + 1)], rmp)
    fig.sphere(x + 10, base - 3, 7, 4, ramp=HAZE)
P2 = 560
L2 = periodic_layer(P2, GY + 6, [(x, crystals) for x in range(30, P2, 70)], 2, FG_PAL)                                 # 0.6x bush/crystal row
FGD = [(10, 6, 20), (22, 12, 38), (36, 22, 58), (52, 34, 80), (70, 50, 104), (90, 70, 130)]
def pillar(fig, x):
    if int(x) % 3 == 0:
        fig.capsule((x, H + 4), (x + 3, 120), 8, FGD); fig.capsule((x + 3, 124), (x + 30, 96), 3, FGD)  # trunk + branch
    else:
        for k in range(4): fig.poly([(x + k * 6 - 9, H + 2), (x + k * 6 - 4, H + 2), (x + k * 6 - 6, H - 16 - k * 5 % 11)], FGD if k % 2 else _ramp((50, 20, 80)))
P4 = 900
L4 = periodic_layer(P4, H, [(x, pillar) for x in (40, 470, 702)], 3, FG_PAL)  # placed so no pillar covers a fight (fight cams 28/56/84 px)                                        # 1.4x foreground
for i, L in enumerate([L0, L1, L2, L3, L4]): L.save(os.path.join(OUT, f'forest-L{i}.png'))
json.dump({'ground': {'kingdom': 200, 'forest': 204, 'lair': 222, 'hall': 228},
           'depth_rows': {'hall': [184, 186, 190, 192, 196, 198, 204, 206, 214], 'kingdom': [190, 196, 206]},  # back-row floor lines for crowds (perspective floors)
           'forest_layers': [{'img': f'forest-L{i}.png', 'speed': sp, 'y': y} for i, (sp, y) in enumerate([(0.1, 0), (0.3, 0), (0.6, 0), (1.0, GY), (1.4, 0)])]},
          open(os.path.join(OUT, 'world.json'), 'w'), indent=1)

# ---------- contact sheet (x4, nearest, labelled) ----------
sheet_rows = []
for name, m in meta.items():
    fr = [atlas[y:y + h, x:x + w] for x, y, w, h in m['frames']]
    strip = np.concatenate([np.pad(f, ((0, 0), (0, 2), (0, 0))) for f in fr], 1)
    sheet_rows.append((name, strip))
SW = max(s.shape[1] for _, s in sheet_rows) + 60
SH = sum(s.shape[0] + 4 for _, s in sheet_rows)
cs = Image.new('RGB', (SW, SH), (60, 40, 90)); dd = ImageDraw.Draw(cs); y = 0
for name, s in sheet_rows:
    cs.paste(Image.fromarray(s, 'RGBA'), (60, y), Image.fromarray(s, 'RGBA'))
    dd.text((2, y + 2), name, fill=(255, 255, 255)); y += s.shape[0] + 4
cs = cs.resize((SW * 3, SH * 3), Image.NEAREST)
os.makedirs(os.path.join(ROOT, 'out/kingdom-come-16bit'), exist_ok=True)
cs.save(os.path.join(ROOT, 'out/kingdom-come-16bit/sprites.png'))
print('ok', {k: (v['w'], v['h'], len(v['frames'])) for k, v in meta.items()})

# ---------- bitmap font (Press Start 2P rendered 1-bit at 8 px; ASCII 32..126 in one row) ----------
from PIL import ImageFont
FONT = os.path.join(ROOT, 'channels/progressiveslop/assets/kingdom-come-16bit/fonts/PressStart2P-Regular.ttf')
fnt = ImageFont.truetype(FONT, 8)
glyphs = Image.new('L', (8 * 95, 8), 0); gd = ImageDraw.Draw(glyphs)
gd.fontmode = '1'
for i, c in enumerate(range(32, 127)):
    gd.text((i * 8, 0), chr(c), font=fnt, fill=255)
g = np.asarray(glyphs) > 127
Image.fromarray(np.dstack([np.full(g.shape + (3,), 255, np.uint8), (g * 255).astype(np.uint8)]), 'RGBA').save(os.path.join(OUT, 'font8.png'))
print('font ok')

"""v2 sprites: side-view walk rigs, combat frames, enemies (knights + robot animals).
Exec'd by build_assets.py (shares its namespace: np, Image, ImageDraw, pixel_sprites helpers, anims, SRC).
Also runnable alone for previews: python3 shots/kingdom-come-16bit/sprites_v2.py --preview <dir>"""
import math, colorsys

V2_KEY_THRESH = 110

def seg_sheet(path, expect):
    """Auto-segment a reference sheet: row bands from the row coverage, frames from column gaps;
    a band with fewer segments than expected gets its widest segment split at the coverage minimum."""
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    key = np.median(a[:5].reshape(-1, 3), 0)
    m = np.sqrt(((a - key) ** 2).sum(2)) > V2_KEY_THRESH
    rp = m.sum(1); bands = []; s = None
    for y, v in enumerate(rp):
        if v > 3 and s is None: s = y
        if v <= 3 and s is not None:
            if y - s > 20: bands.append((s, y))
            s = None
    if s is not None: bands.append((s, len(rp)))
    rows = []
    for (y0, y1), n in zip(bands, expect):
        cp = m[y0:y1].sum(0); segs = []; s = None
        for x, v in enumerate(cp):
            if v > 1 and s is None: s = x
            if v <= 1 and s is not None:
                if x - s > 6: segs.append([s, x])
                s = None
        if s is not None: segs.append([s, len(cp)])
        while len(segs) < n:
            i = max(range(len(segs)), key=lambda k: segs[k][1] - segs[k][0]); x0, x1 = segs[i]
            c = np.convolve(cp[x0:x1].astype(float), np.ones(9) / 9, 'same'); q = (x1 - x0) // 4
            cut = x0 + q + int(np.argmin(c[q:-q])); segs[i:i + 1] = [[x0, cut], [cut, x1]]
        rows.append((y0, y1, segs))
    return a, key, rows

def key_crop(a, key, y0, y1, x0, x1, erode=2):
    c = a[y0:y1, x0:x1]
    d = np.sqrt(((c - key) ** 2).sum(2))
    al = d > V2_KEY_THRESH
    for _ in range(erode):
        e = al.copy(); e[1:] &= al[:-1]; e[:-1] &= al[1:]; e[:, 1:] &= al[:, :-1]; e[:, :-1] &= al[:, 1:]; al = e
    # despill: pull pixels that still lean toward the key colour back to neutral
    # only the matte edge (2 px band) is despilled, so purple cloaks / crimson gowns keep their colour
    edge = al.copy()
    for _ in range(3):
        e = edge.copy(); e[1:] &= edge[:-1]; e[:-1] &= edge[1:]; e[:, 1:] &= edge[:, :-1]; e[:, :-1] &= edge[:, 1:]; edge = e
    band = al & ~edge
    rgb = c.astype(float); lean = (np.clip((230 - d) / 120, 0, 1) * band)[..., None]
    grey = rgb.mean(-1, keepdims=True)
    rgb = rgb * (1 - lean * 0.85) + grey * lean * 0.85
    out = np.dstack([np.clip(rgb, 0, 255), al * 255]).astype(np.uint8)
    ys, xs = np.where(al)
    return out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def kill_fringe(f, key=(246, 0, 125), dist=90):
    """Remove edge pixels close to the key colour (after downscale)."""
    al = f[..., 3] > 0
    n = np.zeros_like(al); n[1:] |= ~al[:-1]; n[:-1] |= ~al[1:]; n[:, 1:] |= ~al[:, :-1]; n[:, :-1] |= ~al[:, 1:]
    d = np.sqrt(((f[..., :3].astype(int) - np.array(key)) ** 2).sum(-1))
    out = f.copy(); out[al & n & (d < dist)] = 0
    return out

HERO_SHEET = os.path.join(SRC, 'heroes-walk-combat-ref.jpg')
ENEMY_SHEET = os.path.join(SRC, 'enemies-combat-ref.jpg')
ha, hkey, hrows = seg_sheet(HERO_SHEET, [8, 8, 6, 6])
ea, ekey, erows = seg_sheet(ENEMY_SHEET, [6, 6, 6, 8])
def ref(a, key, rows, r, i, scale):
    y0, y1, segs = rows[r]; x0, x1 = segs[i]
    return kill_fringe(downscale(key_crop(a, key, y0, y1, x0, x1), scale))

HSC = 0.40   # hero side-view frames -> ~61 px tall (matches the front-view heroes)
ESC = 0.40
raw_h = {r: [ref(ha, hkey, hrows, r, i, HSC) for i in range(len(hrows[r][2]))] for r in range(4)}
raw_e = {r: [ref(ea, ekey, erows, r, i, ESC) for i in range(len(erows[r][2]))] for r in range(4)}
pal2 = build_palette([f for d in (raw_h, raw_e) for r in d.values() for f in r], n=40,
                     fixed=[CYAN, GOLD, RED, (250, 250, 255), (255, 63, 210), (18, 6, 36)])
Q = lambda f: despeckle(quantize(f, pal2), 6)

# ---------------- walk rig ----------------
# 8-frame cycle: 0 contact(A front) 1 down 2 pass 3 up 4 contact(B front) 5 down 6 pass 7 up.
# Each foot: stance = 4 frames sliding back S/4 px per frame (planted on the ground while the world
# scrolls S/4 per frame), swing = 4 frames forward with lift. Hip bob 0,+1,0,-1.
BOB = [0, 1, 0, -1, 0, 1, 0, -1]
def foot_path(i, S, lift):
    p = (i % 8) / 8
    if p < 0.5: return S / 2 - S * (p / 0.5), 0          # stance: front -> back
    q = (p - 0.5) / 0.5
    return -S / 2 + S * q, -lift * math.sin(math.pi * q)  # swing: back -> front, lifted

def ik(hx, hy, fx, fy, L1, L2, fwd=1):
    dx, dy = fx - hx, fy - hy; d = min(math.hypot(dx, dy), L1 + L2 - 0.01)
    a = math.atan2(dy, dx); c = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    b = math.acos(max(-1, min(1, c)))
    ka = a - b * fwd  # knee bends toward facing direction
    return hx + L1 * math.cos(ka), hy + L1 * math.sin(ka)

def seg(d, p0, p1, w, cols):
    """Shaded armour segment: dark core, mid fill, 1 px highlight on the light side."""
    dark, mid, hi = cols
    d.line([p0, p1], fill=dark, width=w + 2)
    d.line([p0, p1], fill=mid, width=w)
    ox = -1 if p1[1] >= p0[1] else 1
    d.line([(p0[0] + ox * (w // 2 - 1), p0[1]), (p1[0] + ox * (w // 2 - 1), p1[1])], fill=hi, width=1)

LEG_FRONT = ((52, 54, 78), (150, 156, 184), (226, 232, 250))
LEG_BACK = ((34, 32, 52), (96, 100, 128), (150, 156, 184))
def draw_leg(d, hip, foot, L1, L2, w, cols, face=1, boot=(7, 3), heel=False):
    kx, ky = ik(hip[0], hip[1], foot[0], foot[1], L1, L2, face)
    seg(d, hip, (kx, ky), w, cols); seg(d, (kx, ky), foot, w - 1, cols)
    d.ellipse([kx - 2, ky - 2, kx + 2, ky + 2], fill=cols[1]); d.point([(kx - 1 * face, ky - 1)], fill=cols[2])
    bl, bh = boot; fx, fy = foot
    pts = [(fx - 2 * face, fy - bh), (fx + (bl - 2) * face, fy - 1), (fx + (bl - 2) * face, fy), (fx - 3 * face, fy)]
    d.polygon(pts, fill=cols[1], outline=cols[0])
    if heel: d.line([(fx - 2 * face, fy), (fx - 2 * face, fy + 0)], fill=cols[0])

def compose(w, h, layers):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for L in layers:
        if callable(L): L(ImageDraw.Draw(im))
        else:
            arr, (x, y) = L; im.alpha_composite(Image.fromarray(arr, 'RGBA'), (int(x), int(y)))
    return np.asarray(im).copy()

def hue_mask(f, ranges, min_sat=0.25):
    h, s_, v = hsv(f); m = np.zeros(h.shape, bool)
    for lo, hi in ranges: m |= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
    return m & (s_ > min_sat) & (f[..., 3] > 0)

def cut_rows(f, y0, y1):
    o = f.copy(); o[:y0] = 0; o[y1:] = 0; return o

from pixel_robots import Painter, leg as rleg, walk_foot, BOB8, CHROME, DARKCHROME, ramp_of, ik as rik
from scipy.ndimage import distance_transform_edt

def hires(sheet_a, key, rows, r, i):
    y0, y1, segs = rows[r]; x0, x1 = segs[i]
    return key_crop(sheet_a, key, y0, y1, x0, x1)

def mask_hsv(f, sat_min=None, sat_max=None, hues=None, vmax=None):
    h, s_, v = hsv(f); m = f[..., 3] > 0
    if sat_min is not None: m &= s_ >= sat_min
    if sat_max is not None: m &= s_ < sat_max
    if vmax is not None: m &= v < vmax
    if hues:
        hm = np.zeros(h.shape, bool)
        for lo, hi in hues: hm |= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
        m &= hm
    return m

def fill_holes_rows(f, keep):
    """Fill pixels between the leftmost and rightmost kept pixel of every row with the nearest kept colour."""
    out = f.copy(); out[~keep] = 0
    span = np.zeros_like(keep)
    for y in range(keep.shape[0]):
        xs = np.where(keep[y])[0]
        if len(xs) > 1: span[y, xs.min():xs.max() + 1] = True
    hole = span & ~keep
    if hole.any():   # diffusion fill: holes take the average of their filled neighbours (smooth, no stripes)
        from scipy.ndimage import convolve
        rgb = out[..., :3].astype(float); known = keep.astype(float)
        k = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], float)
        for _ in range(60):
            num = np.dstack([convolve(rgb[..., c] * known, k, mode='nearest') for c in range(3)])
            den = convolve(known, k, mode='nearest')[..., None]
            new = (den[..., 0] > 0) & hole & (known == 0)
            if not new.any(): break
            rgb[new] = num[new] / den[new]; known[new] = 1
        out[..., :3] = np.where(hole[..., None], rgb, out[..., :3]).astype(np.uint8); out[hole, 3] = 255
    return out

SWORD = [(40, 40, 64), (120, 126, 156), (200, 206, 228), (246, 248, 255)]
def walk_uno(n=8, S=14.0):
    hr = hires(ha, hkey, hrows, 0, 0); Hh, Wh = hr.shape[:2]; K = 1 / HSC
    Hf, Wf = Hh * HSC, Wh * HSC
    hip_hi = int(Hh * 0.60)
    upper = hr.copy(); upper[hip_hi:] = 0
    # keep the silver torso down to the hip but drop the ref legs/sword (low saturation) below the belt line
    cloak = hr.copy(); cloak[:hip_hi - 6] = 0
    cm = mask_hsv(cloak, sat_min=0.22, hues=CLOAK); cloak[~cm] = 0
    xs = np.where(hr[hip_hi - 4, :, 3] > 0)[0]; hip_x = (np.median(xs) / K) + 1.5
    frames = []
    for i in range(n):
        bob = BOB8[i % 8]; sway = round(math.sin(2 * math.pi * i / n) * 1.5)
        pad = 8; fig = Painter(Wf + pad * 2, Hf + 3, K=K)
        ground = Hf + 2; hip = (hip_x + pad, Hf * 0.60 + bob + 0.5)
        L = (ground - 1.2 - hip[1] + bob) / 2 * 1.04
        fa = walk_foot(i, n, S, 3.5); fb = walk_foot(i + n // 2, n, S, 3.5)
        A = (hip[0] + fa[0], ground - 1.2 + fa[1]); B = (hip[0] - 1 + fb[0], ground - 1.2 + fb[1])
        # cloak tail (secondary motion: swings opposite the stride, 1-2 px)
        c = Image.fromarray(shift_rows(cloak, 0, Hh, dx=int(sway * K)), 'RGBA')
        fig.im.alpha_composite(c, (int(pad * K), int(bob * K)))
        rleg(fig, (hip[0] - 1, hip[1]), B, L, L, 2.9, 1, DARKCHROME)
        fig.im.alpha_composite(Image.fromarray(upper, 'RGBA'), (int(pad * K), int(bob * K)))
        hx, hy = hip[0] - 5, hip[1] - 4    # sword hand; blade angled down-back, swings with the arm
        tip = (hx - 9 + sway, hy + 16)
        fig.capsule((hx, hy), tip, 0.9, SWORD); fig.line((hx - 2, hy - 1.5), (hx + 2, hy + 1.5), GOLD, 1.2)
        rleg(fig, hip, A, L, L, 3.2, 1, CHROME)
        frames.append(fig.finish(pal2))
    return frames, S

def walk_aura(n=8, S=12.0):
    hr = hires(ha, hkey, hrows, 1, 0); Hh, Wh = hr.shape[:2]; K = 1 / HSC
    Hf, Wf = Hh * HSC, Wh * HSC
    waist = int(Hh * 0.40); hem = int(Hh * 0.90)
    upper = hr.copy(); upper[int(Hh * 0.53):] = 0
    g = hr.copy(); g[:waist] = 0; g[hem:] = 0
    keep = mask_hsv(g, sat_min=0.25)
    gown = fill_holes_rows(g, keep)   # the slit leg is painted over with gown; legs are rigged separately
    xs = np.where(hr[waist, :, 3] > 0)[0]; hip_x = np.median(xs) / K
    top_xs = np.where(hr[: int(Hh * 0.15), :, 3].any(0))[0]; head_cx = top_xs.mean()
    hv = hsv(upper)
    hair_m = (upper[..., 3] > 0) & (np.arange(Wh)[None, :] < head_cx - 4) & (np.arange(Hh)[:, None] > Hh * 0.08) & ((hv[2] < 0.42) | ((hv[1] > 0.4) & ((hv[0] > 330) | (hv[0] < 20))))
    frames = []
    for i in range(n):
        bob = BOB8[i % 8]; ph = 2 * math.pi * i / n
        pad = 8; fig = Painter(Wf + pad * 2, Hf + 3, K=K)
        ground = Hf + 2; hip = (hip_x + pad + 1, Hf * 0.46 + bob)
        L = (ground - 1.0 - hip[1] + bob) / 2 * 1.03
        fa = walk_foot(i, n, S, 3.0); fb = walk_foot(i + n // 2, n, S, 3.0)
        A = (hip[0] + fa[0], ground - 1.0 + fa[1]); B = (hip[0] - 1 + fb[0], ground - 1.0 + fb[1])
        rleg(fig, (hip[0] - 1, hip[1]), B, L, L, 1.6, 1, DARKCHROME, boot=3.5)
        # gown: hem swings with the stride (rows below the knee shear by up to 2 px), hair streams
        gw = gown.copy(); top = int(Hh * 0.70)
        for fy in range(int(top / K), int(hem / K) + 1):   # shear whole final-pixel rows by whole pixels (no streaks)
            y0, y1 = int(fy * K), int((fy + 1) * K)
            k = (y0 - top) / max(1, hem - top); dxf = int(round(math.sin(ph + 0.6) * 1.6 * k))
            if dxf: gw = shift_rows(gw, y0, y1, dx=int(dxf * K))
        rleg(fig, hip, A, L, L, 1.8, 1, CHROME, boot=3.5)   # both legs behind the gown; boots show below the hem
        fig.im.alpha_composite(Image.fromarray(gw, 'RGBA'), (int(pad * K), int(bob * K)))
        # hair streams back 1 px on the up-beat: move only the hair pixels behind the head (no row tearing)
        u = upper.copy()
        if math.sin(ph) > 0.3:
            hm = hair_m.copy(); moved = np.zeros_like(u); moved[:, :-int(K)][hm[:, int(K):]] = u[:, int(K):][hm[:, int(K):]]
            u[hm] = 0; m2 = moved[..., 3] > 0; u[m2] = moved[m2]
        fig.im.alpha_composite(Image.fromarray(u, 'RGBA'), (int(pad * K), int(bob * K)))
        frames.append(fig.finish(pal2))
    return frames, S

uw, US = walk_uno(); aw, AS = walk_aura()
anims['uno_walk'] = {'fps': 9, 'frames': uw, 'stride': US}
anims['aura_walk'] = {'fps': 9, 'frames': aw, 'stride': AS}

# ---------------- combat frames from the reference sheets (feet-anchored in pack) ----------------
def R2(r, i, flipx=False):
    f = outline(Q(raw_h[r][i])); return flip(f) if flipx else f
def E2(r, i, sc=None):
    return outline(Q(raw_e[r][i] if sc is None else ref(ea, ekey, erows, r, i, sc)))
anims['uno_ready'] = {'fps': 6, 'frames': [R2(2, 0), shift_rows(R2(2, 0), 0, 30, dy=1)]}
anims['uno_roll'] = {'fps': 10, 'frames': [R2(2, 1)]}
anims['uno_recoil'] = {'fps': 10, 'frames': [R2(2, 2)]}
anims['uno_side'] = {'fps': 4, 'frames': [R2(2, 3), shift_rows(R2(2, 3), 0, 28, dy=1)]}
anims['uno_counter'] = {'fps': 12, 'frames': [R2(2, 0), R2(2, 4), R2(2, 5), R2(2, 5)]}
anims['aura_hop'] = {'fps': 8, 'frames': [R2(3, 0)], 'air': True}
anims['aura_shield'] = {'fps': 8, 'frames': [R2(3, 1)]}
anims['aura_recoil'] = {'fps': 10, 'frames': [R2(3, 2)]}
anims['aura_bolt'] = {'fps': 10, 'frames': [R2(3, 3), R2(3, 4), R2(3, 5), R2(3, 5)]}

# knight: march rigged from the reference body (legs rebuilt), thrust/hit/down/dissolve from the sheet
def walk_knight(n=8, S=12.0):
    hr = hires(ea, ekey, erows, 0, 0); Hh, Wh = hr.shape[:2]; K = 1 / ESC
    Hf, Wf = Hh * ESC, Wh * ESC; hip_hi = int(Hh * 0.62)
    upper = hr.copy(); upper[hip_hi:] = 0
    # the spear shaft runs below the hips: keep its pixels (thin vertical run at the spear column)
    cols = np.where(hr[int(Hh * 0.3), :, 3] > 0)[0]; spear_x = int(cols.min())
    shaft = hr.copy(); shaft[:hip_hi] = 0; shaft[:, :max(0, spear_x - 4)] = 0; shaft[:, spear_x + 8:] = 0
    xs = np.where(hr[hip_hi - 4, :, 3] > 0)[0]; hip_x = np.median(xs) / K
    frames = []
    for i in range(n):
        bob = BOB8[i % 8]; pad = 8
        fig = Painter(Wf + pad * 2, Hf + 3, K=K)
        ground = Hf + 2; hip = (hip_x + pad, Hf * 0.62 + bob)
        L = (ground - 1.2 - hip[1] + bob) / 2 * 1.04
        fa = walk_foot(i, n, S, 3.0); fb = walk_foot(i + n // 2, n, S, 3.0)
        # facing left: forward is -x
        A = (hip[0] - fa[0], ground - 1.2 + fa[1]); B = (hip[0] + 1 - fb[0], ground - 1.2 + fb[1])
        rleg(fig, (hip[0] + 1, hip[1]), B, L, L, 2.7, -1, DARKCHROME)
        fig.im.alpha_composite(Image.fromarray(shaft, 'RGBA'), (int(pad * K), int(bob * K)))
        fig.im.alpha_composite(Image.fromarray(upper, 'RGBA'), (int(pad * K), int(bob * K)))
        rleg(fig, hip, A, L, L, 3.0, -1, CHROME)
        frames.append(fig.finish(pal2))
    return frames, S
kw, KS = walk_knight()
anims['knight_march'] = {'fps': 9, 'frames': kw, 'stride': KS, 'enemy': True}
anims['knight_idle'] = {'fps': 4, 'frames': [E2(0, 0), shift_rows(E2(0, 0), 0, 30, dy=1)], 'enemy': True}
anims['knight_telegraph'] = {'fps': 6, 'frames': [E2(1, 0)], 'enemy': True}
anims['knight_attack'] = {'fps': 10, 'frames': [E2(1, 1), E2(1, 2)], 'enemy': True}
anims['knight_hit'] = {'fps': 10, 'frames': [E2(1, 3)], 'enemy': True}
anims['knight_down'] = {'fps': 10, 'frames': [E2(1, 4)], 'enemy': True}
anims['knight_dissolve'] = {'fps': 10, 'frames': [E2(1, 5)], 'enemy': True}
# boss (hovering): idle bob, cast, slam, summon, hurt, kneel
bi = E2(2, 0, 0.56)
anims['boss_idle'] = {'fps': 6, 'frames': [bi, shift_rows(bi, 0, int(bi.shape[0] * 0.5), dy=1)], 'air': True, 'enemy': True}
anims['boss_telegraph'] = {'fps': 6, 'frames': [E2(2, 1, 0.56)], 'air': True, 'enemy': True}
anims['boss_slam'] = {'fps': 8, 'frames': [E2(2, 2, 0.56)], 'air': True, 'enemy': True}
anims['boss_summon'] = {'fps': 6, 'frames': [E2(2, 3, 0.56)], 'air': True, 'enemy': True}
anims['boss_hurt'] = {'fps': 8, 'frames': [E2(2, 4, 0.56)], 'air': True, 'enemy': True}
anims['boss_kneel'] = {'fps': 8, 'frames': [E2(2, 5, 0.56)], 'enemy': True}
anims['boss_attack'] = anims['boss_slam']
anims['orb'] = {'fps': 12, 'frames': [E2(3, i, 0.3) for i in range(4)], 'air': True}
anims['shockwave'] = {'fps': 10, 'frames': [E2(3, i) for i in range(4, 8)]}

# ---------------- unique NPC friends (painted, NOT hero recolours) ----------------
P_PUR = ramp_of((110, 60, 200)); P_MAG = ramp_of((230, 50, 180)); P_CYA = ramp_of((60, 200, 235)); P_GLD = ramp_of((220, 170, 60))
P_TEAL = ramp_of((40, 160, 150)); P_ORG = ramp_of((230, 120, 50))
pal2 = np.concatenate([pal2, np.array([c for r in (P_PUR, P_MAG, P_CYA, P_GLD, P_TEAL) for c in r[1:5]])])
def BigPainter(W, H, sc):
    f = Painter(W * sc, H * sc, K=3); f.K = 3 * sc; return f

def head(fig, kind, cx, cy, s, face=1, led=CYAN):
    """dome / square / visor / antenna heads, always red eyes + headphone cup."""
    if kind == 'dome':
        fig.sphere(cx, cy, 4.6 * s, 4.4 * s)
        fig.eye(cx + 2.0 * s * face, cy, 0.9 * s)
    elif kind == 'square':
        fig.box(cx - 4.5 * s, cy - 4.2 * s, cx + 4.5 * s, cy + 4.0 * s)
        fig.flat([(cx - 3 * s, cy - 0.6 * s), (cx + 4 * s, cy - 0.6 * s), (cx + 4 * s, cy + 1.2 * s), (cx - 3 * s, cy + 1.2 * s)], (30, 20, 40))
        fig.eye(cx + 2.4 * s * face, cy + 0.3 * s, 0.8 * s); fig.eye(cx - 0.6 * s * face, cy + 0.3 * s, 0.7 * s)
    elif kind == 'visor':
        fig.sphere(cx, cy, 4.2 * s, 4.8 * s)
        fig.flat([(cx - 1 * s, cy - 1.2 * s), (cx + 4.6 * s * face, cy - 1.0 * s), (cx + 4.4 * s * face, cy + 1.0 * s), (cx - 1 * s, cy + 1.0 * s)], (120, 0, 20))
        fig.line((cx + 0.5 * s, cy), (cx + 4 * s * face, cy), (255, 60, 70), 0.6 * s)
    elif kind == 'antenna':
        fig.box(cx - 3.8 * s, cy - 3.6 * s, cx + 3.8 * s, cy + 4.2 * s)
        fig.line((cx, cy - 3.6 * s), (cx, cy - 8 * s), (150, 156, 184), 0.5 * s); fig.sphere(cx, cy - 8.4 * s, 1.1 * s, ramp=P_MAG)
        fig.eye(cx + 1.8 * s * face, cy, 0.9 * s)
    fig.phones(cx - 1.2 * s * face, cy + 0.2 * s, 2.0 * s, led=led)

def body_type(fig, kind, cx, top, s, outfit, frame=0, arms=(0.6, 0.6), legs=True, ground=None, face=1):
    """round / boxy / lanky torsos with outfits; arms given as angles (0=down, 1=up), simple leg pair."""
    if kind == 'round':
        tw, th = 6.0 * s, 7.0 * s
        fig.sphere(cx, top + th * 0.55, tw, th * 0.62, ramp=outfit)
        fig.line((cx - tw * 0.8, top + th * 0.62), (cx + tw * 0.8, top + th * 0.62), GOLD, 0.6 * s)
    elif kind == 'boxy':
        tw, th = 5.6 * s, 8.0 * s
        fig.box(cx - tw, top, cx + tw, top + th)
        fig.box(cx - tw * 0.6, top + th * 0.25, cx + tw * 0.6, top + th * 0.7, ramp=outfit)
    else:  # lanky
        tw, th = 3.6 * s, 10.0 * s
        fig.poly([(cx - tw, top), (cx + tw, top), (cx + tw * 0.8, top + th), (cx - tw * 0.8, top + th)])
        fig.poly([(cx - tw * 0.4, top + 1), (cx + tw * 0.9, top + 1), (cx + tw * 0.6, top + th * 0.7), (cx - tw * 0.2, top + th * 0.7)], outfit)
    sh = top + 1.5 * s
    for side, a in ((-1, arms[0]), (1, arms[1])):
        ang = math.pi / 2 - a * math.pi * 0.95
        ex = cx + side * (tw + 0.5 * s) + side * math.cos(ang) * 4.2 * s * 0.4; ey = sh + math.sin(ang) * 4.2 * s
        hx = ex + side * math.cos(ang) * 1.2 * s; hy = ey + math.sin(ang) * 3.4 * s
        fig.capsule((cx + side * (tw - 0.5 * s), sh), (ex, ey), 1.1 * s); fig.capsule((ex, ey), (hx, hy), 1.0 * s)
        fig.sphere(hx, hy, 1.2 * s, ramp=DARKCHROME)
    return top + th

def biped_frames(kind_head, kind_body, s, outfit, poses, H, W, legs_len, prop=None, outfit_robe=False, led=CYAN):
    out = []
    for k, (bob, arms, step) in enumerate(poses):
        fig = Painter(W, H)
        ground = H - 1; cx = W / 2
        hip_y = ground - legs_len + bob
        # legs (little march/step offsets)
        for side, (fx, lift) in ((-1, step[0]), (1, step[1])):
            fig.capsule((cx + side * 1.6 * s, hip_y), (cx + side * 1.8 * s + fx, ground - 1.2 - lift), 1.3 * s, DARKCHROME if side < 0 else CHROME)
            fig.poly([(cx + side * 1.8 * s + fx - 1.6 * s, ground - 2.2 * s - lift), (cx + side * 1.8 * s + fx + 1.8 * s, ground - 2.2 * s - lift), (cx + side * 1.8 * s + fx + 2.0 * s, ground - lift), (cx + side * 1.8 * s + fx - 1.8 * s, ground - lift)])
        th = {'round': 7.0, 'boxy': 8.0, 'lanky': 10.0}[kind_body] * s
        top = hip_y - th + 1
        if outfit_robe:
            fig.poly([(cx - 3.5 * s, top + 1), (cx + 3.5 * s, top + 1), (cx + 6.5 * s + bob * 0.5, ground - 3), (cx - 6.5 * s, ground - 3)], outfit)
        body_type(fig, kind_body, cx, top, s, outfit, k, arms)
        head(fig, kind_head, cx, top - 4.6 * s, s, led=led)
        if prop: prop(fig, cx, top, s, k, ground)
        out.append(fig.finish(pal2))
    return out

def wizard_hat_staff(fig, cx, top, s, k, ground):
    hy = top - 8.6 * s
    fig.poly([(cx - 6 * s, hy + 2), (cx + 6 * s, hy + 2), (cx + 1.5 * s, hy - 12 * s), (cx + 3.5 * s + [0, 0.6, 1, 0.6][k % 4], hy - 13 * s)], P_PUR)
    fig.line((cx - 6 * s, hy + 1.6), (cx + 6 * s, hy + 1.6), GOLD, 0.9)
    fig.sphere(cx + 1 * s, hy - 4 * s, 0.9 * s, ramp=P_GLD)
    sx = cx + 8.5 * s
    fig.capsule((sx, top - 4 * s), (sx, ground - 1), 0.7 * s, ramp=ramp_of((150, 100, 60)))
    fig.sphere(sx, top - 5.5 * s, 1.8 * s, ramp=[P_CYA, ramp_of((180, 250, 255)), P_CYA, ramp_of((40, 150, 220))][k % 4])
def jester_hat(fig, cx, top, s, k, ground):
    hy = top - 8.4 * s; w = [0, 0.8, 1.2, 0.8][k % 4]
    fig.poly([(cx - 4.5 * s, hy + 1.5 * s), (cx, hy - 0.5 * s), (cx - 9 * s, hy - 4 * s + w)], P_MAG)
    fig.poly([(cx + 4.5 * s, hy + 1.5 * s), (cx, hy - 0.5 * s), (cx + 9 * s, hy - 4 * s - w + 1)], P_CYA)
    fig.sphere(cx - 9.4 * s, hy - 4.4 * s + w, 1.1 * s, ramp=P_GLD); fig.sphere(cx + 9.4 * s, hy - 4.4 * s - w + 1, 1.1 * s, ramp=P_GLD)
    # diamond tunic pattern
    for j in range(3):
        fig.flat([(cx - 3 * s + j * 3 * s, top + 3 * s), (cx - 1.5 * s + j * 3 * s, top + 1.5 * s), (cx + j * 3 * s, top + 3 * s), (cx - 1.5 * s + j * 3 * s, top + 4.5 * s)], (60, 210, 240) if j % 2 else (230, 50, 180))

WIZ = [(0, (0.2, 0.55), ((0, 0), (0, 0))), (0, (0.2, 0.6), ((0, 0), (0, 0))), (1, (0.25, 0.65), ((0, 0), (0, 0))), (0, (0.2, 0.6), ((0, 0), (0, 0)))]
anims['wizard_idle'] = {'fps': 6, 'frames': biped_frames('dome', 'lanky', 2.1, P_PUR, WIZ, 64, 44, 15, wizard_hat_staff, outfit_robe=True)}
JST = [(0, (0.3, 0.3), ((0, 0), (0, 0))), (-2, (0.9, 0.4), ((-1, 1), (1, 0))), (-3, (1.0, 1.0), ((-1, 2), (1, 2))), (-1, (0.4, 0.9), ((0, 0), (1, 1)))]
anims['jester_hop'] = {'fps': 8, 'frames': biped_frames('square', 'round', 2.0, P_MAG, JST, 50, 46, 9, jester_hat)}

def crowd(design, outfit, led):
    D = [(0, (0.95, 0.95), ((0, 0), (0, 0))), (2, (0.6, 0.6), ((0, 0), (0, 0))), (0, (0.95, 0.2), ((-1, 1), (0, 0))), (2, (0.2, 0.95), ((0, 0), (1, 1)))]
    hk, bk, s, H, L = design
    return biped_frames(hk, bk, s, outfit, D, H, 40, L, led=led)
DESIGNS = [('antenna', 'boxy', 1.75, 50, 11), ('dome', 'round', 1.8, 42, 8), ('visor', 'lanky', 1.6, 52, 14)]
for v, (dz, outfit, led) in enumerate([(0, P_CYA, (255, 63, 210)), (1, P_MAG, (94, 231, 255)), (2, P_CYA, (255, 63, 210)), (0, P_PUR, (255, 220, 90)), (1, P_TEAL, (255, 63, 210)), (2, P_MAG, (255, 220, 90))]):
    anims[f'crowd{v}'] = {'fps': 4, 'frames': crowd(DESIGNS[dz], outfit, led)}

# ---------------- robot animals (painted at 3x, chrome, red eyes, headphone ears) ----------------
def wolf_frame(pose, k):
    """pose: run | telegraph | lunge | hit | down. Facing left."""
    W, H = 64, 40; fig = BigPainter(W, H, 1.45); g = H - 1; f = -1
    if pose == 'down':
        fig.capsule((18, g - 5), (44, g - 4), 5); fig.sphere(14, g - 6, 5, 4); fig.eye(11, g - 7, 1.0)
        for x in (22, 30, 38, 44): fig.capsule((x, g - 4), (x + 4, g - 1), 1.3)
        return fig.finish(pal2)
    lift = {'run': 0, 'telegraph': 4, 'lunge': -6, 'hit': 0}[pose]
    bx0, bx1 = (20, 46) if pose != 'lunge' else (16, 50)
    by = g - 15 + (lift if pose != 'lunge' else -4) + [0, 1, 0, -1, 0, 1][k % 6] * (pose == 'run')
    tilt = 3 if pose == 'telegraph' else (-2 if pose == 'lunge' else 0)
    # legs: trot (diagonal pairs) for run; tucked for lunge; crouched for telegraph
    for j, (lx, ph) in enumerate(((bx0 + 4, 0), (bx0 + 7, 0.5), (bx1 - 5, 0.5), (bx1 - 2, 0))):
        if pose == 'run':
            fx, fl = walk_foot(k + int(ph * 6), 6, 10, 3)
            foot = (lx - fx, g - 1 + fl)
        elif pose == 'lunge': foot = (lx - 8 if j < 2 else lx + 9, by + 7)
        else: foot = (lx + (2 if pose == 'telegraph' else 0), g - 1)
        hip = (lx, by + 3 + (tilt if j < 2 else 0))
        kx, ky = rik(hip[0], hip[1], foot[0], foot[1], 6.5, 7.5, -1 if j >= 2 else 1)
        rmp = DARKCHROME if j % 2 == 0 else CHROME
        fig.capsule(hip, (kx, ky), 2.4, rmp); fig.capsule((kx, ky), foot, 1.8, rmp); fig.sphere(foot[0] - 1, foot[1] - 0.5, 1.9, 1.3, ramp=rmp)
    fig.sphere(bx1 - 2, by, 6.5, 6.0)                            # haunch
    fig.capsule((bx0 + 2, by + tilt), (bx1 - 2, by), 6.0)        # torso
    fig.sphere(bx0 + 3, by + tilt - 1, 7.5, 7.0)                 # armoured chest
    fig.line((bx0 + 6, by - 5), (bx1 - 4, by - 5), (240, 244, 255), 0.6)
    fig.capsule((bx1, by - 1), (bx1 + 10, by - 6 - (k % 2)), 1.6)  # tail
    hx, hy = bx0 - 4, by - 5 + tilt
    fig.sphere(hx, hy, 5.2, 4.6)                                 # head
    fig.poly([(hx - 2, hy - 1), (hx - 12, hy + 1), (hx - 12, hy + 3.5), (hx - 2, hy + 4)])  # snout
    if pose in ('telegraph', 'lunge'): fig.poly([(hx - 3, hy + 4), (hx - 11, hy + 4), (hx - 9, hy + 7)], DARKCHROME)  # open jaw
    fig.eye(hx - 3, hy - 1, 1.3, col=(255, 230, 230) if pose == 'telegraph' and k % 2 else (255, 40, 60))
    fig.phones(hx + 2, hy - 2, 2.2, led=CYAN)
    return fig.finish(pal2)

def spider_frame(pose, k):
    W, H = 56, 36; fig = BigPainter(W, H, 2.0); g = H - 1
    up = {'walk': 0, 'telegraph': 6, 'attack': 2, 'hit': 0, 'down': -3}[pose]
    cx, cy = 30, g - 11 - (up if pose != 'down' else -3) - ((k % 2) if pose == 'walk' else 0)
    for j in range(4):                                  # 4 visible legs per side, alternating tetrapod gait
        for side, rmp in ((1, DARKCHROME), (-1, CHROME)):
            ph = (j % 2 == (0 if side > 0 else 1))
            phs = (k + (2 if ph else 0)) % 4                # 4-phase gait: plant, push, lift, swing
            base = (cx - 6 + j * 4, cy + 1)
            foot = (cx - 18 + j * 11 + [-3, -1, 2, 3][phs] * (pose == 'walk'), g - 1 - ([0, 0, 3, 1][phs] if pose == 'walk' else 0))
            if pose == 'telegraph' and j == 0: foot = (cx - 20, cy - 12)
            if pose == 'attack' and j == 0: foot = (cx - 26, cy - 2)
            if pose == 'down': foot = (cx - 20 + j * 12, g - 1)
            knee = ((base[0] + foot[0]) / 2, min(base[1], foot[1]) - 7)
            fig.capsule(base, knee, 1.7, rmp); fig.capsule(knee, foot, 1.3, rmp); fig.sphere(knee[0], knee[1], 1.5, ramp=rmp)
    fig.sphere(cx + 6, cy - 1, 9, 6.5)                  # abdomen
    fig.sphere(cx - 6, cy, 5.2, 4.4)                    # head
    fig.eye(cx - 9, cy - 1, 1.1, col=(255, 230, 230) if pose == 'telegraph' and k % 2 else (255, 40, 60)); fig.eye(cx - 6, cy - 2, 0.8)
    fig.phones(cx - 3, cy - 3, 1.8, led=(255, 63, 210))
    fig.line((cx - 10, cy + 3), (cx - 13 - (3 if pose == 'attack' else 0), cy + 6), (240, 240, 255), 0.7)   # fangs
    return fig.finish(pal2)

def bat_frame(pose, k):
    W, H = 48, 34; fig = BigPainter(W, H, 2.15); cx, cy = 24, 16
    flap = {'fly': [-10, -3, 5, 0][k % 4], 'telegraph': -12, 'attack': 6, 'hit': 2, 'down': 3}[pose]
    for side, rmp in ((1, DARKCHROME), (-1, DARKCHROME)):
        tip = (cx + side * 21, cy + flap); mid = (cx + side * 11, cy - 4 + flap * 0.5)
        fig.poly([(cx + side * 3, cy - 2), mid, tip, (cx + side * 15, cy + 4 + flap * 0.4), (cx + side * 8, cy + 6)], rmp)
        fig.capsule((cx + side * 3, cy - 2), mid, 0.9); fig.capsule(mid, tip, 0.7)
    fig.sphere(cx, cy + 1, 5, 6)
    fig.sphere(cx - 1, cy - 6, 4, 3.6)
    fig.eye(cx - 3, cy - 6, 0.9, col=(255, 230, 230) if pose == 'telegraph' and k % 2 else (255, 40, 60)); fig.eye(cx + 0.5, cy - 6, 0.8)
    fig.phones(cx + 2.5, cy - 7, 1.6, led=CYAN)
    if pose == 'attack': fig.poly([(cx - 3, cy + 7), (cx + 3, cy + 7), (cx, cy + 12)], CHROME)
    return fig.finish(pal2)

def serpent_frame(pose, k):
    """robot serpent-dragon rising from the lair floor, facing left."""
    W, H = 84, 76; fig = BigPainter(W, H, 1.2); g = H - 1
    rear = {'idle': 0, 'telegraph': 6, 'attack': -4, 'hit': 2, 'down': -20}[pose]
    pts = []
    for j in range(11):
        t = j / 10
        x = 66 - t * 30 + math.sin(t * 5 + k * 0.9) * 4 + (rear * t * 0.8)
        y = g - 6 - t * (50 + rear) - math.cos(t * 4 + k * 0.9) * 2
        if pose == 'down': y = g - 6 - t * 8; x = 70 - t * 50
        pts.append((x, y))
    for j in range(len(pts) - 1):
        fig.capsule(pts[j], pts[j + 1], 6.0 - j * 0.3, CHROME if j % 2 else ramp_of((150, 156, 190)))
        fig.poly([(pts[j][0] + 2, pts[j][1] - 5 + j * 0.2), (pts[j][0] + 5, pts[j][1] - 9), (pts[j][0] + 6, pts[j][1] - 4)], P_MAG)  # dorsal fins
    hx, hy = pts[-1]
    fig.sphere(hx - 2, hy, 6.5, 5.2)
    jaw = 5 if pose in ('telegraph', 'attack') else 1
    fig.poly([(hx - 4, hy - 2), (hx - 17, hy), (hx - 16, hy + 2), (hx - 4, hy + 2)])
    fig.poly([(hx - 4, hy + 2), (hx - 15, hy + 2 + jaw), (hx - 4, hy + 5)], DARKCHROME)
    fig.poly([(hx + 1, hy - 5), (hx + 8, hy - 13), (hx + 4, hy - 4)], DARKCHROME)   # horns
    fig.eye(hx - 5, hy - 2, 1.4, col=(255, 230, 230) if pose == 'telegraph' and k % 2 else (255, 40, 60))
    fig.phones(hx + 1, hy, 2.4, led=(255, 63, 210))
    if pose == 'telegraph':
        fig.sphere(hx - 15, hy + 3, 2.2, ramp=P_MAG)
    return fig.finish(pal2)

def fire_frame(k):
    W, H = 64, 18; fig = Painter(W, H)
    for j in range(7):
        x = 60 - j * 8 - (k % 2) * 3; r = 3 + j * 0.9 + (k + j) % 2
        fig.sphere(x, 9 + math.sin(j + k) * 2, r, r * 0.8, ramp=[P_MAG, ramp_of((255, 140, 230)), ramp_of((180, 40, 200))][(j + k) % 3])
    return fig.finish(pal2)

for name, fn, poses in (('wolf', wolf_frame, {'run': 6, 'telegraph': 2, 'lunge': 1, 'hit': 1, 'down': 1}),
                        ('spider', spider_frame, {'walk': 4, 'telegraph': 2, 'attack': 1, 'hit': 1, 'down': 1}),
                        ('bat', bat_frame, {'fly': 4, 'telegraph': 2, 'attack': 1, 'hit': 1, 'down': 1}),
                        ('serpent', serpent_frame, {'idle': 6, 'telegraph': 2, 'attack': 2, 'hit': 1, 'down': 1})):
    for pose, n in poses.items():
        nm = {'lunge': 'attack'}.get(pose, pose)
        anims[f'{name}_{nm}'] = {'fps': 10 if pose in ('run', 'walk') else 8, 'frames': [fn(pose, k) for k in range(n)], 'enemy': True,
                                 'air': name == 'bat' or (name == 'wolf' and pose == 'lunge')}
anims['wolf_run']['stride'] = 10
anims['fire'] = {'fps': 12, 'frames': [fire_frame(k) for k in range(2)], 'air': True}

"""v3 cut-out rigs: Uno / Aura / knight walk, wolf gallop + attack, spider, bat.
Ref parts (head, torso+pelvis, cloak, hair) come from walk-design-ref-v3 / animals-ref-v3 on #00FF00;
limbs are FK/IK chrome segments; each frame is composited at 4x and outlined once."""
import math, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from pixel_rig import RefParts, paste, walk_targets, chrome_leg, chrome_arm, rot, ang, hsv, knee_angle, K, key_green
from pixel_robots import Painter, CHROME, DARKCHROME, ramp_of
SRC = os.path.join(ROOT, 'channels/progressiveslop/assets/kingdom-come-16bit/source')
WREF = np.array(Image.open(os.path.join(SRC, 'walk-design-ref-v3.jpg')).convert('RGB'))
AREF = np.array(Image.open(os.path.join(SRC, 'animals-ref-v3.jpg')).convert('RGB'))
N = 8; STRIDE = 39.25; SCHED = [0.0, 6.75 / 39.25, 20.75 / 39.25, 35.0 / 39.25]  # step schedule shared with Uno's v4 walk;          # final px per step (one beat = 4 frames) == world scroll per beat
GOLDR = ramp_of((220, 170, 60)); CRIM = ramp_of((176, 22, 52)); SW = [(40, 40, 64), (120, 126, 156), (200, 206, 228), (246, 248, 255)]
RIG_LOG = {}                # per anim: list of per-frame joint angles (for QA)

def purple(a):
    h, s, v = hsv(a); return (h > 245) & (h < 330) & (s > 0.18) & (a[..., 3] > 0)
def notpurple(a): return ~purple(a)

# ---------------- Uno ----------------
U = RefParts(WREF, (472, 60, 640, 332), 67)
U_HEAD = U.cut([(78, 0), (128, 0), (130, 54), (96, 58), (78, 40)], notpurple)
U_TORSO = U.cut([(80, 46), (128, 46), (134, 72), (130, 120), (124, 140), (82, 140), (78, 100)], notpurple)
U_CLOAK = U.cut(None, purple)
U_HIP = U.P(102, 128); U_NECK = U.P(104, 52); U_SH = U.P(98, 64); U_SH2 = U.P(116, 62)

def uno_frame(i, pal, W=72, H=72):
    ox, gy = 16, H - 2                       # crop -> canvas offset; ground row
    T = walk_targets(N, STRIDE, 17.5, 16.5, gy, U_HIP[0] + ox, lift=5.5, bob_amp=1.0, dip=0.8)
    hip, fA, fB = T[i]; hipP = T[(i - 1) % N][0]
    dy = hip[1] - (U_HIP[1] + 6)             # pelvis offset vs ref pose
    phi = 2 * math.pi * i / N
    fig = Painter(W, H, K)
    off = lambda p, d=dy: (p[0] + ox, p[1] + d)
    tor_a = 1.6 * math.sin(phi * 2)          # slight counter-rotation each step
    # cloak: rides the shoulders, hem lags one frame behind the stride
    sway = 2.2 * math.cos(phi - 2 * math.pi / N) 
    paste(fig, U_CLOAK, U_SH, off(U_SH), tor_a * 0.5, shear=lambda r: sway * max(0, r - 0.25) ** 1.4)
    # far arm (behind torso) swings with near leg
    sh2 = off(U_SH2); a2 = 24 * math.cos(phi)
    chrome_arm(fig, sh2, a2, a2 + 22 + 14 * (1 + math.cos(phi)) / 2, 9.0, 8.5, 2.9, DARKCHROME)
    # far leg B
    kB = chrome_leg(fig, (hip[0] + 1.5, hip[1]), fB, 17.5, 16.5, 3.7, DARKCHROME)
    # torso + pelvis (one ref part), head lags one frame
    paste(fig, U_TORSO, U_HIP, (hip[0], hip[1] - 6), tor_a)
    neck = rot((hip[0], hip[1] - 6), 180 + tor_a, U_HIP[1] - U_NECK[1])
    paste(fig, U_HEAD, U_NECK, (neck[0] + (U_NECK[0] - U_HIP[0]), neck[1] + (hipP[1] - hip[1]) * 0.6), -tor_a * 0.5)
    # near leg A (in front) + hip cap overlapping the pelvis
    kA = chrome_leg(fig, hip, fA, 17.5, 16.5, 3.9, CHROME)
    # near arm + sword (arm swings opposite the near leg)
    sh = off(U_SH); a1 = -24 * math.cos(phi)
    el, wr = chrome_arm(fig, sh, a1, a1 + 20 + 16 * (1 - math.cos(phi)) / 2, 9.0, 8.5, 3.1, CHROME)
    sa = 24 + a1 * 0.35; tip = rot(wr, sa, 24); pommel = rot(wr, sa + 180, 3)
    fig.capsule(pommel, tip, 0.8, SW); fig.line(rot(wr, sa + 90, 2.6), rot(wr, sa - 90, 2.6), GOLDR[3], 1.1)
    fig.sphere(wr[0], wr[1], 1.6)
    RIG_LOG.setdefault('uno_walk', []).append({'hipA': ang(hip, kA), 'hipB': ang(hip, kB), 'kneeA': knee_angle(hip, kA, fA), 'kneeB': knee_angle(hip, kB, fB), 'liftA': gy - fA[1], 'liftB': gy - fB[1], 'arm': a1, 'pelvis_y': hip[1], 'torso_pivot': (hip[0], hip[1] - 6)})
    return fig.finish(pal)

# ---------------- Aura ----------------
A = RefParts(WREF, (492, 380, 640, 642), 65)
def _aura_upper(a):
    h, s, v = hsv(a); yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]] / A.s
    grey = s < 0.22
    arm = grey & (xx < 76) & (yy > 56)       # ref arm pixels -> rebuilt by the rig
    return ~arm
A_HEAD = A.cut([(64, -2), (116, -2), (116, 56), (90, 62), (72, 58), (66, 30)], _aura_upper)
A_HAIR = A.cut([(8, 0), (72, 0), (72, 100), (8, 100)])
A_BOD = A.cut([(66, 52), (110, 54), (112, 78), (106, 104), (70, 104), (64, 80)], _aura_upper)
A_HIP = A.P(88, 112); A_SH = A.P(74, 64); A_SH2 = A.P(98, 62)

def aura_frame(i, pal, W=72, H=72):
    ox, gy = 18, H - 2
    T = walk_targets(N, STRIDE, 17.5, 16.8, gy, A_HIP[0] + ox, lift=5.0, bob_amp=1.0, dip=0.7, sched=SCHED)
    hip, fA, fB = T[i]; hipP = T[(i - 1) % N][0]
    dy = hip[1] - A_HIP[1]; phi = 2 * math.pi * i / N; off = lambda p: (p[0] + ox, p[1] + dy)
    fig = Painter(W, H, K); tor_a = 1.2 * math.sin(phi * 2)
    hs = 1.8 * math.cos(phi - 2 * math.pi / N)    # hair lags one frame
    paste(fig, A_HAIR, A_HIP, (hip[0], hip[1] + (hipP[1] - hip[1]) * 0.8), 0, shear=lambda r: -hs * (1 - r) * 0.8)
    sh2 = off(A_SH2); a2 = 22 * math.cos(phi)
    chrome_arm(fig, sh2, a2, a2 + 18 + 12 * (1 + math.cos(phi)) / 2, 8.6, 8.2, 1.9, DARKCHROME)
    kB = chrome_leg(fig, (hip[0] + 1, hip[1] + 1), fB, 17.5, 16.8, 2.5, DARKCHROME)
    # gown: back panel behind the near leg, trailing hem
    wy = hip[1] - 2; hem = gy - 7; lag = 2.5 * math.cos(phi - 2 * math.pi / N)
    kA = chrome_leg(fig, hip, fA, 17.5, 16.8, 3.0, CHROME)
    # gown drawn OVER the near thigh: front edge runs waist -> front of the near knee (the slit), the
    # shin steps out below it; the hem trails behind with a one-frame lag
    lo = (kA[0] + (fA[0] - kA[0]) * 0.35, kA[1] + (fA[1] - kA[1]) * 0.35)
    slit_x = min(lo[0], kA[0]) - 2.5
    back = min(fB[0] - 4, hip[0] - 15) - lag
    pts = [(hip[0] - 6, wy), (hip[0] + 5, wy), (max(hip[0] + 6, kA[0] + 3), kA[1] - 2), (kA[0] + 1.5, kA[1] + 2.5), (slit_x, hem + 1)]
    for k in range(1, 7):
        t = k / 6; pts.append((slit_x + (back - slit_x) * t, hem + 1.5 + (1.0 if k % 2 else 0) - t * 0.6))
    pts += [(back - 1.5, hem - 3), (hip[0] - 10 - lag * 0.5, hip[1] + 9)]
    fig.poly(pts, [CRIM[0], CRIM[1], CRIM[2], CRIM[2], CRIM[2], CRIM[2]], shade=False)
    fig.flat([(hip[0] - 2, wy + 4), (hip[0] + 1, wy + 4), (slit_x - 3, hem), (back + 5, hem)], CRIM[1])   # fold shadow
    fig.line((hip[0] + 5, wy + 1), (kA[0] + 2.5, kA[1] - 1.5), GOLDR[3], 0.6); fig.line((kA[0] + 1.5, kA[1] + 2.5), (slit_x, hem + 1), GOLDR[3], 0.6)
    fig.line((slit_x, hem + 1.5), (back, hem + 0.9), GOLDR[2], 0.5)
    paste(fig, A_BOD, A_HIP, hip, tor_a)
    neck = (hip[0], hip[1] + (hipP[1] - hip[1]) * 0.6)
    paste(fig, A_HEAD, A_HIP, neck, -tor_a * 0.4)
    sh = off(A_SH); a1 = -22 * math.cos(phi)
    el, wr = chrome_arm(fig, sh, a1, a1 + 18 + 14 * (1 - math.cos(phi)) / 2, 8.6, 8.2, 2.1, CHROME)
    fig.sphere(wr[0], wr[1], 1.0, ramp=ramp_of((60, 200, 235)))   # cyan magic glint in the hand
    RIG_LOG.setdefault('aura_walk', []).append({'hipA': ang(hip, kA), 'hipB': ang(hip, kB), 'kneeA': knee_angle(hip, kA, fA), 'liftA': gy - fA[1], 'arm': a1})
    return fig.finish(pal)

def walk(fn, pal): RIG_LOG.pop(fn.__name__.replace('_frame', '_walk'), None); return [fn(i, pal) for i in range(N)]

if __name__ == '__main__':
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    from pixel_sprites import build_palette
    pal = build_palette([key_green(WREF[60:640]), key_green(AREF)], n=40, fixed=[(94, 231, 255), (220, 170, 60), (255, 40, 60), (250, 250, 255), (255, 63, 210), (18, 6, 36)])
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/rig'; os.makedirs(out, exist_ok=True)
    for nm, fn in (('uno', uno_frame), ('aura', aura_frame)):
        fr = walk(fn, pal)
        strip = np.concatenate([np.pad(f, ((0, 0), (0, 2), (0, 0))) for f in fr], 1)
        bg = np.zeros_like(strip); bg[...] = (40, 24, 70, 255); m = strip[..., 3:] > 0; comp = np.where(m, strip, bg)
        comp[-2, :, :3] = (255, 63, 210)
        Image.fromarray(comp).resize((comp.shape[1] * 4, comp.shape[0] * 4), Image.NEAREST).save(f'{out}/{nm}-strip.png')
        for r in RIG_LOG.get(nm + '_walk', []): print(nm, {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if k != 'torso_pivot'})

# ---------------- mirrored refs (enemies face left in the ref; rig them facing right, flip at the end)
def mref(sheet, box, final_h):
    Wd = sheet.shape[1]; x0, y0, x1, y1 = box
    return RefParts(sheet[:, ::-1], (Wd - x1, y0, Wd - x0, y1), final_h), (x1 - x0)
flipf = lambda f: f[:, ::-1].copy()

# ---------------- wolf: quadruped gallop with spine flex ----------------
WO, WW = mref(AREF, (0, 0, 240, 170), 60)
mx = lambda pts: [(WW - x, y) for x, y in pts]
WO_HEAD = WO.cut(mx([(22, 30), (90, 30), (92, 82), (78, 112), (24, 104)]))
WO_CHEST = WO.cut(mx([(70, 44), (132, 46), (134, 114), (76, 114), (70, 90)]))
WO_REAR = WO.cut(mx([(128, 48), (192, 50), (198, 108), (186, 114), (128, 114)]))
WO_TAIL = WO.cut(mx([(184, 48), (236, 44), (236, 96), (188, 100)]))
P_NECK = WO.P(WW - 84, 70); P_SPINE = WO.P(WW - 130, 80); P_TAILB = WO.P(WW - 190, 66)
P_SH = WO.P(WW - 98, 104); P_HIP = WO.P(WW - 168, 100)

def wolf_pose(pose, i, pal, W=96, H=60):
    n = 6; phi = 2 * math.pi * i / n
    ox, gy = 6, H - 2
    fig = Painter(W, H, K)
    # pose parameters
    if pose == 'run':
        bob = -2.0 * math.sin(phi); flex = 7 * math.sin(phi)         # + = chest pitched down (gathered)
        fr = [42 * math.sin(phi), 42 * math.sin(phi - 0.7)]        # front pair (near, far), deg forward
        hi = [-40 * math.sin(phi + 0.4), -40 * math.sin(phi - 0.3)]  # hind pair, opposite phase
        bend = lambda a, k: 25 + 45 * max(0, math.cos(phi + k))
        head_a = 5 * math.sin(phi + 0.8); tail_a = 14 * math.sin(phi + 1.4); drop = 0
    elif pose == 'telegraph':
        bob = 3 + i; flex = 10; fr = [-12, -18]; hi = [24, 18]; bend = lambda a, k: 70; head_a = 10; tail_a = -18 + 10 * i; drop = 0
    elif pose == 'attack':
        bob = -8; flex = -12; fr = [70, 60]; hi = [-62, -55]; bend = lambda a, k: 10; head_a = -14; tail_a = 22; drop = 0
    elif pose == 'hit':
        bob = -1; flex = -14; fr = [-30, -20]; hi = [10, 0]; bend = lambda a, k: 40; head_a = -24; tail_a = -24; drop = 0
    else:  # down
        bob = 12; flex = 0; fr = [80, 70]; hi = [-80, -70]; bend = lambda a, k: 10; head_a = 20; tail_a = -30; drop = 1
    base_y = bob
    spine = (P_SPINE[0] + ox, P_SPINE[1] + base_y)
    def at(p, a):  # rotate a point attached to a body half around the spine joint
        r = math.radians(a); dx, dy = p[0] + ox - spine[0], p[1] + base_y - spine[1]
        return (spine[0] + dx * math.cos(r) - dy * math.sin(r), spine[1] + dx * math.sin(r) + dy * math.cos(r))
    sh = at(P_SH, flex); hp = at(P_HIP, -flex)
    LF, LH = (9.5, 9.5), (10.5, 9.5)
    log = {}
    def leg4(root, a, b, L, r, ramp, front, key):
        k1 = rot(root, a, L[0]); k2 = rot(k1, a + (-b if front else b), L[1])
        if pose == 'run' or pose == 'attack': pass
        k2 = (k2[0], min(k2[1], gy))
        fig.capsule(root, k1, r, ramp); fig.capsule(k1, k2, r * 0.8, ramp); fig.sphere(k1[0], k1[1], r * 0.85, ramp=ramp)
        fig.poly([(k2[0] - 2.0, k2[1] - 2.2), (k2[0] + 3.2, k2[1] - 1.0), (k2[0] + 3.4, k2[1] + 0.5), (k2[0] - 2.0, k2[1] + 0.5)], ramp)
        log[key] = a
    # far legs first
    leg4((sh[0] - 1.5, sh[1] + 1), fr[1], bend(fr[1], 0.7), LF, 2.2, DARKCHROME, True, 'front_far')
    leg4((hp[0] + 1.5, hp[1] + 1), hi[1], bend(hi[1], 2.4), LH, 2.6, DARKCHROME, False, 'hind_far')
    paste(fig, WO_TAIL, P_TAILB, at(P_TAILB, -flex), tail_a)
    paste(fig, WO_REAR, P_SPINE, spine, -flex)
    paste(fig, WO_CHEST, P_SPINE, spine, flex)
    paste(fig, WO_HEAD, P_NECK, at(P_NECK, flex), head_a + flex * 0.5)
    leg4(sh, fr[0], bend(fr[0], 0), LF, 2.5, CHROME, True, 'front_near')
    leg4(hp, hi[0], bend(hi[0], 1.7), LH, 2.9, CHROME, False, 'hind_near')
    RIG_LOG.setdefault('wolf_' + pose, []).append(dict(log, flex=flex, bob=bob))
    return flipf(fig.finish(pal))

def strip_png(frames, path, scale=4, gl=True):
    h = max(f.shape[0] for f in frames); fr = [np.pad(f, ((h - f.shape[0], 0), (0, 2), (0, 0))) for f in frames]
    s = np.concatenate(fr, 1); bg = np.zeros_like(s); bg[...] = (40, 24, 70, 255)
    c = np.where(s[..., 3:] > 0, s, bg)
    Image.fromarray(c).resize((c.shape[1] * scale, c.shape[0] * scale), Image.NEAREST).save(path)

# ---------------- knight march (upper body from the enemy ref sprite, rigged legs) ----------------
def knight_walk(idle, pal, n=8, S=18):
    up = flipf(idle)                                   # face right while rigging
    h, w = up.shape[:2]; HIPY = 40
    up_hi = np.array(Image.fromarray(up).resize((w * K, h * K), Image.NEAREST)); up_hi[HIPY * K + 2:, :, 3] = 0
    hipx = 25; W, H = w + 24, h + 2; ox = 12; gy = H - 2
    T = walk_targets(n, S, 11.5, 10.5, gy, hipx + ox, lift=4.5, bob_amp=0.8, dip=0.8, ankle=1.8)
    out = []
    for i in range(n):
        hip, fA, fB = T[i]; phi = 2 * math.pi * i / n
        fig = Painter(W, H, K)
        kB = chrome_leg(fig, (hip[0] + 2, hip[1]), fB, 11.5, 10.5, 3.0, DARKCHROME)
        paste(fig, up_hi, (hipx, HIPY), hip, 1.2 * math.sin(2 * phi))
        kA = chrome_leg(fig, (hip[0] - 1, hip[1]), fA, 11.5, 10.5, 3.3, CHROME)
        RIG_LOG.setdefault('knight_march', []).append({'hipA': ang(hip, kA), 'hipB': ang(hip, kB), 'kneeA': knee_angle(hip, kA, fA), 'liftA': gy - fA[1]})
        out.append(flipf(fig.finish(pal)))
    return out, S

# ---------------- spider: ref body, rigged legs, alternating tetrapod gait ----------------
SP, SPW = mref(AREF, (22, 382, 212, 493), 44)
SP_BODY = SP.cut([(SPW - x, y) for x, y in [(30, 34), (60, 26), (84, 0), (162, 0), (168, 58), (134, 76), (84, 86), (36, 84)]])
SP_C = SP.P(SPW - 100, 50)

def spider_pose(pose, i, pal, W=86, H=46):
    n = 4; ox, gy = 6, H - 2; phi = 2 * math.pi * i / n
    fig = Painter(W, H, K)
    bob = {'walk': -1.0 * (i % 2), 'telegraph': -4 - i, 'attack': 1.5, 'hit': -1, 'down': 4}[pose]
    tilt = {'walk': 0, 'telegraph': -10, 'attack': 6, 'hit': -8, 'down': 0}[pose]
    c = (SP_C[0] + ox, SP_C[1] + bob)
    roots = [SP.P(SPW - x, y) for x, y in [(56, 62), (80, 66), (110, 66), (138, 60)]]   # front -> back, along the underside
    log = {}
    for side, ramp, dx in ((-1, DARKCHROME, 2.5), (1, CHROME, 0)):       # far side first
        for j, r0 in enumerate(roots):
            root = (r0[0] + ox + dx, r0[1] + bob + (0 if side > 0 else -1.5))
            # tetrapod: legs (0,2) of one side + (1,3) of the other swing together
            grp = (j + (0 if side > 0 else 1)) % 2
            ph = phi + grp * math.pi
            swing = math.cos(ph)                         # foot fore/aft; lifted while moving forward
            lift_t = max(0, math.sin(ph))
            reach = [24, 11, -9, -22][j] * (1.0 if side > 0 else 0.85)   # splayed: front legs reach forward, back legs back
            sw = 10 * swing if pose == 'walk' else 0
            lift = lift_t * 5 if pose == 'walk' else 0
            a = reach + sw
            if pose == 'telegraph' and j == 0: a, lift = 30, 22
            if pose == 'attack' and j == 0: a, lift = 36, 8
            if pose == 'down': a, lift = reach * 1.3, -1
            foot = (root[0] + a, gy - lift)
            knee = (root[0] + a * 0.42, root[1] - 13 - (2 if j in (0, 3) else 0) + lift * 0.2)
            fig.capsule(root, knee, 1.7, ramp); fig.capsule(knee, foot, 1.3, ramp); fig.sphere(knee[0], knee[1], 1.6, ramp=ramp)
            log[f'{"far" if side < 0 else "near"}{j}'] = round(a, 1)
    paste(fig, SP_BODY, SP_C, c, tilt)
    RIG_LOG.setdefault('spider_' + pose, []).append(dict(log, bob=bob))
    return flipf(fig.finish(pal))

# ---------------- bat: ref body, rigged membrane wings ----------------
BA, BAW = mref(AREF, (20, 535, 216, 664), 46)
BA_BODY = BA.cut([(BAW - x, y) for x, y in [(8, 56), (60, 44), (84, 52), (132, 58), (160, 112), (142, 128), (60, 120), (12, 106)]])
BA_C = BA.P(BAW - 96, 76); BA_SH = [BA.P(BAW - 92, 58), BA.P(BAW - 112, 60)]
FLAP = {'fly': [70, 25, -45, 15], 'telegraph': [70, 74], 'attack': [-20], 'hit': [30], 'down': [-50]}   # wing angle above horizontal

def bat_pose(pose, i, pal, W=84, H=70):
    ox, oy = 8, 6
    wa = FLAP[pose][i % len(FLAP[pose])]
    rise = -0.09 * wa                                   # body rises on the downstroke, sinks on the upstroke
    fig = Painter(W, H, K)
    def wing(sh, a, ramp, span):
        r = math.radians(a)
        tip = (sh[0] - span * 0.55 * math.cos(r) + 6, sh[1] - span * math.sin(r) * 0.8)
        wr = (sh[0] + (tip[0] - sh[0]) * 0.42 + 3, sh[1] + (tip[1] - sh[1]) * 0.42 - 3 * math.cos(r))
        root_back = (sh[0] - 15, sh[1] + 5)
        # trailing edge: scallops between finger tips, from the wing tip back to the body
        f1 = (tip[0] + (root_back[0] - tip[0]) * 0.33 - 2, tip[1] + (root_back[1] - tip[1]) * 0.33 + 4)
        f2 = (tip[0] + (root_back[0] - tip[0]) * 0.66 - 1, tip[1] + (root_back[1] - tip[1]) * 0.66 + 4)
        mid = lambda p, q, d: ((p[0] + q[0]) / 2 + d * 0.3, (p[1] + q[1]) / 2 - d)
        mem = [sh, wr, tip, mid(tip, f1, 2), f1, mid(f1, f2, 2), f2, mid(f2, root_back, 2), root_back]
        fig.poly(mem, ramp)
        for t in (tip, f1, f2): fig.capsule(wr, t, 0.5, CHROME)
        fig.capsule(sh, wr, 1.0, CHROME); fig.sphere(wr[0], wr[1], 1.0)
        return wr, [tip]
    sh_back = (BA_SH[1][0] + ox, BA_SH[1][1] + oy + rise); sh_front = (BA_SH[0][0] + ox, BA_SH[0][1] + oy + rise)
    wing(sh_back, wa + 8, DARKCHROME, 56)
    paste(fig, BA_BODY, BA_C, (BA_C[0] + ox, BA_C[1] + oy + rise), {'attack': 18, 'hit': -14, 'down': 30}.get(pose, 0))
    wr, tips = wing(sh_front, wa, DARKCHROME, 62)
    RIG_LOG.setdefault('bat_' + pose, []).append({'wing': wa, 'rise': rise, 'tip_y': round(tips[0][1], 1)})
    return flipf(fig.finish(pal))

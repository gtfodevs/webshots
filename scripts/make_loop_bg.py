#!/usr/bin/env python3
"""Themed seamless-looping background video for comic mode (played full-frame behind every page; panels cover it).

  python3 scripts/make_loop_bg.py --theme blinking_eyes --orient landscape --out /workspace/<song>/bg/eyes-landscape.mp4
  themes: blinking_eyes (horror), starfield (space), neon_rain (cyber / dojo), embers (fantasy: embers + smoke),
          deco_gold (1920s / crime / luxury: gold art-deco sunburst + shimmer + gold dust on black)

Every motion is periodic in the loop length (blink schedules, twinkles and pulses repeat a whole number of times; drifting
things travel a whole number of screen sizes), so frame N wraps onto frame 0. The seam check measures the last->first frame
difference against the typical frame-to-frame difference and fails (exit 1) when the seam would show a jump.
Spec: "bg_video": {"landscape": "bg/x-landscape.mp4", "vertical": "bg/x-vertical.mp4"}, "loop": true.
Never overwrites: -v2, -v3 ... suffixes.
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_lib as C

TAU = 2 * math.pi


def eyes(W, H, N, rnd, ph):
    """Pairs of glowing eyes (mostly red, ~20% ghost-green). Each pair blinks 1-3x per loop at staggered times
    (0.25 s lid close/open), ~1 in 5 does a slow 0.9 s menacing blink, the glow pulses, some pairs fade out and back."""
    fps = 30
    n_eyes = int(W * H / 52000)
    E = []
    for _ in range(n_eyes):
        s = rnd.uniform(16, 34) * (W / 1920 if W > H else 1)
        E.append(dict(x=rnd.uniform(0.03, 0.97) * W, y=rnd.uniform(0.03, 0.97) * H, s=s,
                      col=(120, 255, 170) if rnd.random() < 0.2 else (255, 40, 30),
                      blinks=[(rnd.uniform(0, 1), 0.9 if rnd.random() < 0.2 else rnd.uniform(0.2, 0.3)) for _ in range(rnd.integers(1, 4))],
                      pk=int(rnd.integers(1, 4)), pp=rnd.uniform(0, TAU), fade=rnd.random() < 0.3, fp=rnd.uniform(0, 1)))
    L = N / fps
    def frame(n):
        t = n / fps
        layer = Image.new('L', (W, H)); core = Image.new('RGB', (W, H)); glow = Image.new('RGB', (W, H))
        dl, dc = ImageDraw.Draw(layer), ImageDraw.Draw(core)
        for e in E:
            op = 1.0
            for b0, d in e['blinks']:
                x = ((t - b0 * L) % L) / d          # periodic in L
                if x < 1:
                    op = min(op, (1 - math.sin(math.pi * x)) if d < 0.5 else (1 - C.ease_io(min(1, x / 0.4)) if x < 0.4 else (0 if x < 0.6 else C.ease_io((x - 0.6) / 0.4))))
            a = 0.75 + 0.25 * math.sin(TAU * e['pk'] * n / N + e['pp'])
            if e['fade']:
                y = (n / N + e['fp']) % 1.0
                a *= max(0.0, min(1.0, abs(y - 0.5) * 2 / 0.3 - 0.4))   # fades out around mid-cycle and back
            if a < 0.02:
                continue
            s = e['s']; eh = s * 0.5 * op
            for side in (-1, 1):
                cx = e['x'] + side * s * 0.8; cy = e['y']
                sl = side * s * 0.12
                if eh >= 0.6:
                    pts = [(cx - s / 2, cy + sl), (cx, cy - eh), (cx + s / 2, cy - sl), (cx, cy + eh * 0.8)]
                    col = tuple(int(c * a) for c in e['col'])
                    dl.polygon(pts, fill=int(255 * a))
                    dc.polygon(pts, fill=tuple(min(255, int((c + 150) * a)) for c in e['col']))
                    glow.paste(col, [int(cx - s), int(cy - s / 2), int(cx + s), int(cy + s / 2)])
        g = glow.filter(ImageFilter.GaussianBlur(14))
        g = Image.fromarray(np.clip(np.asarray(g, np.float32) * 1.6, 0, 255).astype(np.uint8))
        g.paste(core, (0, 0), layer)
        return g
    return frame


def starfield(W, H, N, rnd, ph):
    """Three parallax layers of stars drifting left (1, 2 and 3 screen widths per loop) with periodic twinkle."""
    layers = []
    for k, (cnt, sz, br) in enumerate(((int(W * H / 2500), 1.2, 140), (int(W * H / 9000), 2.0, 200), (int(W * H / 30000), 3.2, 255))):
        layers.append((rnd.uniform(0, W, cnt), rnd.uniform(0, H, cnt), sz, br, k + 1, rnd.uniform(0, TAU, cnt), rnd.integers(1, 4, cnt)))
    neb = np.zeros((H // 8, W // 8, 3), np.float32)
    for _ in range(5):
        cx, cy, r = rnd.uniform(0, W // 8), rnd.uniform(0, H // 8), rnd.uniform(20, 70)
        yy, xx = np.mgrid[0:H // 8, 0:W // 8]
        neb += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))[..., None] * np.array(rnd.choice([[60, 20, 90], [20, 40, 90], [80, 20, 60]]), np.float32)
    neb = Image.fromarray(np.clip(neb, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    def frame(n):
        f = n / N
        img = neb.copy(); d = ImageDraw.Draw(img)
        for xs, ys, sz, br, speed, phs, tw in layers:
            x = (xs - f * speed * W) % W
            a = 0.6 + 0.4 * np.sin(TAU * tw * f + phs)
            for xi, yi, ai in zip(x, ys, a):
                c = int(br * ai); d.ellipse([xi - sz, yi - sz, xi + sz, yi + sz], fill=(c, c, min(255, c + 20)))
        return img
    return frame


def neon_rain(W, H, N, rnd, ph):
    """Neon rain streaks (cyan / magenta / violet) falling 2-4 screen heights per loop, faint scanline glow."""
    cnt = int(W * H / 9000)
    xs, ys = rnd.uniform(0, W, cnt), rnd.uniform(0, H, cnt)
    sp = rnd.integers(2, 5, cnt); ln = rnd.uniform(0.03, 0.09, cnt) * H
    cols = [(0, 230, 255), (255, 60, 200), (150, 90, 255)]
    ci = rnd.integers(0, 3, cnt)
    def frame(n):
        f = n / N
        img = Image.new('RGB', (W, H), (6, 4, 14)); d = ImageDraw.Draw(img)
        for x, y0, s, l, c in zip(xs, ys, sp, ln, ci):
            y = (y0 + f * s * H) % H
            for yy in (y, y - H):   # wraps exactly s screen heights per loop
                d.line([(x, yy), (x - l * 0.08, yy + l)], fill=cols[c], width=2)
        g = img.filter(ImageFilter.GaussianBlur(3))
        return Image.blend(img, g, 0.5).point(lambda v: min(255, int(v * 1.3)))
    return frame


def embers(W, H, N, rnd, ph):
    """Embers rising 1-2 screen heights per loop with periodic sway over slow drifting smoke."""
    cnt = int(W * H / 14000)
    xs, ys = rnd.uniform(0, W, cnt), rnd.uniform(0, H, cnt)
    sp = rnd.integers(1, 3, cnt); sw = rnd.uniform(10, 40, cnt); swp = rnd.uniform(0, TAU, cnt); r = rnd.uniform(1.5, 4, cnt)
    smoke = rnd.normal(0, 1, (H // 16, 2 * W // 16)).astype(np.float32)
    smoke = np.asarray(Image.fromarray(((smoke * 40) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
    smoke = np.concatenate([smoke[:, :W // 16], smoke[:, :W // 16]], 1)   # tiles: drifting exactly one width per loop
    def frame(n):
        f = n / N
        off = int(round(f * (W // 16)))
        sm = smoke[:, off:off + W // 16]
        sm = Image.fromarray(np.clip((sm - 110) * 0.6, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        img = Image.merge('RGB', [sm.point(lambda v: int(v * 0.5)), sm.point(lambda v: int(v * 0.3)), sm.point(lambda v: int(v * 0.35))])
        d = ImageDraw.Draw(img)
        for x0, y0, s, w, p, rr in zip(xs, ys, sp, sw, swp, r):
            y = (y0 - f * s * H) % H
            x = x0 + w * math.sin(TAU * f * s + p)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 150 + int(60 * math.sin(TAU * f + p)), 40))
        return Image.blend(img, img.filter(ImageFilter.GaussianBlur(4)), 0.4).point(lambda v: min(255, int(v * 1.25)))
    return frame


def deco_gold(W, H, N, rnd, ph):
    """Art-deco gold on black (crime / 1920s): a sunburst fan of thin gold rays rising from the bottom centre, stepped
    deco arcs around its hub, chevron bands top and bottom and a double keyline frame. A soft diagonal shimmer band
    sweeps across exactly once per loop (wrapping), each ray glints on its own whole-number period, and fine gold dust
    drifts up exactly one screen height per loop with periodic twinkle - so frame N wraps onto frame 0."""
    S = 2   # line art drawn at 2x, then downsampled (anti-aliased hairlines)
    art = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(art)
    cx, cy = W * S / 2, H * S * (1.04 if W > H else 0.86)
    R = math.hypot(W * S, H * S)
    n_rays = 44
    rays = []
    for k in range(n_rays + 1):
        a = math.pi + math.pi * k / n_rays
        rays.append(a)
        wdt = 3 * S if k % 4 == 0 else (2 * S if k % 2 == 0 else 1 * S)
        d.line([(cx + 0.16 * R * math.cos(a), cy + 0.16 * R * math.sin(a)), (cx + R * math.cos(a), cy + R * math.sin(a))],
               fill=200 if k % 2 == 0 else 120, width=wdt)
    for j, rr in enumerate((0.10, 0.13, 0.16, 0.30, 0.31, 0.47)):   # stepped deco arcs around the hub
        r_ = rr * R
        d.arc([cx - r_, cy - r_, cx + r_, cy + r_], 180, 360, fill=230 if j in (2, 5) else 150, width=(3 if j in (2, 5) else 2) * S)
    for row, y0 in ((0, 0.0), (1, 1.0)):                           # chevron bands
        yy = y0 * H * S
        step = 0.055 * min(W, H) * S
        for m in range(3):
            off = (m + 1) * 0.022 * min(W, H) * S * (1 if row == 0 else -1)
            pts = []
            x = 0.0; up = True
            while x <= W * S + step:
                pts.append((x, yy + off + (0 if up else step * 0.45 * (1 if row == 0 else -1)))); x += step / 2; up = not up
            d.line(pts, fill=150 - 30 * m, width=S * 2 if m == 0 else S)
    m_ = 0.018 * min(W, H) * S                                     # double keyline frame
    for k, w_ in ((1, 2), (2.2, 1)):
        d.rectangle([m_ * k, m_ * k, W * S - m_ * k, H * S - m_ * k], outline=170, width=int(w_ * S))
    art = art.resize((W, H), Image.LANCZOS)
    A = np.asarray(art, np.float32) / 255.0
    # per-pixel ray index -> a glint phase per ray (whole-number periods per loop)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = np.arctan2(yy - cy / S, xx - cx / S)
    ang = np.where(ang > 0, ang - 2 * np.pi, ang)                   # upper half: -pi..0
    ray_i = np.clip(np.round((ang + np.pi) / np.pi * n_rays), 0, n_rays).astype(np.int32)
    gk = rnd.integers(1, 4, n_rays + 1); gp = rnd.uniform(0, TAU, n_rays + 1)
    u = (xx / W + yy / H) / 2.0                                     # diagonal coordinate 0..1
    gold = np.array([255, 196, 92], np.float32); deep = np.array([150, 96, 22], np.float32)
    vign = np.clip(1.15 - 0.55 * np.hypot((xx - W / 2) / W, (yy - H / 2) / H) * 2, 0.45, 1.0)
    cnt = int(W * H / 9000)
    dx, dy = rnd.uniform(0, W, cnt), rnd.uniform(0, H, cnt)
    dk = rnd.integers(1, 4, cnt); dp = rnd.uniform(0, TAU, cnt); dr = rnd.uniform(0.8, 2.2, cnt); dsw = rnd.uniform(4, 18, cnt)
    def frame(n):
        f = n / N
        dist = np.abs(((u - f + 0.5) % 1.0) - 0.5)                  # wrapped distance to the sweeping band
        band = np.exp(-(dist / 0.07) ** 2)
        glint = 0.75 + 0.25 * np.sin(TAU * gk * f + gp)[ray_i]
        lum = A * (0.62 + 0.9 * band) * glint * vign
        col = deep[None, None] * (1 - band[..., None]) + gold[None, None] * band[..., None]
        img = np.clip(lum[..., None] * col + 6, 0, 255)
        out = Image.fromarray(img.astype(np.uint8))
        dd = ImageDraw.Draw(out)
        for x0, y0, k, p, r_, sw in zip(dx, dy, dk, dp, dr, dsw):
            y = (y0 - f * H) % H
            x = x0 + sw * math.sin(TAU * f * k + p)
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(TAU * k * f * 2 + p))
            dd.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(int(255 * a), int(205 * a), int(110 * a)))
        return Image.blend(out, out.filter(ImageFilter.GaussianBlur(2.5)), 0.35).point(lambda v: min(255, int(v * 1.12)))
    return frame


THEMES = {'blinking_eyes': eyes, 'starfield': starfield, 'neon_rain': neon_rain, 'embers': embers, 'deco_gold': deco_gold}


def seam_check(frames_fn, N):
    """last->first difference vs the median consecutive-frame difference (small proxies)."""
    def small(n):
        return np.asarray(frames_fn(n % N).resize((240, 240)), np.float32)
    ds = [np.abs(small(k + 1) - small(k)).mean() for k in range(0, N - 1, max(1, N // 24))]
    seam = np.abs(small(0) - small(N - 1)).mean()
    med = float(np.median(ds))
    return seam, med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--theme', required=True, choices=sorted(THEMES))
    ap.add_argument('--orient', choices=['landscape', 'vertical'], default='landscape')
    ap.add_argument('--seconds', type=float, default=9.6, help='loop length (rounded to whole frames)')
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    W, H = C.SIZES[a.orient]
    N = int(round(a.seconds * a.fps))
    fn = THEMES[a.theme](W, H, N, np.random.default_rng(a.seed), None)
    seam, med = seam_check(fn, N)
    ok = seam <= max(1.5 * med, 0.5)
    print(f'seam check: last->first diff {seam:.2f} vs median frame diff {med:.2f} -> {"OK" if ok else "JUMP"}')
    if not ok:
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out = C.next_free(a.out)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(a.fps),
                            '-i', '-', '-c:v', 'libx264', '-crf', '16', '-preset', 'slow', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for n in range(N):
        enc.stdin.write(fn(n).convert('RGB').tobytes())
    enc.stdin.close()
    if enc.wait():
        sys.exit('encode failed')
    print(out, f'{N} frames ({N / a.fps:.2f} s loop)')


if __name__ == '__main__':
    main()

"""Chrome robot painter for pixel-game sprites (reusable across songs).

Characters are painted at K x the final size with cylinder/sphere shading (no antialiasing), then
box-downscaled to the sprite size, quantized to the shot palette and outlined, so they land at the
same detail level as sprites cut from painted reference sheets. Brand: chrome silver, red eyes,
headphone ears.

  fig = Painter(w, h, K=3)                 # w,h in FINAL pixels
  fig.capsule((x0,y0),(x1,y1), r)          # coordinates in final pixels (floats ok)
  fig.sphere(cx, cy, rx, ry); fig.box(x0,y0,x1,y1); fig.poly(pts, base); fig.eye(...); fig.phones(...)
  arr = fig.finish(pal)                    # RGBA uint8, final size, quantized + outlined
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from pixel_sprites import quantize, outline, despeckle

CHROME = [(26, 24, 44), (62, 64, 92), (104, 108, 138), (150, 156, 184), (196, 202, 224), (238, 242, 255)]
DARKCHROME = [(18, 14, 30), (40, 38, 60), (66, 66, 92), (98, 100, 128), (134, 138, 166), (180, 186, 210)]

def ramp_of(rgb, n=6):
    r, g, b = rgb
    out = []
    for k in range(n):
        t = k / (n - 1)
        f = 0.25 + 1.0 * t
        out.append(tuple(int(min(255, c * f + (255 * max(0, t - 0.75) * 1.2))) for c in (r, g, b)))
    return out

class Painter:
    def __init__(self, w, h, K=3):
        self.K, self.w, self.h = K, w, h
        self.im = Image.new('RGBA', (int(w * K), int(h * K)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.light = (-0.45, -0.6)   # light from upper left

    def P(self, x, y): return (x * self.K, y * self.K)

    def capsule(self, p0, p1, r, ramp=CHROME):
        """Limb with cylindrical shading: stacked strokes from the dark rim to a highlight stripe."""
        K = self.K; d = self.d
        x0, y0 = self.P(*p0); x1, y1 = self.P(*p1)
        L = math.hypot(x1 - x0, y1 - y0) + 1e-6; nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        if nx * self.light[0] + ny * self.light[1] < 0: nx, ny = -nx, -ny   # normal toward the light
        R = r * K; n = len(ramp)
        for k in range(n):
            t = k / (n - 1); w = max(1, R * 2 * (1 - 0.8 * t)); off = R * 0.45 * t
            ox, oy = nx * off, ny * off
            d.line([(x0 + ox, y0 + oy), (x1 + ox, y1 + oy)], fill=ramp[k], width=int(w))
            for (cx, cy) in ((x0 + ox, y0 + oy), (x1 + ox, y1 + oy)):
                d.ellipse([cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2], fill=ramp[k])

    def sphere(self, cx, cy, rx, ry=None, ramp=CHROME):
        ry = rx if ry is None else ry; K = self.K; n = len(ramp)
        for k in range(n):
            t = k / (n - 1); s = 1 - 0.78 * t
            ox, oy = self.light[0] * rx * 0.5 * t, self.light[1] * ry * 0.5 * t
            X, Y = (cx + ox) * K, (cy + oy) * K
            self.d.ellipse([X - rx * s * K, Y - ry * s * K, X + rx * s * K, Y + ry * s * K], fill=ramp[k])

    def box(self, x0, y0, x1, y1, ramp=CHROME, bevel=0.18):
        K = self.K; n = len(ramp)
        self.d.rectangle([x0 * K, y0 * K, x1 * K, y1 * K], fill=ramp[1])
        w, h = x1 - x0, y1 - y0
        for k in range(2, n):
            t = (k - 1) / (n - 2); i = bevel * min(w, h) * t
            self.d.rectangle([(x0 + i * 0.6) * K, (y0 + i * 0.5) * K, (x1 - i * 1.6) * K, (y1 - i * 1.8) * K], fill=ramp[k])

    def poly(self, pts, ramp=CHROME, shade=True):
        K = self.K; P = [(x * K, y * K) for x, y in pts]
        self.d.polygon(P, fill=ramp[2])
        if shade:
            cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
            for k, s in ((3, 0.75), (4, 0.45)):
                Q = [(cx + (x - cx) * s + self.light[0] * 2 * K * (1 - s), cy + (y - cy) * s + self.light[1] * 2 * K * (1 - s)) for x, y in P]
                self.d.polygon(Q, fill=ramp[k])

    def flat(self, pts, col):
        self.d.polygon([(x * self.K, y * self.K) for x, y in pts], fill=col)

    def line(self, p0, p1, col, w=1):
        self.d.line([self.P(*p0), self.P(*p1)], fill=col, width=max(1, int(w * self.K)))

    def eye(self, x, y, r=1.0, col=(255, 40, 60)):
        K = self.K
        self.d.ellipse([(x - r) * K, (y - r * 0.8) * K, (x + r) * K, (y + r * 0.8) * K], fill=(120, 0, 20))
        self.d.ellipse([(x - r * 0.7) * K, (y - r * 0.55) * K, (x + r * 0.7) * K, (y + r * 0.55) * K], fill=col)
        self.d.ellipse([(x - r * 0.25) * K, (y - r * 0.3) * K, (x + r * 0.2) * K, (y + r * 0.1) * K], fill=(255, 200, 200))

    def phones(self, cx, cy, r, side=1, led=(94, 231, 255), band=True):
        """Headphone ear cup (side view: one cup) + band over the head."""
        K = self.K
        if band:
            self.d.arc([(cx - r * 2.2) * K, (cy - r * 2.6) * K, (cx + r * 1.4) * K, (cy + r * 0.6) * K], 190, 350, fill=(30, 26, 48), width=max(1, int(0.9 * K)))
        self.sphere(cx, cy, r * 0.9, r * 1.05, ramp=DARKCHROME)
        self.d.ellipse([(cx - r * 0.35) * K, (cy - r * 0.35) * K, (cx + r * 0.35) * K, (cy + r * 0.35) * K], fill=led)

    def finish(self, pal, min_island=6):
        im = self.im.resize((int(self.w), int(self.h)), Image.BOX)
        a = np.asarray(im).astype(float)
        al = a[..., 3:4] / 255
        rgb = np.where(al > 0, a[..., :3] / np.maximum(al, 1e-6) * 1.0, 0)
        out = np.dstack([np.clip(rgb, 0, 255), (al[..., 0] >= 0.45) * 255]).astype(np.uint8)
        return outline(despeckle(quantize(out, pal), min_island))

# ---------- legs ----------
def ik(hx, hy, fx, fy, L1, L2, fwd=1):
    dx, dy = fx - hx, fy - hy; dd = max(1e-3, min(math.hypot(dx, dy), L1 + L2 - 0.05))
    a = math.atan2(dy, dx); c = (L1 * L1 + dd * dd - L2 * L2) / (2 * L1 * dd)
    b = math.acos(max(-1, min(1, c)))
    ka = a - b * fwd
    return hx + L1 * math.cos(ka), hy + L1 * math.sin(ka)

def walk_foot(i, n, S, lift):
    """Foot offset for frame i of an n-frame cycle: stance (planted, slides back S over n/2 frames
    exactly as fast as the ground scrolls) then swing (forward, lifted)."""
    p = (i % n) / n
    if p < 0.5: return S / 2 - S * (p / 0.5), 0.0
    q = (p - 0.5) / 0.5
    return -S / 2 + S * q, -lift * math.sin(math.pi * q)

BOB8 = [0, 1, 0, -1, 0, 1, 0, -1]   # contact, down, pass, up (x2)

def leg(fig, hip, foot, L1, L2, r, face=1, ramp=CHROME, boot=None):
    kx, ky = ik(hip[0], hip[1], foot[0], foot[1], L1, L2, face)
    fig.capsule(hip, (kx, ky), r, ramp); fig.capsule((kx, ky), foot, r * 0.85, ramp)
    fig.sphere(kx, ky, r * 0.8, ramp=ramp)
    bl = boot or r * 2.6
    fx, fy = foot
    fig.poly([(fx - r * 0.9 * face, fy - r * 1.6), (fx + bl * face, fy - r * 0.4), (fx + bl * face, fy + 0.4), (fx - r * 1.1 * face, fy + 0.4)], ramp)
    return kx, ky

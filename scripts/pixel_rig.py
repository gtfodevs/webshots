"""2D cut-out rig for pixel-game robots (reusable).

Parts (cut from a clean reference at 4x, or painted chrome segments) hang off a pelvis and are
posed with forward kinematics from a walk keyframe table; the stance foot is solved by IK so it
stays planted and slides back exactly STRIDE px per step (= world scroll). The whole pose is
composited at 4x, box-downscaled once, quantized and outlined ONCE so it reads as one sprite.

  ref = RefParts(sheet_rgb, box, key='green')         # crop + chroma-key a reference figure
  part = ref.cut(poly, mask_fn)                         # RGBA part (4x space) + its own coords
  walk_cycle(n=8, stride_px, leg_len) -> per-frame pelvis / foot / knee targets
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from pixel_robots import Painter, CHROME, DARKCHROME, ik

K = 4  # hi-res factor

def key_green(rgb):
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    keyed = (g > 140) & (g - np.maximum(r, b) > 60)
    # despill edge: pixels with a green cast near the key
    spill = (g > np.maximum(r, b) + 12) & ~keyed
    out = rgb.copy().astype(int)
    out[spill, 1] = np.maximum(out[spill, 0], out[spill, 2])
    a = (~keyed).astype(np.uint8) * 255
    return np.dstack([np.clip(out, 0, 255).astype(np.uint8), a])

def hsv(rgba):
    c = rgba[..., :3].astype(float) / 255; mx, mn = c.max(2), c.min(2); d = mx - mn + 1e-6
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, d / (mx + 1e-6), mx

class RefParts:
    """A keyed reference figure scaled so 1 unit = 1 final pixel (stored at K x)."""
    def __init__(self, sheet, box, final_h):
        x0, y0, x1, y1 = box; crop = sheet[y0:y1, x0:x1]
        self.s = final_h * K / (y1 - y0)                # source px -> hi-res px
        im = Image.fromarray(key_green(crop)).resize((round((x1 - x0) * self.s), round((y1 - y0) * self.s)), Image.NEAREST)
        self.rgba = np.array(im); self.f = self.s / K    # source px -> final px
    def cut(self, poly_src=None, mask=None):
        """poly in SOURCE crop coords; mask(rgba)->bool. Returns RGBA hi-res layer of full crop size."""
        a = self.rgba.copy(); m = a[..., 3] > 0
        if poly_src is not None:
            pm = Image.new('L', (a.shape[1], a.shape[0]), 0)
            ImageDraw.Draw(pm).polygon([(x * self.s, y * self.s) for x, y in poly_src], fill=255)
            m &= np.array(pm) > 0
        if mask is not None: m &= mask(a)
        a[..., 3] = m * 255; return a
    def P(self, x, y): return (x * self.f, y * self.f)   # source crop coords -> final px

def paste(fig, layer, pivot_final, at_final, angle=0.0, shear=None):
    """Composite a hi-res layer into the Painter canvas: rotate `angle` deg about pivot, then move
    the pivot to `at`. shear(row_frac)->dx_final optional (cloth lag)."""
    im = layer
    if shear is not None:
        h = im.shape[0]; out = np.zeros_like(im)
        for y in range(h):
            dx = int(round(shear(y / h) * K))
            if dx >= 0: out[y, dx:] = im[y, :im.shape[1] - dx]
            else: out[y, :dx] = im[y, -dx:]
        im = out
    pil = Image.fromarray(im)
    px, py = pivot_final[0] * K, pivot_final[1] * K
    if angle:
        pil = pil.rotate(angle, resample=Image.NEAREST, center=(px, py))
    ox, oy = round(at_final[0] * K - px), round(at_final[1] * K - py)
    fig.im.alpha_composite(pil, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))

def rot(p, a, L):
    """point at distance L from p along angle a (deg; 0 = straight down, + = forward/right)."""
    r = math.radians(a); return (p[0] + L * math.sin(r), p[1] + L * math.cos(r))

def ang(p, q):
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1]))

def walk_targets(n, S, L1, L2, ground, hip_x, lift, bob_amp=1.5, dip=1.0, ankle=2.3, sched=None):
    """Biped walk: n frames, 2 steps per cycle, stride S final px per step.
    Leg A: stance frames 0..n/2-1 (foot from +S/2 to -S/2 relative to the hip, planted -> slides
    back S/(n/2) per frame = world scroll), swing frames n/2..n-1 (foot from -S/2 forward to +S/2,
    lifted).  Leg B is half a cycle out of phase.  Returns per frame: hip(x,y), footA, footB."""
    half = n // 2; L = L1 + L2
    h0 = math.sqrt((0.985 * L) ** 2 - (S / 2) ** 2) + ankle  # hip height at contact (leg nearly straight)
    out = []
    for i in range(n):
        p = i % half
        cf = (sched[p] if sched else p / half)            # fraction of the step travelled at this frame
        fx = S / 2 - S * cf                             # stance foot offset from the hip
        hp = math.sqrt((0.975 * L) ** 2 - fx * fx) + ankle  # inverted-pendulum height over the stance foot
        h = 0.85 * hp + 0.15 * h0
        bob = (dip if p == 1 else 0) - (bob_amp if p == half // 2 + 1 else 0) * 0.5
        hip = (hip_x, ground - h + bob)
        def foot(j):
            q = (j % n)
            if q < half:      # stance
                return (hip_x + S / 2 - S * (sched[q] if sched else q / half), ground)
            t = (sched[q - half] if sched else (q - half) / half)
            return (hip_x - S / 2 + S * t, ground - lift * math.sin(math.pi * min(1, t * 1.15)) ** 0.8)
        out.append((hip, foot(i), foot(i + half)))
    return out

def chrome_leg(fig, hip, foot, L1, L2, r, ramp=CHROME, face=1, toe=None):
    """Segmented chrome leg: thigh plate, round knee cap, shin, boot. Knee bends forward (face)."""
    kx, ky = ik(hip[0], hip[1], foot[0], foot[1] - r * 0.7, L1, L2, face)
    knee = (kx, ky); ank = (foot[0], foot[1] - r * 0.7)
    fig.capsule(hip, knee, r, ramp); fig.capsule(knee, ank, r * 0.82, ramp)
    fig.sphere(kx, ky, r * 0.95, ramp=ramp); fig.sphere(hip[0], hip[1], r * 1.0, ramp=ramp)
    bl = r * 2.6; fx, fy = foot
    tilt = 0 if toe is None else toe
    fig.poly([(fx - r * 1.0 * face, fy - r * 1.7), (fx + bl * 0.6 * face, fy - r * 1.4 - tilt * 0.5), (fx + bl * face, fy - tilt), (fx + bl * face, fy + 0.4 - tilt), (fx - r * 1.1 * face, fy + 0.4)], ramp)
    return knee

def chrome_arm(fig, sh, a_up, a_lo, L1, L2, r, ramp=CHROME):
    el = rot(sh, a_up, L1); wr = rot(el, a_lo, L2)
    fig.sphere(sh[0], sh[1], r * 1.25, ramp=ramp)
    fig.capsule(sh, el, r, ramp); fig.capsule(el, wr, r * 0.85, ramp); fig.sphere(el[0], el[1], r * 0.8, ramp=ramp)
    fig.sphere(wr[0], wr[1], r * 1.05, ramp=ramp)
    return el, wr

def knee_angle(hip, knee, foot):
    a1, a2 = ang(hip, knee), ang(knee, foot); return a1 - a2

def onion(frames, scale=4):
    """Onion-skin: overlay all frames (feet-aligned) with alternating tints."""
    h = max(f.shape[0] for f in frames); w = max(f.shape[1] for f in frames)
    acc = np.zeros((h, w, 3), float); cnt = np.zeros((h, w), float)
    tints = [(255, 80, 80), (255, 200, 60), (80, 255, 120), (80, 160, 255), (220, 90, 255), (255, 255, 255), (60, 230, 230), (255, 120, 200)]
    out = np.full((h, w, 3), 24, np.uint8)
    for i, f in enumerate(frames):
        y0 = h - f.shape[0]; x0 = (w - f.shape[1]) // 2
        m = f[..., 3] > 0; t = np.array(tints[i % len(tints)])
        reg = out[y0:y0 + f.shape[0], x0:x0 + f.shape[1]]
        reg[m] = (reg[m] * 0.45 + (f[..., :3][m] * 0.35 + t * 0.65) * 0.55).astype(np.uint8)
    return Image.fromarray(out).resize((w * scale, h * scale), Image.NEAREST)

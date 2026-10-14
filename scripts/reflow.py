#!/usr/bin/env python3
"""Living panels (shared layout feature): a page reflows through layout states as panels arrive.

State k (k panels landed) is a tiling of the content box (normalised rects, gutter G). When panel k lands it
arrives FULL FRAME (on top) for `arrive` beats, then every panel eases into state k over `move` beats
(0.5-0.9 s). The state family is built so the move is collision-free: already-placed panels only shrink along
one axis or share a moving edge, never cross each other.

Families (every move is collision-free: panels only shrink along one axis or share a moving edge):
  'wide' (16:9 default; cells stay landscape-shaped, right for 16:9 footage)
    1: [full]   2: [A top row / B bottom row]   3: [A top] over [B | C]   4: 2x2 (A shrinks to top-left)
  'rows' (Short default; 9:16 frame stacked into rows, 3 rows = 16:9-ish cells)
    1: [full]   2: two rows   3: three rows   4: four rows
  'grid' (16:9, for tall/portrait art)
    1: [full]   2: [left | right]   3: [top-left | top-right] over [wide bottom]   4: 2x2
"""
import math

G = 0.016        # gutter (share of the content box)
MAX_PANELS = 4


FAMILIES = ('wide', 'rows', 'grid')
DEFAULT_FAMILY = {'landscape': 'wide', 'vertical': 'rows'}


def states(n, family='grid'):
    g = G / 2
    full = (0, 0, 1, 1)
    if n > MAX_PANELS:
        raise ValueError(f'reflow pages hold at most {MAX_PANELS} panels')
    if family == 'wide':
        top, bot = (0, 0, 1, 0.5 - g), (0, 0.5 + g, 1, 0.5 - g)
        bl, br = (0, 0.5 + g, 0.5 - g, 0.5 - g), (0.5 + g, 0.5 + g, 0.5 - g, 0.5 - g)
        tl, tr = (0, 0, 0.5 - g, 0.5 - g), (0.5 + g, 0, 0.5 - g, 0.5 - g)
        fam = {1: [full], 2: [top, bot], 3: [top, bl, br], 4: [tl, bl, br, tr]}
    elif family == 'rows':
        fam = {k: [(0, (j / k + g) if j else 0, 1, (1 / k) - (g if j else 0) - (g if j < k - 1 else 0)) for j in range(k)] for k in range(1, 5)}
    else:
        L, Rt = (0, 0, 0.5 - g, 1), (0.5 + g, 0, 0.5 - g, 1)
        top = 0.55
        s3 = [(0, 0, 0.5 - g, top - g), (0.5 + g, 0, 0.5 - g, top - g), (0, top + g, 1, 1 - top - g)]
        s4 = [(0, 0, 0.5 - g, 0.5 - g), (0.5 + g, 0, 0.5 - g, 0.5 - g), (0, 0.5 + g, 0.5 - g, 0.5 - g), (0.5 + g, 0.5 + g, 0.5 - g, 0.5 - g)]
        fam = {1: [full], 2: [L, Rt], 3: s3, 4: s4}
    return [fam[k] for k in range(1, n + 1)]


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return tuple(p + (q - p) * k for p, q in zip(a, b))


def schedule(lands, beat, arrive=1.0, move=1.0):
    """lands: landing times (sorted, page clock). Returns [(t_land, t_settle_start, t_settle_end)] per state."""
    out = []
    for t in lands:
        a = t + arrive * beat
        out.append((t, a, a + min(0.9, max(0.5, move * beat))))
    return out


def rect_at(i, t, lands, beat, arrive=1.0, move=1.0, transpose=False, family='grid', arrival=(0, 0, 1, 1)):
    """Normalised rect of panel i (landing order) at page time t, or None before it lands. Returns (rect, z).
    arrival: where a newcomer sits while it arrives (default the whole content box; a full-width band for wide
    shots in a tall frame, comic_lib.arrival_box)."""
    n = len(lands)
    S = states(n, family)
    sch = schedule(lands, beat, arrive, move)
    if t < lands[i]:
        return None, 0
    # the latest state that has started
    k = max(j for j in range(n) if lands[j] <= t)
    t_land, t_s0, t_s1 = sch[k]
    tgt = S[k][i]
    if k == 0:
        r, z = tuple(arrival), 0                   # the first panel alone: full frame (or its full-width band)
    else:
        prev = (tuple(arrival) if k == 1 else S[k - 1][i]) if i < k else tuple(arrival)
        if t < t_s0:
            r = prev                                   # the newcomer holds full frame during its arrival
        else:
            r = lerp(prev, tgt, ease_io((t - t_s0) / (t_s1 - t_s0)))
        z = 2 if (i == k and t < t_s1) else 0
    if transpose:
        r = (r[1], r[0], r[3], r[2])
    return r, z


def collisions(lands, beat, arrive=1.0, move=1.0, n_samples=24, transpose=False, family='grid'):
    """[(t, i, j, overlap share)] where two settled / settling panels (not an arriving one) overlap."""
    out = []
    for k in range(1, len(lands)):
        t0 = lands[k]; t1 = lands[k] + (arrive + 1) * beat + 0.9
        for s in range(n_samples + 1):
            t = t0 + (t1 - t0) * s / n_samples
            rs = [rect_at(i, t, lands, beat, arrive, move, transpose, family) for i in range(k + 1)]
            for i in range(k + 1):
                for j in range(i + 1, k + 1):
                    (a, za), (b, zb) = rs[i], rs[j]
                    if a is None or b is None or za == 2 or zb == 2:
                        continue
                    ix = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]); iy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                    if ix > 1e-4 and iy > 1e-4:
                        out.append((round(t, 3), i, j, round(ix * iy / min(a[2] * a[3], b[2] * b[3]), 4)))
    return out

#!/usr/bin/env python3
"""Shared camera engine (comic mode, explainers, any renderer that crops footage into a cell).

Two jobs:
  1. track_regions(): follow focus boxes (faces, key action) through a clip at ~1 fps (cheap NCC template
     search), so the camera knows where faces go while the clip plays.
  2. plan_move(): choose ONE eased camera move per cut, from the cut's faces, the cell's aspect and the
     transitions on either side, and return a window(t) path (a crop window at the cell aspect, in source
     pixels). The window is applied to the still before the clip starts and to every clip frame, so the
     still -> clip handoff never jumps and the screen never stands still.

Move selection (documented in docs/VIDEO_PIPELINE.md, "Camera moves per cut"):
  - one face, or a splash / zoom / iris beat ....................... push_in   (slow push toward the face)
  - all faces fit, with little slack, 2+ faces ...................... pull_back (tight on the lead face -> all)
  - all faces fit with slack, outgoing whip ........................ whip      (pan accelerating into the whip)
  - all faces fit with slack ....................................... drift     (pan along the slack, toward the
                                                                                 outgoing transition's direction)
  - faces spread side to side wider than the cell ................. pan_h     (face A -> face B)
  - faces stacked / action up-down taller than the cell ........... tilt_v    (face A -> face B)
  - a single face cannot fit the cell at all ...................... needs_bigger_cell (layout must enlarge it)
Every move eases in and out but keeps a linear floor so the speed is never zero (no static frames).
"""
import json, math, os, subprocess
import numpy as np

PAD = 0.06          # share of the window kept clear around a face (stands in for the ink inset / slanted edges)
PUSH = 0.86         # push_in end scale (window shrinks to 86 %)
PULL = 0.78         # pull_back start scale
LINEAR = 0.25       # linear share of the progress curve (never zero speed)

DIRS = {'slide_left': (-1, 0), 'slide_right': (1, 0), 'slide_up': (0, -1), 'slide_down': (0, 1),
        'whip': (1, 0), 'whip_left': (-1, 0), 'whip_right': (1, 0), 'wipe': (1, 0), 'wipe_left': (-1, 0),
        'push_left': (-1, 0), 'push_right': (1, 0), 'slash': (1, 1), 'diagonal': (1, 1), 'speed_lines': (1, 0)}


def direction(name):
    """(dx, dy) a transition moves the eye, (0, 0) when it has none (fade, iris, zoom ...)."""
    if not name:
        return (0, 0)
    for k, v in DIRS.items():
        if k in name:
            return v
    return (0, 0)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def progress(x, curve='io'):
    x = min(max(x, 0.0), 1.0)
    if curve == 'linear':
        return x
    e = ease_io(x) if curve == 'io' else x ** 2.2   # 'in' accelerates into a whip
    return (1 - LINEAR) * e + LINEAR * x


# ------------------------------------------------------------------ tracking
def _gray_frames(path, fps=1.0, w=320):
    pr = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                         '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(',')
    W, H = int(pr[0]), int(pr[1]); h = int(round(H * w / W))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:{h}', '-f', 'rawvideo',
                          '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw, np.uint8)[: n * w * h].reshape(n, h, w).astype(np.float32)


def _match(frame, tpl, cx, cy, rad):
    """Best NCC position of tpl in frame around (cx, cy) +- rad px (top-left coords), stride 2 then refine."""
    th, tw = tpl.shape; H, W = frame.shape
    t = tpl - tpl.mean(); tn = math.sqrt(float((t * t).sum())) or 1.0
    best = (-2, cx, cy)
    def score(x, y):
        p = frame[y:y + th, x:x + tw]
        if p.shape != tpl.shape:
            return -2
        p = p - p.mean(); d = math.sqrt(float((p * p).sum())) * tn or 1.0
        return float((p * t).sum() / d)
    for step, r in ((3, rad), (1, 3)):
        x0, y0 = best[1] if best[0] > -2 else cx, best[2] if best[0] > -2 else cy
        for y in range(max(0, y0 - r), min(H - th, y0 + r) + 1, step):
            for x in range(max(0, x0 - r), min(W - tw, x0 + r) + 1, step):
                s = score(x, y)
                if s > best[0]:
                    best = (s, x, y)
    return best


_TRACK_CACHE = {}
def track_regions(clip_path, boxes, fps=1.0, cache_path=None, t_in=0.0, t_out=None):
    """boxes: [[x0, y0, x1, y1]] normalised to the clip frame at t_in. Returns {'t': [...], 'boxes': [[box per
    region] per sample]} normalised, sampled at ~fps from t_in to t_out. Boxes keep their size (faces barely
    scale over 6 s); a weak match (NCC < 0.35) keeps the previous position."""
    key = json.dumps([os.path.abspath(clip_path), os.path.getsize(clip_path), int(os.path.getmtime(clip_path)),
                      [[round(v, 4) for v in b] for b in boxes], fps, t_in, t_out])
    disk = {}
    if cache_path:
        try: disk = json.load(open(cache_path))
        except Exception: disk = {}
    if key in _TRACK_CACHE: return _TRACK_CACHE[key]
    if key in disk: _TRACK_CACHE[key] = disk[key]; return disk[key]
    G = _gray_frames(clip_path, fps)
    i0 = int(round(t_in * fps)); i1 = len(G) if t_out is None else min(len(G), int(math.ceil(t_out * fps)) + 1)
    G = G[i0:max(i1, i0 + 1)]
    H, W = G[0].shape
    out_t, out_b = [], []
    pos = []
    for b in boxes:
        x0, y0 = int(b[0] * W), int(b[1] * H); x1, y1 = max(x0 + 6, int(b[2] * W)), max(y0 + 6, int(b[3] * H))
        pos.append([x0, y0, x1 - x0, y1 - y0, G[0][y0:y1, x0:x1].copy()])
    for k, f in enumerate(G):
        row = []
        for p in pos:
            x, y, w, h, tpl = p
            if k > 0 and tpl.size:
                s, nx, ny = _match(f, tpl, x, y, max(8, int(0.12 * W)))
                if s >= 0.35:
                    p[0], p[1] = nx, ny
                    if s > 0.6:   # refresh the template slowly so it follows turning heads
                        p[4] = 0.7 * tpl + 0.3 * f[ny:ny + h, nx:nx + w]
            row.append([p[0] / W, p[1] / H, (p[0] + w) / W, (p[1] + h) / H])
        out_t.append(t_in + k / fps); out_b.append(row)
    res = {'t': out_t, 'boxes': out_b}
    _TRACK_CACHE[key] = res
    if cache_path:
        disk[key] = res
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump(disk, open(cache_path, 'w'))
    return res


def interp_boxes(track, t):
    ts = track['t']
    if t <= ts[0] or len(ts) == 1: return track['boxes'][0]
    if t >= ts[-1]: return track['boxes'][-1]
    j = max(i for i in range(len(ts)) if ts[i] <= t)
    a = (t - ts[j]) / (ts[j + 1] - ts[j])
    return [[(1 - a) * p + a * q for p, q in zip(b0, b1)] for b0, b1 in zip(track['boxes'][j], track['boxes'][j + 1])]


# ------------------------------------------------------------------ planning
class Plan:
    def __init__(self, move, keys, curve, t0, t1, faces_at, active, fits=True, why=''):
        self.move, self.keys, self.curve, self.t0, self.t1 = move, keys, curve, t0, t1
        self.faces_at, self.active, self.fits, self.why = faces_at, active, fits, why

    def window(self, t):
        """(X, Y, W, H) source px at time t (song or scene time, the same clock as t0/t1)."""
        x = (t - self.t0) / max(self.t1 - self.t0, 1e-3)
        ks = self.keys
        if len(ks) == 2:
            p = progress(x, self.curve); a, b = ks[0][1], ks[1][1]
            return tuple(av + (bv - av) * p for av, bv in zip(a, b))
        # multi-key (pan with holds): piecewise, eased per segment, linear floor inside each
        x = min(max(x, 0.0), 1.0)
        for (xa, wa), (xb, wb) in zip(ks, ks[1:]):
            if x <= xb + 1e-9:
                p = progress((x - xa) / max(xb - xa, 1e-6), 'io')
                return tuple(av + (bv - av) * p for av, bv in zip(wa, wb))
        return ks[-1][1]

    def expected(self, t):
        """Indices of the faces this move promises to keep fully in the window at t."""
        return self.active(t)

    def info(self):
        return {'move': self.move, 'fits': self.fits, 'why': self.why}


def _union(bs):
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def _place(lo_need, hi_need, size, lo_lim, hi_lim, pref):
    """Window start on one axis so [lo_need, hi_need] sits inside (with the window inside the limits); pref
    in [0, 1] picks within the feasible range. Returns (start, feasible)."""
    a = max(lo_lim, hi_need - size); b = min(hi_lim - size, lo_need)
    if a > b:
        return min(max((lo_need + hi_need) / 2 - size / 2, lo_lim), hi_lim - size), False
    return a + (b - a) * pref, True


REVEAL = True   # default camera rule 'reveal' (Jason 2026-10-14): pan only across the part the crop hides, one direction, eased, never back


def _reveal_plan(img_wh, cell_wh, within, faces_at, t0, t1, n_faces, F, PAD, Ww, Wh, bx, by, bw, bh, dx, dy):
    """Largest window of the cell's aspect (no zoom). If the art is wider/taller than the cell, pan linearly ONE way
    across the hidden slack (limited so the required faces stay in for the whole move); no slack = static."""
    w, h = Ww, Wh
    horiz = bw - w > bh - h
    slack = (bw - w) if horiz else (bh - h)
    lo, hi = (bx, bx + bw - w) if horiz else (by, by + bh - h)
    if n_faces and F and F[0]:
        U = _union([b for fs in F for b in fs])
        k = (0, 2) if horiz else (1, 3); size = w if horiz else h
        pad = PAD * size
        a = max(lo, U[k[1]] + pad - size); b = min(hi, U[k[0]] - pad)
        if a <= b:
            lo, hi = a, b
        else:
            c = min(max((U[k[0]] + U[k[1]]) / 2 - size / 2, lo), hi); lo = hi = c
    cx, cy = bx + (bw - w) / 2, by + (bh - h) / 2
    def W_(v):
        return (v, cy, w, h) if horiz else (cx, v, w, h)
    if slack < 0.02 * (w if horiz else h) or hi - lo < 2:
        v = (lo + hi) / 2
        return Plan('static', [(0, W_(v)), (1, W_(v))], 'linear', t0, t1, faces_at, lambda t: list(range(n_faces)), why='art fits: no pan')
    sg = (dx if horiz else dy) or 1
    a, b = (lo, hi) if sg > 0 else (hi, lo)
    return Plan('reveal_pan', [(0, W_(a)), (1, W_(b))], 'io', t0, t1, faces_at, lambda t: list(range(n_faces)),
                why='linear one-way pan across the cropped-off ' + ('width' if horiz else 'height'))


def plan_move(img_wh, cell_wh, within, faces_at, t0, t1, n_faces, out_tr=None, in_tr=None, splash=False,
              base=None, pad=PAD):
    PAD = pad
    """faces_at(t) -> [[x0, y0, x1, y1] source px] for the required faces / focus regions (tracked).
    within: (X, Y, W, H) source rect the footage covers. Returns a Plan."""
    iw, ih = img_wh; cw, ch = cell_wh; a = cw / ch
    bx, by, bw, bh = within or (0, 0, iw, ih)
    Ww, Wh = (bw, bw / a) if bw / bh < a else (bh * a, bh)
    samples = np.linspace(t0, t1, 9)
    F = [faces_at(t) for t in samples]
    dx, dy = direction(out_tr)
    def win(scale, need, pref=(0.5, 0.5)):
        w, h = Ww * scale, Wh * scale
        if need is None:
            X = bx + (bw - w) * pref[0]; Y = by + (bh - h) * pref[1]; return (X, Y, w, h), True
        pw, ph = PAD * w, PAD * h
        X, okx = _place(need[0] - pw, need[2] + pw, w, bx, bx + bw, pref[0])
        Y, oky = _place(need[1] - ph, need[3] + ph, h, by, by + bh, pref[1])
        return (X, Y, w, h), okx and oky
    allidx = list(range(n_faces))
    if REVEAL:
        return _reveal_plan(img_wh, cell_wh, within, faces_at, t0, t1, n_faces, F, PAD, Ww, Wh, bx, by, bw, bh, dx, dy)
    if n_faces == 0:
        pref0 = (0.5 - 0.5 * dx, 0.5 - 0.5 * dy) if (dx or dy) else (0.5, 0.5)
        w0, _ = win(1.0, None); w1, _ = win(PUSH, None, (0.5 + 0.3 * dx, 0.5 + 0.3 * dy))
        return Plan('push_in', [(0, w0), (1, w1)], 'io', t0, t1, faces_at, lambda t: [])
    U = _union([b for fs in F for b in fs])           # where every face goes over the whole cut
    fits_all = (U[2] - U[0]) * (1 + 2 * PAD) <= Ww and (U[3] - U[1]) * (1 + 2 * PAD) <= Wh
    if fits_all:
        slack_x = Ww - (U[2] - U[0]) * (1 + 2 * PAD); slack_y = Wh - (U[3] - U[1]) * (1 + 2 * PAD)
        tight = min(slack_x / Ww, slack_y / Wh) < 0.10
        if n_faces >= 2 and tight:
            lead = F[0][0]
            ws, _ = win(PULL, lead); we, _ = win(1.0, U)
            return Plan('pull_back', [(0, ws), (1, we)], 'io', t0, t1, faces_at,
                        lambda t, T=t0, L=t1 - t0: [0] if (t - T) / L < 0.5 else allidx, why='faces fill the cell; reveal')
        if n_faces == 1 or splash or (out_tr or '').startswith(('zoom', 'iris')) or (dx == 0 and dy == 0 and not in_tr):
            # scale so U still fits
            s_need = max((U[2] - U[0]) * (1 + 2 * PAD) / Ww, (U[3] - U[1]) * (1 + 2 * PAD) / Wh)
            s1 = max(PUSH, s_need)
            w0, _ = win(1.0, U); w1, _ = win(s1, U)
            return Plan('push_in', [(0, w0), (1, w1)], 'io', t0, t1, faces_at, lambda t: allidx)
        # pan along the slack toward the outgoing transition's direction
        horiz = (abs(dx) >= abs(dy) and slack_x / Ww >= 0.04) or slack_y / Wh < 0.04
        s = 0.94 if max(slack_x / Ww, slack_y / Wh) < 0.08 else 1.0   # a touch of zoom gives room to move
        sg = (dx if horiz else dy) or 1
        p0 = (0.0, 0.5) if horiz else (0.5, 0.0); p1 = (1.0, 0.5) if horiz else (0.5, 1.0)
        if sg < 0: p0, p1 = p1, p0
        w0, _ = win(s, U, p0); w1, _ = win(s, U, p1)
        move = 'whip' if 'whip' in (out_tr or '') else 'drift'
        return Plan(move, [(0, w0), (1, w1)], 'in' if move == 'whip' else 'io', t0, t1, faces_at, lambda t: allidx)
    fit = lambda b, s=1.0: (b[2] - b[0]) * (1 + 2 * PAD) <= Ww * s and (b[3] - b[1]) * (1 + 2 * PAD) <= Wh * s
    Us = [_union(fs) for fs in F]
    if all(fit(u_) for u_ in Us):
        # the faces fit together at every moment but move more than the cell allows: follow them (focus tracking)
        keys = [(k / (len(Us) - 1), win(0.97 if all(fit(u_, 0.97) for u_ in Us) else 1.0, u_)[0]) for k, u_ in enumerate(Us)]
        return Plan('follow', keys, 'io', t0, t1, faces_at, lambda t: allidx, why='faces move; window tracks them')
    # faces do not fit together: pan / tilt between them (each must fit alone at every moment)
    singles = [_union([fs[i] for fs in F]) for i in allidx]
    lone = [i for i in allidx if not all(fit(fs[i]) for fs in F)]
    if lone:
        return Plan('needs_bigger_cell', [(0, win(1.0, None)[0]), (1, win(1.0, None)[0])], 'io', t0, t1, faces_at,
                    lambda t: [], fits=False, why=f'face {lone} alone is larger than the cell window')
    ox = (U[2] - U[0]) * (1 + 2 * PAD) - Ww; oy = (U[3] - U[1]) * (1 + 2 * PAD) - Wh
    horiz = ox / Ww >= oy / Wh
    key = (lambda b: (b[0] + b[2]) / 2) if horiz else (lambda b: (b[1] + b[3]) / 2)
    order = sorted(allidx, key=lambda i: key(singles[i]))
    sg = (dx if horiz else dy)
    if sg < 0: order = order[::-1]
    A, B = order[0], order[-1]
    sa = singles[A] if fit(singles[A]) else F[0][A]; sb = singles[B] if fit(singles[B]) else F[-1][B]
    wa, _ = win(1.0, sa); wb, _ = win(1.0, sb)
    keys = [(0.0, wa), (0.22, wa), (0.78, wb), (1.0, wb)]
    # tiny push inside the holds so the hold itself keeps moving
    def shrink(w, k):
        X, Y, W_, H_ = w; return (X + W_ * (1 - k) / 2, Y + H_ * (1 - k) / 2, W_ * k, H_ * k)
    keys = [(0.0, wa), (0.22, shrink(wa, 0.97)), (0.78, shrink(wb, 0.97)), (1.0, wb)]
    active = lambda t, T=t0, L=t1 - t0: [A] if (t - T) / L <= 0.22 else ([B] if (t - T) / L >= 0.78 else [])
    return Plan('pan_h' if horiz else 'tilt_v', keys, 'io', t0, t1, faces_at, active,
                why=f'faces {order} spread {"side to side" if horiz else "top to bottom"}')


def window_misses(plan, t, cell_wh, pad=0.0):
    """[(face index, fraction outside)] for the faces the plan promises at t (QA)."""
    X, Y, W, H = plan.window(t)
    fs = plan.faces_at(t); out = []
    for i in plan.expected(t):
        b = fs[i]; bw, bh = b[2] - b[0], b[3] - b[1]
        ix = max(0.0, min(b[2], X + W - pad * W) - max(b[0], X + pad * W)); iy = max(0.0, min(b[3], Y + H - pad * H) - max(b[1], Y + pad * H))
        frac = 1 - (ix * iy) / max(bw * bh, 1e-6)
        if frac > 0.05:
            out.append((i, round(frac, 3)))
    return out

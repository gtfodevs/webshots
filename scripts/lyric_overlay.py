#!/usr/bin/env python3
"""Floating lyric overlay (shared: comic, music videos, explainers).

Captions are NOT inside panels: they live on one layer above pages and transitions, follow lyric timing only,
and carry across panel changes and page turns. Page / panel timing never waits on a caption.

  cues = cues_from_lines(timeline['lyrics'], t0, t1)
  ov = Overlay(orient, (W, H), faces_fn, font_path, style)   # faces_fn(song_t) -> [[x0, y0, x1, y1] frame px]
  ov.plan(cues)                                              # placement path per cue (avoids tracked faces)
  frame = ov.draw(frame, song_t)
  ov.rect_at(song_t) -> [(cue, rect)]                       # QA uses the same geometry

Placement: candidate slots in a lower band, an upper band and across the gutters (16:9), or inside the Short's
safe band (clear of platform UI: top 10 %, bottom 22 %, right 12 %). Each cue picks, per 0.25 s step, the slot
with the least face overlap plus a switching penalty (dynamic programming), then slides between slots with an
0.35 s ease, so it moves smoothly when the layer beneath moves. Style 'deco_gold': navy box, double gold rule,
chevron end tabs, comic lettering in cream.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

STEP = 0.25        # s between placement decisions
SLIDE = 0.35       # s ease between two slots
FADE = 0.16
HOP_FADE = 0.10
SWITCH_COST = 0.08
VMAX = 1400        # px/s caption glide speed limit
TRAVEL = 0.0004
HOP_COST = 2.0     # a fade-hop costs about as much as 20 % face cover for one frame    # cost per px moved (keeps the box still unless a face is coming)
MARGIN = 14        # px clearance kept from faces when planning (QA checks the bare box)
DENSE = 1 / 30     # s, face sampling for placement (video rate)
SHORT_UI = {'top': 0.10, 'bottom': 0.22, 'right': 0.12, 'left': 0.04}

STYLES = {
    'deco_gold': {'fill': (16, 18, 40), 'rule': (226, 180, 72), 'rule2': (120, 86, 24), 'text': (252, 240, 206),
                  'shadow': (0, 0, 0), 'alpha': 238},
    'plain': {'fill': (250, 246, 230), 'rule': (20, 20, 20), 'rule2': (20, 20, 20), 'text': (20, 20, 20),
              'shadow': (0, 0, 0), 'alpha': 255},
}


def cues_from_lines(lines, t0=-1e9, t1=1e9, min_dur=0.9, tail=0.30):
    """[{text, at, until}] from timeline lyric lines ({t, end, text}): up from the first sung word until shortly
    after the line ends (or just before the next line starts). Pure lyric timing."""
    L = sorted([l for l in lines if t0 - 0.2 <= l['t'] < t1], key=lambda l: l['t'])
    out = []
    for i, l in enumerate(L):
        nxt = L[i + 1]['t'] if i + 1 < len(L) else 1e9
        until = min(l.get('end', l['t'] + 2.5) + tail, nxt - 0.05)
        until = max(until, l['t'] + min_dur)
        out.append({'text': clean(l['text']), 'at': round(max(l['t'], t0), 3), 'until': round(min(until, t1), 3)})
    return out


def clean(s):
    import re
    return re.sub(r'^\([^)]*\)\s*', '', s).replace('\u2019', "'").upper()


def _wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if font.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


class Overlay:
    def __init__(self, orient, size, faces_fn, font_path, style='deco_gold', px=None, obstacles_fn=None):
        self.obstacles_fn = obstacles_fn
        self.orient, (self.W, self.H) = orient, size
        self.faces_fn, self.style = faces_fn, STYLES.get(style, STYLES['deco_gold'])
        self.px = px or (46 if orient == 'landscape' else 52)
        self.font = ImageFont.truetype(font_path, self.px)
        self.paths = []
        W, H = self.W, self.H
        if orient == 'landscape':
            self.band = (0.04 * W, 0.05 * H, 0.96 * W, 0.95 * H)
            self.maxw = 0.56 * W
        else:
            self.band = (SHORT_UI['left'] * W, SHORT_UI['top'] * H, (1 - SHORT_UI['right']) * W, (1 - SHORT_UI['bottom']) * H)
            self.maxw = (1 - SHORT_UI['left'] - SHORT_UI['right']) * W * 0.94

    # ---------------------------------------------------------------- geometry
    def box_size(self, text):
        lines = _wrap(text, self.font, self.maxw - 2 * self.pad())
        lh = int(self.px * 1.08)
        w = max(self.font.getlength(l) for l in lines) + 2 * self.pad() + 2 * self.tab()
        h = lh * len(lines) + 2 * self.pad() * 0.8
        return int(w), int(h), lines

    def pad(self):
        return int(self.px * 0.42)

    def tab(self):
        return int(self.px * 0.36)

    def slots(self, w, h):
        """Candidate positions: lower band first (classic caption row), then upper band, then the gutter rows
        between (16:9: the box may cross gutters); 4 x positions per row. Order = preference."""
        x0, y0, x1, y1 = self.band
        xs = [x0 + (x1 - x0 - w) * f for f in ((0.5, 0.0, 1.0, 0.25, 0.75) if self.orient == 'landscape' else (0.5, 0.0, 1.0))]
        fr = (1.0, 0.0, 0.5, 0.75, 0.25) if self.orient == 'landscape' else (1.0, 0.0, 0.36, 0.66, 0.5, 0.18, 0.84)
        out = []
        for f in fr:
            y = y0 + (y1 - y0 - h) * f
            for x in xs:
                out.append((max(x0, min(x, x1 - w)), max(y0, min(y, y1 - h)), w, h))
        return out

    @staticmethod
    def overlap(r, faces, margin=0.0):
        x, y, w, h = r
        x, y, w, h = x - margin, y - margin, w + 2 * margin, h + 2 * margin
        s = 0.0
        for f in faces:
            ix = max(0.0, min(x + w, f[2]) - max(x, f[0])); iy = max(0.0, min(y + h, f[3]) - max(y, f[1]))
            if ix * iy > 0:
                s = max(s, ix * iy / max((f[2] - f[0]) * (f[3] - f[1]), 1.0))
        return s

    def _faces(self, t):
        k = round(t / DENSE)
        if k not in self._fc:
            self._fc[k] = self.faces_fn(k * DENSE)
        return self._fc[k]

    def grid(self, w, h):
        """Fine candidate grid inside the safe band (x: 7 columns, y: half-box rows). Placement prefers the lower
        band, then the upper band, then anywhere between (across gutters)."""
        x0, y0, x1, y1 = self.band
        xs = np.linspace(x0, x1 - w, 7)
        ys = np.arange(y0, y1 - h + 1e-6, max(h / 2, 12))
        ys = np.append(ys, y1 - h) if ys[-1] < y1 - h - 1 else ys
        G = np.array([(x, y) for y in ys for x in xs])
        cx = (x0 + x1 - w) / 2
        pref = np.minimum(np.abs(G[:, 1] - (y1 - h)), np.abs(G[:, 1] - y0) + 0.25 * (y1 - y0)) / (y1 - y0) * 0.06 \
            + np.abs(G[:, 0] - cx) / (x1 - x0) * 0.03
        return G, pref

    def _cost_faces(self, G, w, h, faces):
        if not faces:
            return np.zeros(len(G))
        F = np.array(faces, float)
        m = MARGIN
        ix = np.clip(np.minimum(G[:, None, 0] + w + m, F[None, :, 2]) - np.maximum(G[:, None, 0] - m, F[None, :, 0]), 0, None)
        iy = np.clip(np.minimum(G[:, None, 1] + h + m, F[None, :, 3]) - np.maximum(G[:, None, 1] - m, F[None, :, 1]), 0, None)
        area = np.maximum((F[:, 2] - F[:, 0]) * (F[:, 3] - F[:, 1]), 1.0)
        return (ix * iy / area[None, :]).max(axis=1)

    def plan(self, cues):
        """Per cue, a continuous path sampled at video rate: dynamic programming over a fine grid of positions with
        cost = face overlap (x 10, with a MARGIN px clearance) + placement preference + travel (px), and a speed limit
        (VMAX px/s), so the box glides out of the way of faces that move (camera moves, living-panel reflow, page
        turns) and otherwise sits still. The path is then eased (short moving average) and re-checked."""
        self._fc = getattr(self, '_fc', {})
        self.paths = []
        for c in cues:
            w, h, lines = self.box_size(c['text'])
            G, pref = self.grid(w, h)
            # samples on the global video-frame grid (k / 30 s) so planning sees exactly the frames that render
            ts = np.arange(math.ceil(c['at'] / DENSE - 1e-6), math.floor(c['until'] / DENSE + 1e-6) + 1) * DENSE
            if len(ts) == 0:
                ts = np.array([c['at']])
            dmax = VMAX * DENSE
            dist = np.hypot(G[:, None, 0] - G[None, :, 0], G[:, None, 1] - G[None, :, 1])
            # beyond the glide speed a move is a HOP (quick fade out / fade in elsewhere): only when no gliding
            # path stays clear, e.g. a full-frame newcomer's face sweeping across the whole frame while it settles
            trans = np.where(dist <= dmax + 1e-6, dist * TRAVEL, HOP_COST)
            raw = [self._cost_faces(G, w, h, self._faces(t)) for t in ts]
            cost = [r * 100 + pref for r in raw]      # faces dominate every other term
            if self.obstacles_fn:      # soft: keep off SFX / other lettering when a face-free spot allows
                cost = [cv + self._cost_faces(G, w, h, self.obstacles_fn(t)) * 3 for cv, t in zip(cost, ts)]
            # frames where NO position in the safe band is clear of faces (e.g. a Short page mid-reflow fills the
            # whole band): the caption is hidden there (quick fade), never drawn over a face
            blocked = [float(t) for t, r in zip(ts, raw) if r.min() > 0]
            D = cost[0].copy(); bps = []
            for i in range(1, len(ts)):
                tot = D[None, :] + trans            # [to, from]
                j = tot.argmin(axis=1); bps.append(j)
                D = tot[np.arange(len(G)), j] + cost[i]
            k = int(D.argmin()); seq = [k]
            for j in reversed(bps):
                k = int(j[k]); seq.append(k)
            seq.reverse()
            P = G[seq].astype(float)
            if len(P) > 4:                          # ease: 5-sample moving average, keep any sample that clears faces better raw
                Q = P.copy()
                cut = [0] + [i for i in range(1, len(seq)) if dist[seq[i], seq[i - 1]] > dmax + 1e-6] + [len(P)]
                for a, b in zip(cut, cut[1:]):
                    for i in range(a, b):
                        Q[i] = P[max(a, i - 2):min(b, i + 3)].mean(axis=0)
                for i, t in enumerate(ts):
                    if self.overlap((Q[i][0], Q[i][1], w, h), self._faces(t)) > self.overlap((P[i][0], P[i][1], w, h), self._faces(t)):
                        Q[i] = P[i]
                P = Q
            hops = [i for i in range(1, len(seq)) if dist[seq[i], seq[i - 1]] > dmax + 1e-6]
            self.paths.append({'cue': c, 'lines': lines, 'ts': ts, 'P': P, 'size': (w, h), 'hops': [float(ts[i]) for i in hops], 'blocked': blocked})
        return self.paths

    def _pos(self, p, t):
        ts, P = p['ts'], p['P']
        i = int(np.searchsorted(ts, t, side='right')) - 1
        if 0 <= i < len(ts) - 1 and any(abs(h - ts[i + 1]) < 1e-6 for h in p.get('hops', [])):
            x, y = P[i]          # never interpolate across a hop
        else:
            x = float(np.interp(t, ts, P[:, 0])); y = float(np.interp(t, ts, P[:, 1]))
        return (x, y) + tuple(p['size'])

    def rect_at(self, t):
        out = []
        for p in self.paths:
            c = p['cue']
            if c['at'] <= t < c['until']:
                out.append((p, self._pos(p, t)))
        return out

    # ---------------------------------------------------------------- drawing
    def _tile(self, p):
        if '_tile' in p:
            return p['_tile']
        st = self.style; w, h = p['size']; tab = self.tab(); pad = self.pad()
        im = Image.new('RGBA', (w + 12, h + 12), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        poly = [(tab, 0), (w - tab, 0), (w, h / 2), (w - tab, h), (tab, h), (0, h / 2)]
        d.polygon([(x + 8, y + 8) for x, y in poly], fill=st['shadow'] + (150,))
        d.polygon(poly, fill=st['fill'] + (st['alpha'],))
        d.line(poly + [poly[0]], fill=st['rule'] + (255,), width=4)
        inset = [(tab + 6, 7), (w - tab - 6, 7), (w - 9, h / 2), (w - tab - 6, h - 7), (tab + 6, h - 7), (9, h / 2)]
        d.line(inset + [inset[0]], fill=st['rule2'] + (255,), width=2)
        lh = int(self.px * 1.08); y = pad * 0.8
        for l in p['lines']:
            lw = self.font.getlength(l)
            d.text(((w - lw) / 2 + 2, y + 2), l, font=self.font, fill=(0, 0, 0, 200))
            d.text(((w - lw) / 2, y), l, font=self.font, fill=st['text'] + (255,))
            y += lh
        p['_tile'] = im
        return im

    @staticmethod
    def alpha(p, t):
        c = p['cue']
        a = min(1.0, (t - c['at']) / FADE, (c['until'] - t) / FADE)
        for hp in p.get('hops', []):
            a = min(a, abs(t - hp) / HOP_FADE)
        for b in p.get('blocked', []):
            if abs(t - b) < DENSE / 2 + 1e-6:
                return 0.0
            a = min(a, (abs(t - b) - DENSE / 2) / HOP_FADE)
        return max(0.0, a)

    def draw(self, img, t):
        rs = self.rect_at(t)
        if not rs:
            return img
        img = img.convert('RGB').copy()
        for p, r in rs:
            c = p['cue']
            a = self.alpha(p, t)
            dy = (1 - min(1.0, (t - c['at']) / FADE)) * 14
            tile = self._tile(p)
            if a < 1:
                tile = tile.copy(); tile.putalpha(tile.getchannel('A').point(lambda v: int(v * max(a, 0))))
            img.paste(tile, (int(round(r[0])), int(round(r[1] + dy))), tile)
        return img

    # ---------------------------------------------------------------- QA
    def problems(self, t0, t1, fps=10, face_tol=0.02):
        """[(t, text, kind, value)]: 'face' overlap share > face_tol, 'clipped' outside the safe band."""
        out = []
        x0, y0, x1, y1 = self.band
        for t in np.arange(t0, t1, 1.0 / fps):
            faces = self.faces_fn(t)
            for p, r in self.rect_at(t):
                if self.alpha(p, t) < 0.05:      # invisible (fade in/out, mid-hop)
                    continue
                ov = self.overlap(r, faces)
                if ov > face_tol:
                    out.append((round(float(t), 2), p['cue']['text'], 'face', round(ov, 3)))
                if r[0] < x0 - 1 or r[1] < y0 - 1 or r[0] + r[2] > x1 + 1 or r[1] + r[3] > y1 + 1:
                    out.append((round(float(t), 2), p['cue']['text'], 'clipped', 1.0))
            # two captions overlapping each other
            rs = self.rect_at(t)
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    a, b = rs[i][1], rs[j][1]
                    if min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0]) and min(a[1] + a[3], b[1] + b[3]) > max(a[1], b[1]):
                        out.append((round(float(t), 2), rs[i][0]['cue']['text'], 'caption overlap', 1.0))
        return out

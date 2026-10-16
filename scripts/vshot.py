"""Native 9:16 trailer shots (Jason 2026-10-14): a Short glimpse is built straight from source clips, never from the
16:9 page layouts. One clip cropped to its subject fills the frame, or two related clips stack top/bottom (9:8 each).
Faces stay whole; the crop pans ONE way, linearly, a few % (reveal rule); clips play forward only, then hold."""
import os, subprocess
import numpy as np
from PIL import Image, ImageDraw

GUTTER = 8
PAN = 0.05   # fraction of source width drifted over a glimpse


def _decode(path, t_in, dur, fps):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t_in:.3f}', '-i', path, '-t', f'{dur + 0.5:.3f}',
                        '-map', '0:v:0', '-vf', f'framerate=fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       capture_output=True, check=True)
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
                                    '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.split()[0].split(',')[:2])
    a = np.frombuffer(p.stdout, np.uint8)
    n = len(a) // (w * h * 3)
    return [Image.fromarray(a[i * w * h * 3:(i + 1) * w * h * 3].reshape(h, w, 3)) for i in range(n)], (w, h)


class Cell:
    def __init__(self, c, box, dur, fps):
        self.box, self.fps = box, fps
        self.c, self.frames = c, None   # decoded on first render (geometry alone serves the lyric planner)
        w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
                                        '-of', 'csv=p=0', c['path']], capture_output=True, text=True).stdout.split()[0].split(',')[:2])
        self.w, self.h = w, h
        bw, bh = box[2], box[3]
        a = bw / bh
        ch = h * c.get('zoom', 1.0); cw = ch * a
        if cw > w:
            cw = w; ch = w / a
        self.cw, self.ch = cw, ch
        self.y0 = min(max(c.get('fy', 0.0) * h, 0), h - ch)
        faces = [r for r in c.get('faces', [])]
        lo, hi = 0.0, w - cw
        if faces:
            fx0 = min(f[0] for f in faces) * w; fx1 = max(f[2] for f in faces) * w
            lo, hi = max(lo, min(fx1 - cw, hi)), min(hi, max(fx0, lo))
            if lo > hi:
                lo = hi = min(max((fx0 + fx1) / 2 - cw / 2, 0), w - cw)
        x_s = min(max(c.get('fx', 0.5) * w - cw / 2, lo), hi)
        d = PAN * w * (1 if x_s + cw / 2 < w / 2 else -1)   # drift toward the image centre: one way, linear
        x_e = min(max(x_s + d, lo), hi)
        self.x_s, self.x_e, self.dur = x_s, x_e, max(dur, 1e-3)
        self.faces = faces

    def x0(self, t):
        return self.x_s + (self.x_e - self.x_s) * min(max(t / self.dur, 0), 1)

    def render(self, frame, t):
        if self.frames is None:
            self.frames = _decode(self.c['path'], self.c.get('in', 0.0), self.dur, self.fps)[0]
        src = self.frames[min(int(t * self.fps), len(self.frames) - 1)]
        x0 = self.x0(t)
        img = src.resize((self.box[2], self.box[3]), Image.LANCZOS, box=(x0, self.y0, x0 + self.cw, self.y0 + self.ch))
        frame.paste(img, (self.box[0], self.box[1]))

    def face_px(self, t):
        x0 = self.x0(t); sx = self.box[2] / self.cw; sy = self.box[3] / self.ch
        return [[self.box[0] + (f[0] * self.w - x0) * sx, self.box[1] + (f[1] * self.h - self.y0) * sy,
                 self.box[0] + (f[2] * self.w - x0) * sx, self.box[1] + (f[3] * self.h - self.y0) * sy] for f in self.faces]


class VShot:
    def __init__(self, cells, size, dur, fps):
        W, H = size
        n = len(cells)
        hh = (H - GUTTER * (n - 1)) // n
        boxes = [(0, k * (hh + GUTTER), W, hh if k < n - 1 else H - k * (hh + GUTTER)) for k in range(n)]
        self.size = size
        self.cells = [Cell(c, b, dur, fps) for c, b in zip(cells, boxes)]

    def free(self):
        for c in self.cells:
            c.frames = None

    def frame(self, t):
        f = Image.new('RGB', self.size, (12, 10, 8))
        for c in self.cells:
            c.render(f, t)
        return f

    def faces(self, t):
        return [b for c in self.cells for b in c.face_px(t)]


def resolve_cells(spec, resolve, vs):
    """vs: [{'id': 'f02', 'fx': .5, ...}, ...] -> cells with clip path, in point and face boxes from the spec."""
    units = {u['id']: u for p in spec['pages'] for u in p.get('panels', [])}
    out = []
    for c in vs:
        u = units.get(c['id'], {})
        src = c.get('src') or (u.get('clip') or {}).get('src') or f"clips/v5/{c['id']}.mp4"
        faces = c.get('faces')
        if faces is None:
            faces = [r['box'] for r in u.get('focusRegions', []) if r.get('face') or 'face' in r.get('label', '').lower()]
        out.append(dict(c, path=resolve(spec, src), faces=faces, **({'in': (u.get('clip') or {}).get('in', 0.0)} if 'in' not in c else {})))
    return out

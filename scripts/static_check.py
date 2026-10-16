#!/usr/bin/env python3
"""Find near-static stretches in a rendered video by frame differencing (shared pipeline QA gate).
usage: static_check.py VIDEO [--max 0.4] [--thresh 0.35] [--json out.json]
A frame is 'static' when the mean absolute luma difference to the previous frame (0-255 scale, at 192 px wide)
is below --thresh. Stretches of consecutive static frames longer than --max seconds FAIL (exit 1)."""
import argparse, json, subprocess, sys
import numpy as np


def diffs(path, w=192):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate',
                        '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(',')
    W, H = int(p[0]), int(p[1]); n, d = p[2].split('/'); fps = float(n) / float(d)
    h = int(round(H * w / W / 2) * 2)
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    prev, out = None, []
    sz = w * h
    while True:
        b = proc.stdout.read(sz)
        if len(b) < sz: break
        f = np.frombuffer(b, np.uint8).astype(np.int16)
        out.append(0.0 if prev is None else float(np.abs(f - prev).mean()))
        prev = f
    proc.wait()
    return np.array(out), fps


def stretches(d, fps, thresh, min_s):
    st, res = None, []
    for i, v in enumerate(list(d) + [1e9]):
        if i > 0 and v < thresh:
            st = i if st is None else st
        else:
            if st is not None and (i - st) / fps > min_s:
                res.append((round(st / fps, 2), round(i / fps, 2), round((i - st) / fps, 2), round(float(np.mean(d[st:i])), 3)))
            st = None
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--max', type=float, default=0.4)
    ap.add_argument('--thresh', type=float, default=0.35); ap.add_argument('--json'); ap.add_argument('--skip-tail', type=float, default=0.0,
                    help='ignore the last N s (end card hold is allowed to settle)')
    a = ap.parse_args()
    d, fps = diffs(a.video)
    dur = len(d) / fps
    res = [r for r in stretches(d, fps, a.thresh, a.max) if r[0] < dur - a.skip_tail]
    for s, e, L, m in res:
        print(f'  FAIL static {s:7.2f}-{e:7.2f}s ({L:.2f}s, mean diff {m})')
    if a.json:
        json.dump({'video': a.video, 'fps': fps, 'max': a.max, 'thresh': a.thresh, 'stretches': res,
                   'diff': [round(x, 3) for x in d]}, open(a.json, 'w'))
    print(f"static check: {'PASS' if not res else f'{len(res)} static stretch(es) > {a.max}s'} ({a.video})")
    sys.exit(1 if res else 0)

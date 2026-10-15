#!/usr/bin/env python3
"""The Pharaoh's Waking Up: deterministic assembly (full 16:9 video + 9:16 Short).

  python3 assemble.py --root /workspace/pharaoh full|short|all [--jobs 4]

Composes the shot list with scripts/music_fx.py (snap, overlays, parallax, typography):
  grok_clip        -> picked clip (clip_picks.json), scaled, no zoom/push; trims from TRIM; never overlays.
  still_parallax   -> STILLS source split into fg/bg (music_fx.make_layers), 'locked_subtle' parallax + overlay preset.
  scenery_overlays -> refs/bg_<loc>.jpg static plate + overlay preset (crypt / desert_night / tomb_embers).
  end_card         -> logo over dunes + desert_night, fade to black on the last 1.5 s.
Cuts snap with music_fx SNAP_PRESETS['beats'] (drops > beat grid). Punch on cuts = short exposure flash
(strong on drops, light on kicks) and exposure pops on snapped punch_hits; never a zoom. Beat head-bob layer:
not in the engine, skipped. Intro: out/intro_v1.mp4 replaces 0-6.5 s. Every shot renders to its own
segment in parallel, then concat + song mux. Same inputs -> same frames.
"""
import argparse, json, os, subprocess, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../../scripts')))
import music_fx as fx  # noqa: E402

FPS = 30
INTRO_END = 6.5
TRIM = {'s15': 2.0, 's36': 2.0, 's43': 2.0}          # dark eyes in the first ~2 s
STILLS = {'s05': 'panels/s06_start_v2.jpg', 's11': 'panels/s24_start_v2.jpg', 's19': 'panels/s20_start_v2.jpg',
          's27': 'panels/s21_start_v2.jpg', 's40': 'panels/s50_start_v2.jpg', 's54': 'pharaoh_front',
          's59': 'refs/bg_chamber.jpg'}
SHORT_IDS = ('s25', 's38')                           # inclusive, then end card
SHORT_CARD = 5.0
SHORT_BOOST = {'s25'}                                 # BAM shot (only BAM in either video)
R = None                                              # project root


def P(p): return os.path.join(R, p)


def load():
    sl = json.load(open(P('shotlist.json'))); picks = json.load(open(P('clip_picks.json')))
    tl = json.load(open(P('audio/analysis.json')))
    shots = [dict(s, hits=[{'t': h} for h in s.get('punch_hits', [])]) for s in sl['shots']]
    shots = fx.snap_shots(shots, tl, 'beats', FPS)
    shots[0]['t'] = 0.0; shots[-1]['end'] = sl['duration']
    drops = tl['drops']; kicks = [k['t'] if isinstance(k, dict) else k for k in tl['kicks']]
    drops = [d['t'] if isinstance(d, dict) else d for d in drops]
    for s in shots:
        s['clip'] = picks.get(s['id'])
        s['flash'] = 0.55 if any(abs(s['t'] - d) < 1.5 / FPS for d in drops) else (0.18 if any(abs(s['t'] - k) < 1.5 / FPS for k in kicks) else 0)
        if s['t'] == 0: s['flash'] = 0
    return sl, shots


# ------------------------------------------------------------------ plates
def fit(img, W, H):
    return np.asarray(Image.fromarray(img).convert('RGB').resize((W, H), Image.LANCZOS))


def still_layers(sid, W, H):
    src = STILLS[sid]
    if src == 'pharaoh_front':  # engine-made layers: Pharaoh cutout over the hall plate
        fg = np.asarray(Image.open(P('panels/layers/fg.png')).convert('RGBA'))
        bg = fit(np.asarray(Image.open(P('refs/bg_hall.jpg'))), W, H)
        sc = 0.92 * H / fg.shape[0]; fgr = np.asarray(Image.fromarray(fg).resize((int(fg.shape[1] * sc), int(fg.shape[0] * sc)), Image.LANCZOS))
        canvas = np.zeros((H, W, 4), np.uint8); x = (W - fgr.shape[1]) // 2; y = H - fgr.shape[0]
        canvas[y:y + fgr.shape[0], max(0, x):x + fgr.shape[1]] = fgr[:, max(0, -x):W - x]
        return bg, canvas
    d = P(f'tmp/asm/layers_{sid}'); fg_p, bg_p, _ = fx.make_layers(P(src), d)
    return fit(np.asarray(Image.open(bg_p)), W, H), np.asarray(Image.open(fg_p).convert('RGBA').resize((W, H), Image.LANCZOS))


def comp(bg, fg, par, t, W, H):
    c = fx.shift(bg, *par.offset(0, t)).astype(np.float32) / 255
    f = fx.shift(fg, *par.offset(2, t)).astype(np.float32) / 255
    a = f[..., 3:4]; c = c * (1 - a) + f[..., :3] * a
    return (np.clip(c, 0, 1) * 255).astype(np.uint8), f[..., 3]


def clip_reader(s, W, H):
    path = P(s['clip']); dur = s['end'] - s['t']; off = TRIM.get(s['id'], 0.0)
    cd = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]))
    avail = cd - off - 0.05
    if avail < 2.0: raise SystemExit(f"{s['id']}: clip {path} too short ({cd:.2f}s)")
    speed = min(1.0, avail / dur)  # only slows if the trimmed clip is shorter than the shot (logged)
    if speed < 1: print(f"  note {s['id']}: trimmed clip {avail:.2f}s < shot {dur:.2f}s, played at {speed:.3f}x", flush=True)
    vf = f'setpts=PTS/{speed:.5f},fps={FPS},scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration=1'
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(off), '-i', path, '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    last = [None]
    def nxt():
        b = p.stdout.read(W * H * 3)
        if len(b) == W * H * 3: last[0] = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        return last[0]
    return nxt, p


# ------------------------------------------------------------------ per shot render
def cues_for(s, short=False):
    tx = s.get('text') or {}
    if not tx: return []
    if s['id'] == 's01': return []  # intro logo covers s01
    t0 = max(s['t'], INTRO_END) if not short else s['t']
    if tx['kind'] == 'sfx':
        return [{'kind': 'sfx', 't': s['t'], 'end': s['t'] + 0.9, 'text': tx['text'], 'preset': 'sfx', 'cue': tx.get('cue')}]
    lead = 0.25 if tx['kind'] == 'caption' else 0.0
    end = s['end'] - 0.15
    if s['type'] == 'end_card': end = s['end'] - 2.0
    return [{'kind': tx['kind'], 't': t0 + lead, 'end': end, 'text': tx['text'], 'preset': tx.get('preset')}]


def crop_x(frame_mask, Wsrc, cw):
    """Fixed per-shot vertical crop: center on the subject mask centroid (subject-weighted), clamped."""
    if frame_mask is None or frame_mask.sum() < 1: return (Wsrc - cw) // 2
    cols = frame_mask.sum(0); cx = float((cols * np.arange(len(cols))).sum() / cols.sum())
    return int(np.clip(cx - cw / 2, 0, Wsrc - cw))


def subject_mask(rgb):
    from rembg import remove, new_session
    global _SESS
    try: _SESS
    except NameError: _SESS = new_session('isnet-general-use')
    small = Image.fromarray(rgb).resize((640, 360))
    a = np.asarray(remove(small, session=_SESS))[:, :, 3]
    return np.asarray(Image.fromarray(a).resize((rgb.shape[1], rgb.shape[0]))).astype(np.float32) / 255


def render_shot(job):
    s, mode, out, seg_t0, seg_t1 = job['shot'], job['mode'], job['out'], job['t0'], job['t1']
    W, H = 1920, 1080                              # composition plate (16:9) for both modes
    OW, OH = (1920, 1080) if mode == 'full' else (1080, 1920)
    n = int(round(seg_t1 * FPS)) - int(round(seg_t0 * FPS))
    seed = int(s['id'][1:])
    typ, ovs, nxt, proc, bg, fg, par = None, None, None, None, None, None, None
    if s['type'] == 'grok_clip':
        nxt, proc = clip_reader(s, W, H)
    else:
        ovs = fx.build_overlays(s.get('overlay') or 'crypt', W, H, seed)
        if s['type'] == 'still_parallax':
            bg, fg = still_layers(s['id'], W, H); par = fx.Parallax('locked_subtle', seed, W / 1280)
        else:
            loc = 'dunes' if s['type'] == 'end_card' else s['location']
            plate = fit(np.asarray(Image.open(P(s['bg'] if s['bg'].startswith('refs') else f'refs/bg_{loc}.jpg'))), W, H)
            if s['type'] == 'end_card':
                plate = (plate * 0.45).astype(np.uint8)
                logo = Image.open(P('refs/logo-MASTER.jpg')).convert('RGB'); lw = int(W * 0.42)
                logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
                im = Image.fromarray(plate); m = Image.new('L', logo.size, 0)
                ImageDraw.Draw(m).rounded_rectangle([0, 0, logo.width - 1, logo.height - 1], 40, fill=255)
                im.paste(logo, ((W - lw) // 2, int(H * 0.40 - logo.height / 2)), m); plate = np.asarray(im)
            bg = plate
    # crop + face/busy map from the representative frame (computed once, deterministic)
    first = None
    frames_tmp = []
    def base(k, t):
        lt = t - s['t']
        if nxt is not None: return nxt(), None
        if fg is not None: f, m = comp(bg, fg, par, lt, W, H)
        else: f, m = bg, None
        return fx.apply_overlays(f, ovs, lt), m
    cues = [c for c in cues_for(s, mode == 'short') if c['end'] > seg_t0]
    if mode == 'short' and s['type'] == 'end_card':
        cues = [{'kind': 'caption', 't': seg_t0 + 0.4, 'end': seg_t1 - 1.0, 'text': s['text']['text'], 'prefer': ('bottom',)}]
    if cues: typ = fx.TypeLayer(OW, OH, cues)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{OW}x{OH}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-g', '30', out], stdin=subprocess.PIPE)
    cx = None; faces = None; busy = None; card_fade = s['type'] == 'end_card'
    # punch pops (exposure, not zoom): snapped hits on engine shots, flash on the cut itself
    pops = [(s['t'], s['flash'])] + ([(h['t'], 0.16) for h in s.get('hits', [])] if s['type'] != 'grok_clip' else [])
    for k in range(n):
        t = (int(round(seg_t0 * FPS)) + k) / FPS
        f, m = base(k, t)
        if cx is None:  # first frame: decide crop + text placement from the subject
            mm = m if m is not None else (subject_mask(f) if (mode == 'short' or cues) and s['type'] != 'end_card' else None)
            if mode == 'short':
                cw = int(W * OW / OH * H / H * (H / W) * W / W * 1) if False else int(round(H * OW / OH))  # 608 px of 1080 tall
                cx = crop_x(mm, W, cw); job_cx = cx
            else: cx = 0
            if cues:
                mv = mm if mm is not None else np.zeros((H, W), np.float32)
                if mode == 'short': mv = np.asarray(Image.fromarray((mv[:, cx:cx + cw] * 255).astype(np.uint8)).resize((OW, OH))).astype(np.float32) / 255
                busy = mv; ff_rgb = f if mode == 'full' else np.asarray(Image.fromarray(f[:, cx:cx + cw]).resize((OW, OH)))
                faces = fx.detect_faces(ff_rgb, (mv * 255).astype(np.uint8))
        if mode == 'short': f = np.asarray(Image.fromarray(f[:, cx:cx + int(round(H * OW / OH))]).resize((OW, OH), Image.LANCZOS))
        g = 1.0
        for pt, amt in pops:
            dt = t - pt
            if amt and 0 <= dt < 0.2: g += amt * (1 - fx.ease(dt / 0.2))
        if card_fade:
            g *= min(1, (t - s['t']) / 0.8) * min(1, max(0, (seg_t1 - t) / 1.5))
        if g != 1.0: f = np.clip(f.astype(np.float32) * g + (max(0, g - 1) * 60), 0, 255).astype(np.uint8)
        if typ: f = typ.draw(np.ascontiguousarray(f), t, faces, busy)
        ff.stdin.write(np.ascontiguousarray(f).tobytes())
    ff.stdin.close(); ff.wait()
    if proc: proc.kill()
    return {'id': s['id'], 'out': out, 'frames': n, 'crop_x': cx if mode == 'short' else None}


# ------------------------------------------------------------------ assemble
def build(mode, jobs):
    sl, shots = load()
    os.makedirs(P(f'tmp/asm/{mode}'), exist_ok=True)
    if mode == 'full':
        sel = shots; a0, a1 = 0.0, sl['duration']
    else:
        i0 = next(i for i, s in enumerate(shots) if s['id'] == SHORT_IDS[0]); i1 = next(i for i, s in enumerate(shots) if s['id'] == SHORT_IDS[1])
        sel = shots[i0:i1 + 1] + [dict(shots[-1])]
        a0 = sel[0]['t']; seam = sel[-2]['end']
        card = sel[-1]; card['end'] = seam + SHORT_CARD; card['t'] = seam
        a1 = card['end']
    work = []
    for i, s in enumerate(sel):
        t0, t1 = s['t'], s['end']
        if mode == 'full' and t1 <= INTRO_END: continue
        if mode == 'full': t0 = max(t0, INTRO_END)
        work.append({'shot': s, 'mode': mode, 'out': P(f'tmp/asm/{mode}/{i:02d}_{s["id"]}.mp4'), 't0': t0, 't1': t1})
    with Pool(jobs) as pool:
        res = pool.map(render_shot, work, chunksize=1)
    lst = P(f'tmp/asm/{mode}/concat.txt')
    with open(lst, 'w') as f:
        if mode == 'full': f.write(f"file '{P('out/intro_v1.mp4')}'\n")
        for r in res: f.write(f"file '{r['out']}'\n")
    out = P(f'out/pharaoh_{mode}_v1.mp4'); silent = P(f'tmp/asm/{mode}/video.mp4')
    if mode == 'full':  # intro is a different encode: re-encode the whole picture once
        subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-an', '-vf', f'fps={FPS},format=yuv420p',
                               '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', silent])
    else:
        subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-an', '-c', 'copy', silent])
    dur = a1 - a0
    af = 'afade=t=out:st=%.3f:d=0.6' % (dur - 0.6) if mode == 'short' else 'anull'
    subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-ss', f'{a0:.3f}', '-t', f'{dur:.3f}', '-i', P('audio/pharaoh.mp3'),
                           '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', af, '-c:a', 'aac', '-b:a', '256k', '-t', f'{dur:.3f}',
                           '-movflags', '+faststart', out])
    web = P(f'out/pharaoh_{mode}_v1_web.mp4')
    subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-preset', 'slow',
                           '-crf', '21', '-maxrate', '4M' if mode == 'full' else '6M', '-bufsize', '8M', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', web])
    contact(out, P(f'out/pharaoh_{mode}_v1_contact.jpg'), 24 if mode == 'full' else 16, mode)
    plan = {'mode': mode, 'audio': [round(a0, 3), round(a1, 3)], 'shots': [{'id': s['id'], 't': s['t'], 'end': s['end'], 'type': s['type'], 'clip': s.get('clip'),
            'cut_on': s.get('cut_on'), 'flash': s['flash'], 'trim': TRIM.get(s['id']), 'still': STILLS.get(s['id'])} for s in sel],
            'crops': {r['id']: r['crop_x'] for r in res if r['crop_x'] is not None}}
    json.dump(plan, open(P(f'out/pharaoh_{mode}_v1.plan.json'), 'w'), indent=1)
    print('done', out, f'{dur:.3f}s')


def contact(src, dst, n, mode):
    d = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src]))
    cols = 6 if mode == 'full' else 8; tw = 320 if mode == 'full' else 180; th = tw * 9 // 16 if mode == 'full' else tw * 16 // 9
    sheet = Image.new('RGB', (cols * tw, -(-n // cols) * th), (40, 0, 40)); dr = ImageDraw.Draw(sheet)
    for i in range(n):
        t = d * (i + 0.5) / n
        b = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', src, '-frames:v', '1', '-vf', f'scale={tw}:{th}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(Image.frombytes('RGB', (tw, th), b), (x, y)); dr.text((x + 5, y + 4), f'{t:.2f}s', fill=(255, 255, 0))
    sheet.save(dst, quality=88)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('what', choices=['full', 'short', 'all']); ap.add_argument('--root', default='/workspace/pharaoh')
    ap.add_argument('--jobs', type=int, default=4); a = ap.parse_args(); R = os.path.abspath(a.root)
    for m in (['full', 'short'] if a.what == 'all' else [a.what]): build(m, a.jobs)

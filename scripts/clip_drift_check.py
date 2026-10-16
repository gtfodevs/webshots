#!/usr/bin/env python3
"""Character-drift check for generated clips (Grok Imagine image-to-video / reference-to-video).

  python3 scripts/clip_drift_check.py SPEC [--ids f02,f16] [--clips 'clips/{id}_*.mp4'] [--out DIR] [--refs DIR]

For every clip, frames are sampled at 4 fps and each required focus region of the panel (faces: Uno, Aura, ...)
is tracked by normalised cross-correlation from the first frame. Per region and frame it measures:
  track   best NCC of the frame-0 crop near its last position (identity drift / morphing when it collapses)
  skin    share of human skin-tone pixels (YCbCr) in the tracked box - chrome robots are grey/steel, so a rising
          skin share means the face is turning human (the "Aura reads as human" failure)
  eyes    glowing red/green eye-pair present in the box (brand: red eyes) - losing them, or a red horizontal
          band replacing them, is the "dome turns into a visor" failure (visor = wide red blob)
  extra   number of glowing eye pairs in the whole frame vs frame 0 - more pairs = extra characters
With --refs DIR (locked character sheets: <name>-front.png, -side.png, -back.png), each face crop is also compared
to the named character's sheet views (best NCC over scales) for a reference-similarity score.
A clip is FLAGGED (exit 1, listed under "regenerate") when any rule trips; thresholds are below and in the report.
Writes DIR/drift-report.json and DIR/<clip>-drift.jpg (sampled frames with tracked boxes, red = tripped).
"""
import argparse, glob, json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_lib as C

FPS = 4
TRACK_MIN = 0.35      # NCC of the face crop vs frame 0 below this = the face changed (morph / swapped / gone)
SKIN_RISE = 0.18      # skin-tone share rising this much above frame 0 = face reading as human
SKIN_ABS = 0.35       # ... or simply this much skin in a robot face
EXTRA_PAIRS = 2       # eye pairs this many above frame 0, in >= 25% of samples = extra characters
VISOR_W = 3.5         # a single red blob this many times wider than tall where the eyes were = visor


def frames(path, fps=FPS, w=480):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:-2', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path],
                           capture_output=True, text=True).stdout.strip().split(',')
    h = round(w * int(probe[1]) / int(probe[0]) / 2) * 2
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = math.sqrt(float((a * a).sum() * (b * b).sum())) or 1.0
    return float((a * b).sum() / d)


def track(prev_box, tmpl, gray, search=0.3):
    """Best NCC of the frame-0 template near prev_box, over scales 0.9/1.0/1.1 of the current box (camera
    push-ins grow the face); returns (score, box). The template is never updated, so a morph shows as a drop."""
    x0, y0, x1, y1 = prev_box
    H, W = gray.shape
    best = (-1.0, prev_box)
    for sc in (0.9, 1.0, 1.1):
        w, h = max(8, int((x1 - x0) * sc)), max(8, int((y1 - y0) * sc))
        if w >= W or h >= H:
            continue
        t = np.asarray(Image.fromarray(tmpl.astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        step = max(2, int(min(w, h) / 8))
        for dy in range(-int(h * search), int(h * search) + 1, step):
            for dx in range(-int(w * search), int(w * search) + 1, step):
                X, Y = int(cx - w / 2 + dx), int(cy - h / 2 + dy)
                if X < 0 or Y < 0 or X + w > W or Y + h > H:
                    continue
                s_ = ncc(t, gray[Y:Y + h, X:X + w])
                if s_ > best[0]:
                    best = (s_, (X, Y, X + w, Y + h))
    return best


def skin_share(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    m = (cr > 135) & (cr < 175) & (cb > 85) & (cb < 130) & (y > 60) & (r > g) & (abs(r - g) > 12)
    return float(m.mean())


def eye_blobs(rgb):
    from scipy import ndimage as ndi
    a = rgb.astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    m = ((R > 190) & (R - G > 70) & (R - B > 70)) | ((G > 190) & (G - R > 50) & (G - B > 20))
    lab, n = ndi.label(ndi.binary_opening(m))
    out = []
    for i, sl in enumerate(ndi.find_objects(lab)):
        ys, xs = sl
        if (lab[sl] == i + 1).sum() >= 4:
            out.append(((xs.start + xs.stop) / 2, (ys.start + ys.stop) / 2, xs.stop - xs.start, ys.stop - ys.start))
    return out


def eye_pairs(blobs):
    n = 0; used = set()
    for i, (x1, y1, w1, h1) in enumerate(blobs):
        for j, (x2, y2, w2, h2) in enumerate(blobs):
            if j <= i or i in used or j in used:
                continue
            s = max(w1, h1, w2, h2); d = math.hypot(x2 - x1, y2 - y1)
            if 1.3 * s < d < 7 * s and abs(y2 - y1) < 0.45 * d:
                n += 1; used |= {i, j}
    return n


def ref_similarity(crop_gray, refs):
    best = -1.0
    for r in refs:
        for sc in (0.8, 1.0, 1.25):
            rr = np.asarray(Image.fromarray(r.astype(np.uint8)).resize((max(8, int(crop_gray.shape[1] * sc)), max(8, int(crop_gray.shape[0] * sc)))), np.float32)
            rr = rr[:crop_gray.shape[0], :crop_gray.shape[1]]
            if rr.shape == crop_gray.shape:
                best = max(best, ncc(crop_gray, rr))
    return best


def check_clip(spec, u, path, refs_dir=None):
    img = Image.open(C.resolve(spec, u['image'])).convert('RGB')
    F = frames(path)
    n, H, W = F.shape[:3]
    regs = [r for r in C.focus_regions(spec, u, img) if r.get('required', True)]
    reg, _ = C.register_cached(C.resolve(spec, u['image']), path, img, spec.get('fps', 30))
    rx, ry, rw, rh = reg
    def to_clip(box):   # normalised panel box -> clip px
        return [int(max(0, min(W, (box[0] * img.width - rx) / rw * W))), int(max(0, min(H, (box[1] * img.height - ry) / rh * H))),
                int(max(0, min(W, (box[2] * img.width - rx) / rw * W))), int(max(0, min(H, (box[3] * img.height - ry) / rh * H)))]
    gray = F.astype(np.float32).mean(-1)
    pairs0 = eye_pairs(eye_blobs(F[0]))
    res = {'clip': os.path.relpath(path, C.resolve(spec, '.')), 'frames': n, 'regions': [], 'flags': []}
    trips = {}
    for r in regs:
        if 'face' not in r['label'].lower() and 'head' not in r['label'].lower() and 'eyes' not in r['label'].lower():
            continue
        b = to_clip(r['box'])
        if b[2] - b[0] < 8 or b[3] - b[1] < 8:
            continue
        tmpl = gray[0, b[1]:b[3], b[0]:b[2]]
        sk0 = skin_share(F[0, b[1]:b[3], b[0]:b[2]])
        had_eyes = len(eye_blobs(F[0, b[1]:b[3], b[0]:b[2]])) > 0
        ref_imgs = []
        if refs_dir:
            name = r['label'].split()[0].lower()
            ref_imgs = [np.asarray(Image.open(p).convert('L'), np.float32) for p in sorted(glob.glob(os.path.join(refs_dir, f'{name}-*.png')))]
        rows, box = [], b
        for k in range(n):
            sc, box = track(box, tmpl, gray[k]) if k else (1.0, b)
            crop = F[k, box[1]:box[3], box[0]:box[2]]
            sk = skin_share(crop)
            bl = eye_blobs(crop)
            visor = any(w_ > VISOR_W * max(h_, 1) and w_ > 0.35 * (box[2] - box[0]) for _, _, w_, h_ in bl)
            row = {'t': round(k / FPS, 2), 'track': round(sc, 3), 'skin': round(sk, 3), 'eyes': len(bl) > 0, 'visor': visor}
            if ref_imgs:
                row['ref'] = round(ref_similarity(gray[k, box[1]:box[3], box[0]:box[2]], ref_imgs), 3)
            why = []
            if sc < TRACK_MIN: why.append(f'face changed (track {sc:.2f})')
            if sk > max(SKIN_ABS, sk0 + SKIN_RISE): why.append(f'reads human (skin {sk:.0%} vs {sk0:.0%} at 0 s)')
            if had_eyes and visor: why.append('eyes became a visor band')
            if why:
                trips.setdefault((r['label'], tuple(why[0].split(' (')[:1])), []).append(row['t'])
            row['why'] = why; row['box'] = box
            rows.append(row)
        res['regions'].append({'label': r['label'], 'rows': rows})
    # extra characters: glowing eye pairs beyond the cast this shot should have. Heuristic (lantern glints, eyes
    # turning toward camera also add pairs), so it asks for a human look ("review") instead of forcing a regen.
    cast = max(pairs0, sum(1 for r in regs if any(k in r['label'].lower() for k in ('face', 'head', 'eyes'))))
    extra = [round(k / FPS, 2) for k in range(n) if eye_pairs(eye_blobs(F[k])) >= cast + EXTRA_PAIRS]
    res['review'] = [f"possible extra characters at {extra[0]:.2f}-{extra[-1]:.2f}s ({len(extra)} samples)"] if len(extra) >= max(3, 0.25 * n) else []
    for (label, kind), ts in trips.items():
        if len(ts) >= 3:   # one/two-frame blips (blinks, flashes) are ignored
            res['flags'].append(f"{label}: {kind[0] if isinstance(kind, tuple) else kind} at {ts[0]:.2f}-{ts[-1]:.2f}s ({len(ts)} samples)")
    # sheet
    cols = min(8, n); idx = np.linspace(0, n - 1, cols).astype(int)
    sheet = Image.new('RGB', (cols * (W // 2), H // 2 + 20), (20, 20, 20)); d = ImageDraw.Draw(sheet)
    for c, k in enumerate(idx):
        im = Image.fromarray(F[k]); dd = ImageDraw.Draw(im)
        for rg in res['regions']:
            row = rg['rows'][k]
            dd.rectangle(row['box'], outline=(255, 40, 40) if row['why'] else (40, 255, 80), width=3)
        sheet.paste(im.resize((W // 2, H // 2)), (c * (W // 2), 0)); d.text((c * (W // 2) + 4, H // 2 + 4), f'{k / FPS:.1f}s', fill=(255, 255, 0))
    return res, sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('--ids'); ap.add_argument('--clips', help="glob relative to assetsDir, default: each panel's clip.src")
    ap.add_argument('--out', default=None); ap.add_argument('--refs', help='locked character sheet dir (<name>-front.png ...)')
    a = ap.parse_args()
    spec = C.load_spec(a.spec)
    out = a.out or os.path.join(C.ROOT, 'out', os.path.basename(os.path.dirname(spec['_path'])), 'drift')
    os.makedirs(out, exist_ok=True)
    want = set(a.ids.split(',')) if a.ids else None
    report, regen = [], []
    for sub in C.subspecs(spec):
        for u in sub['panels']:
            if want and u['id'] not in want:
                continue
            paths = sorted(glob.glob(os.path.join(os.environ.get('COMIC_ASSETS') or spec.get('assetsDir') or spec['_dir'], a.clips.replace('{id}', u['id'])))) if a.clips else ([C.resolve(spec, u['clip']['src'])] if u.get('clip') else [])
            for pth in paths:
                if 'greenstart' in pth:
                    continue
                res, sheet = check_clip(spec, u, pth, a.refs)
                sheet.save(os.path.join(out, os.path.basename(pth).replace('.mp4', '-drift.jpg')), quality=85)
                report.append(res)
                print(f"{'FLAG' if res['flags'] else ('look' if res['review'] else 'ok  ')} {os.path.basename(pth)}" + ''.join(': ' + '; '.join(x) for x in (res['flags'], res['review']) if x))
                if res['flags']:
                    regen.append(os.path.basename(pth))
    json.dump({'thresholds': {'track_min': TRACK_MIN, 'skin_rise': SKIN_RISE, 'skin_abs': SKIN_ABS, 'visor_w': VISOR_W},
               'regenerate': regen, 'clips': report}, open(os.path.join(out, 'drift-report.json'), 'w'), indent=1, default=str)
    print(f"\nDrift check: {len(regen)} of {len(report)} clip(s) flagged for regeneration -> {out}/drift-report.json")
    return 1 if regen else 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Comic mode QA (run by `npm run check -- <name>` when shots/<name>/<name>.comic.json exists).

Checks:
  clips     every clip in/out is inside its source duration, out > in, length <= 3 s
  beats     every panel / caption / SFX / transition time sits on a beat of the song timeline (<= 60 ms)
  text      captions + SFX stay inside the frame (both orientations) and never overlap while both are on screen
  slots     no black or empty panel slot: every visible slot has real picture content at sampled times
  align     each clip's first frame registers onto its panel (NCC >= 0.75) and the used frames stay close to it
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import comic_lib as C
from PIL import Image

MAX_CLIP = 3.0
problems, report = [], {}


def fail(msg):
    problems.append(msg); print('  FAIL', msg)


def ok(msg):
    print('  ok  ', msg)


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def main(path):
    spec = C.load_spec(path)
    units = [dict(p) for p in spec['panels']] + [dict(spec['splash'], id='splash', at=spec['transition']['at'])]

    print('clips:')
    for u in units:
        c = u.get('clip')
        if not c:
            continue
        src = C.resolve(spec, c['src'])
        if not os.path.exists(src):
            fail(f"{u['id']}: clip missing {src}"); continue
        d = C.probe_duration(src)
        L = c['out'] - c['in']
        if not (0 <= c['in'] < c['out'] <= d + 1e-3):
            fail(f"{u['id']}: in/out {c['in']}-{c['out']} outside source 0-{d:.2f}s")
        elif L > MAX_CLIP:
            fail(f"{u['id']}: clip uses {L:.2f}s > {MAX_CLIP}s")
        else:
            ok(f"{u['id']}: {os.path.basename(src)} {c['in']:.2f}-{c['out']:.2f}s ({L:.2f}s of {d:.2f}s)")

    print('beats:')
    beats = np.array(C.song_beats(spec))
    times = []
    for u in units:
        times.append((f"{u['id']} lands", u['at']))
        if u.get('clip'): times.append((f"{u['id']} clip", u['clip']['at']))
        for c in u.get('captions', []): times.append((f"{u['id']} caption", c.get('at', u['at'])))
        for s in u.get('sfx', []): times.append((f"{u['id']} sfx {s['text']}", s['at']))
    times.append(('transition start', spec['transition']['at'] - spec['transition'].get('dur', 0.4)))
    if len(beats):
        off = [(w, t, float(np.min(np.abs(beats - t)))) for w, t in times]
        bad = [o for o in off if o[2] > 0.06]
        for w, t, e in bad: fail(f'{w} at {t:.3f}s is {e*1000:.0f} ms off the beat grid')
        if not bad: ok(f'{len(times)} events on the beat grid (max {max(o[2] for o in off)*1000:.0f} ms)')
    for w, t in times:
        if not (spec['song']['start'] - 1e-3 <= t <= spec['song']['end']):
            fail(f'{w} at {t:.3f}s is outside the song section')

    for orient in ('landscape', 'vertical'):
        print(f'text ({orient}):')
        W, H = C.SIZES[orient]
        items = C.text_items(spec, orient)
        n0 = len(problems)
        for it in items:
            x, y, w, h = it['rect']
            if x < 8 or y < 8 or x + w > W - 8 or y + h > H - 8:
                fail(f"{orient}: {it['who']} leaves the frame {it['rect']}")
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                live = max(a['from'], b['from']) < min(a['to'], b['to'])
                if live and overlap(a['rect'], b['rect']):
                    fail(f"{orient}: {a['who']} overlaps {b['who']}")
        if len(problems) == n0:
            ok(f'{len(items)} captions/SFX inside frame, no overlaps')

    print('slots + alignment:')
    sc = C.Scene(spec, 'landscape')
    for u in sc.units + [sc.splash]:
        if u.get('clip'):
            s = u['regScore']
            img = Image.open(C.resolve(spec, u['image'])).convert('RGB')
            rx, ry, rw, rh = u['reg']
            # used frames vs the panel area they are mapped onto
            P = C.gray_small(img.crop((int(rx), int(ry), int(rx + rw), int(ry + rh))), 184)
            sim = [C.ncc(P, C.gray_small(f, 184)[:P.shape[0], :P.shape[1]]) for f in
                   C.read_clip(C.resolve(spec, u['clip']['src']), u['clip']['in'], u['clip']['out'], 6)]
            scale = rw / img.width
            report[u['id']] = {'register': [round(v, 1) for v in u['reg']], 'ncc0': round(s, 3), 'nccUsedMin': round(min(sim), 3)}
            if s < 0.75 or not (0.9 < scale < 1.1):
                fail(f"{u['id']}: clip does not line up with its panel (ncc {s:.2f}, scale {scale:.2f})")
            else:
                rin, _ = C.register(img, C.read_clip(C.resolve(spec, u['clip']['src']), u['clip']['in'], u['clip']['in'] + 0.05, 30)[0])
                shift = max(abs(a - b) for a, b in zip(rin, u['reg'])) / img.width
                if shift > 0.03:
                    fail(f"{u['id']}: first used frame (in={u['clip']['in']}s) is reframed {shift:.1%} vs the panel - the cut would jump")
                if min(sim) < 0.45:
                    print(f"  warn  {u['id']}: used frames change a lot vs the panel (min ncc {min(sim):.2f}) - fine for an impact burst, otherwise trim tighter")
                if shift <= 0.03: ok(f"{u['id']}: clip registers on panel at {tuple(round(v) for v in u['reg'])} ncc {s:.2f}, used frames min ncc {min(sim):.2f}")
    for orient in ('landscape', 'vertical'):
        sc = sc if orient == 'landscape' else C.Scene(spec, 'vertical')
        samples = set()
        for u in sc.units + [sc.splash]:
            samples.add(C.T(spec, u['at']) + 0.2)
            if u.get('clip'):
                c = u['clip']; t0 = C.T(spec, c['at'])
                samples |= {t0 + 0.05, t0 + (c['out'] - c['in']) / 2, t0 + (c['out'] - c['in']) + 0.2}
        samples.add(C.scene_len(spec) - 0.05)
        n0 = len(problems)
        tr_t = C.T(spec, spec['transition']['at'])
        for t in sorted(samples):
            a = np.asarray(sc.frame(t), np.float32)
            live = [u for u in sc.units if t >= C.T(spec, u['at']) + 0.15] if t < tr_t else [sc.splash]
            for u in live:
                x, y, w, h = u['slotrect']
                r = a[y:y + h, x:x + w]
                lum = r.mean(axis=2)
                dark = float((lum < 12).mean())
                if r.std() < 18 or lum.mean() < 25 or dark > 0.35:
                    fail(f"{orient}: slot {u['slot'] if 'slot' in u else 'splash'} ({u['id']}) looks empty/black at {t:.2f}s (std {r.std():.0f}, mean {lum.mean():.0f}, black {dark:.0%})")
        if len(problems) == n0:
            ok(f'{orient}: {len(samples)} sampled frames, every visible slot has picture content')

    out = os.path.join(C.ROOT, 'out', os.path.basename(os.path.dirname(spec['_path'])), 'qa')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'comic-qa.json'), 'w') as f:
        json.dump({'problems': problems, 'align': report}, f, indent=2)
    print(f"\nComic QA: {'PASS' if not problems else f'{len(problems)} problem(s)'}  (out/.../qa/comic-qa.json)")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))

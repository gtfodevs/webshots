#!/usr/bin/env python3
"""Comic mode QA (run by `npm run check -- <name>` when shots/<name>/<name>.comic.json exists).

Checks (every page of a multi-page spec):
  clips     clip in/out inside the source duration, out > in, length <= 6 s (warn < 3.5 s without a trimNote,
            warn if the page turns before the clip finishes)
  hold      the clip starts <= 0.6 s after its panel lands (one-beat static hold, then motion)
  beats     every landing / clip / caption / SFX / transition time is on the song's beat grid (<= 60 ms)
  text      captions + SFX inside the frame (landscape + vertical), no overlaps while on screen;
            no clipping: every box inside its panel's lettering rect and the page safe area (C.TEXT_SAFE),
            measured ink of every caption line inside its box; a lyric caption stays up until its
            sung line ends (timeline lyrics) and never overlaps the next caption
  audio     song / Short cut points never land mid-word (timeline words), inside the source audio,
            tail fades naturally (C.TAIL_FADE) under the end card
  end card  every video + Short ends on the end card (spec.endCard / C.ENDCARD_DEFAULT, ~3 s); its
            measured text fits the title-safe area (C.SAFE) in both orientations
  slots     no black or empty slot at sampled frames
  align     each clip registers on its panel (NCC >= 0.75, scale 0.9-1.1); first used frame not re-framed
  paper     no page leaves more than 30% bare paper once its panels have landed (pick the layout for the count)
  layouts   no layout (or splash style) repeated on consecutive pages; flags low layout variety per song
  unique    every panel is a different scene: no two panels with near-identical prompts
            (content-word Jaccard >= 0.6), the same location + camera pair, or near-identical
            images (64-bit DCT perceptual hash, Hamming distance <= 10)

A spec with "draft": true (planning stage, art not generated yet) runs the timing, text,
hold and prompt checks and reports missing media instead of failing on it.
"""
import itertools, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import comic_lib as C
from PIL import Image

MAX_CLIP = 6.05      # Jason: let clips play (3.5-4.5 s typical, full ~6 s when clean)
MIN_CLIP_WANT = 3.5
PROMPT_SIM = 0.6
PHASH_DIST = 10
MAX_PAPER = 0.3
STOP = set('a an the and of in on with to at by from for into its his her their is as it this that over under while one two'.split())
problems, warnings, report = [], [], {}


def fail(msg):
    problems.append(msg); print('  FAIL', msg)


def warn(msg):
    warnings.append(msg); print('  warn', msg)


def ok(msg):
    print('  ok  ', msg)


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def words(s):
    return {w for w in re.findall(r'[a-z]+', s.lower()) if w not in STOP and len(w) > 2}


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def phash(path):
    g = np.asarray(Image.open(path).convert('L').resize((32, 32), Image.LANCZOS), np.float64)
    n = 32
    k = np.arange(n)
    D = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
    dct = D @ g @ D.T
    low = dct[:8, :8].flatten()
    return low[1:] > np.median(low[1:])


def inside(r, box, tol=0):
    return (r[0] >= box[0] - tol and r[1] >= box[1] - tol and
            r[0] + r[2] <= box[0] + box[2] + tol and r[1] + r[3] <= box[1] + box[3] + tol)


_TL = {}
def timeline(spec):
    p = spec['song'].get('timeline')
    if not p:
        return {}
    p = C.resolve(spec, p)
    if p not in _TL:
        _TL[p] = json.load(open(p)) if os.path.exists(p) else {}
    return _TL[p]


def norm(s):
    return re.sub(r'[^A-Z0-9 ]', '', C.lyric_text(s)).split()


def sung_end(line):
    """End of the sung line. The aligner sometimes stretches a line over an instrumental gap, so the
    line ends at the last word before a > 2 s gap (+0.6 s for that word), capped by line.end."""
    ts = [w['t'] for w in line.get('words', [])]
    if not ts:
        return line['end']
    last = ts[0]
    for t in ts[1:]:
        if t - last > 2.0:
            break
        last = t
    return min(line['end'], last + 0.6)


def check_lyric_timing(sub, items, pid):
    """A lyric caption must stay up until its sung line ends (no caption gone before the singer is)."""
    lines = timeline(sub).get('lyrics', [])
    if not lines:
        return
    t0 = sub['song']['start']
    for it in items:
        c = it.get('obj') or {}
        if it.get('kind') != 'caption' or not c.get('lyric'):
            continue
        want = norm(c['text'])
        at = it['from'] + t0
        cands = [l for l in lines if norm(l['text']) == want and abs(l['t'] - at) < 4.0]
        if not cands:
            continue
        line = min(cands, key=lambda l: abs(l['t'] - at))
        # the same lyric may continue on the next box (e.g. a splash repeats it): follow the chain
        to = it['to']
        for o in sorted(items, key=lambda o: o['from']):
            if o is not it and o.get('kind') == 'caption' and norm(o['obj']['text']) == want and o['from'] <= to + 0.6 and o['to'] > to:
                to = o['to']
        gone = to + t0
        end = sung_end(line)
        if gone < end - 0.05:
            fail(f"{pid}: {it['who']} leaves at {gone:.2f}s but the line is sung until {end:.2f}s")


def check_audio(spec):
    """No clipped audio: cut points never land mid-word, the source covers the span, the tail fades."""
    print('audio:')
    n0 = len(problems)
    words = timeline(spec).get('words', [])
    lines = timeline(spec).get('lyrics', [])
    src = C.resolve(spec, spec['song']['audio'])
    dur = None
    if os.path.exists(src):
        dur = C.probe_duration(src)
    else:
        warn(f"song audio {spec['song']['audio']} not found - source-length checks skipped")
    cuts = [('song start', spec['song']['start']), ('song end', spec['song']['end'])]
    if spec.get('short'):
        cuts += [('Short start', spec['short']['start']), ('Short end', spec['short']['end'])]
    for name, t in cuts:
        if dur is not None and t > dur + 0.05:
            fail(f"{name} {t:.2f}s is past the end of the audio ({dur:.2f}s)")
        if 'start' in name and t < 0.05:
            continue
        if dur is not None and 'end' in name and t >= dur - 0.05:
            continue
        for w in words:
            if w['s'] + 0.03 < t < w['e'] - 0.03:
                fail(f"{name} at {t:.2f}s cuts the word '{w['w']}' ({w['s']:.2f}-{w['e']:.2f}s) - move it to a gap")
                break
        if 'end' in name:
            for l in lines:
                if l['t'] < t < l['end'] - 0.05:
                    warn(f"{name} at {t:.2f}s lands inside the lyric line '{l['text']}' - the tail fade carries it out")
                    break
    ec = C.endcard(spec)
    if not ec:
        fail('no end card - every comic video and Short ends on the PROGRESSIVE SLOP end card (spec.endCard)')
    if C.TAIL_FADE < 1.5:
        fail(f'tail fade {C.TAIL_FADE}s is too short - fade the song out naturally (>= 1.5 s)')
    if len(problems) == n0:
        ok(f"cut points clear of words, tail fades over >= {C.TAIL_FADE}s" + (f" under a {ec['seconds']}s end card" if ec else ''))


def check_endcard(spec):
    print('end card:')
    n0 = len(problems)
    ec = C.endcard(spec)
    if not ec:
        return
    if not 2.5 <= ec['seconds'] <= 4.0:
        warn(f"end card holds {ec['seconds']}s (aim for ~3 s)")
    for orient in ('landscape', 'vertical'):
        W, H = C.SIZES[orient]
        x0, y0, x1, y1 = C.SAFE[orient]
        safe = (x0, y0, x1 - x0, y1 - y0)
        for it in C.endcard_layout(ec, orient):
            for tb in C.endcard_text_bounds(it):
                if not inside(tb, it['rect']):
                    fail(f"end card {orient}: text {tb} spills out of its box {it['rect']}")
                if not inside(tb, safe):
                    fail(f"end card {orient}: text {tb} is outside the title-safe area {C.SAFE[orient]}")
            if not inside(C.endcard_bounds_rotated(it), (0, 0, W, H)):
                fail(f"end card {orient}: box {C.endcard_bounds_rotated(it)} leaves the frame")
    if len(problems) == n0:
        ok(f"{len(ec['lines'])} lines fit inside the title-safe area (landscape + vertical), held {ec['seconds']}s")


def all_units(sub):
    us = [dict(p) for p in sub['panels']]
    sp = C.splash_unit(sub)
    return us + ([sp] if sp else [])


def media_ok(spec, rel):
    return rel and os.path.exists(C.resolve(spec, rel))


def check_page(sub, draft):
    pid = sub.get('page', 'page')
    units = all_units(sub)
    have_media = all(media_ok(sub, u['image']) and (not u.get('clip') or (media_ok(sub, u['clip'].get('src')) and u['clip'].get('in') is not None and u['clip'].get('out') is not None)) for u in units)

    # clips + hold
    for u in units:
        c = u.get('clip')
        if not c:
            continue
        land, start = u['at'], C.clip_start(sub, u)
        if start - land > C.MAX_HOLD + 1e-6:
            fail(f"{pid}/{u['id']}: clip starts {start - land:.2f}s after the panel lands (max {C.MAX_HOLD}s)")
        elif start - land < C.MIN_HOLD - 1e-6:
            fail(f"{pid}/{u['id']}: clip starts {start - land:.2f}s after landing - keep the anticipation beat (>= {C.MIN_HOLD}s)")
        if c.get('in') is None or c.get('out') is None:
            if not draft: fail(f"{pid}/{u['id']}: clip has no in/out")
            elif (c.get('expected') or 0) > 6.0: fail(f"{pid}/{u['id']}: expected trim {c['expected']}s > 6.0s")
            continue
        L = c['out'] - c['in']
        if L > MAX_CLIP or c['out'] <= c['in']:
            fail(f"{pid}/{u['id']}: clip {c['in']}-{c['out']} is empty or longer than {MAX_CLIP}s")
        if L < MIN_CLIP_WANT - 1e-6 and not c.get('trimNote'):
            warn(f"{pid}/{u['id']}: clip only {L:.2f}s - let it play 3.5-4.5 s unless it breaks (add a trimNote saying why)")
        is_splash = bool(C.splash_unit(sub)) and u['id'] == C.splash_unit(sub)['id']
        page_cut = (sub['song']['end'] if is_splash else
                    (sub['transition']['at'] - sub['transition'].get('dur', 0.4) if sub.get('transition') else sub['song']['end']))
        if start + L > page_cut + 0.05:
            warn(f"{pid}/{u['id']}: clip runs {start + L - page_cut:.2f}s past the page turn and gets cut off")
        src = C.resolve(sub, c['src'])
        if os.path.exists(src):
            d = C.probe_duration(src)
            if not (0 <= c['in'] < c['out'] <= d + 1e-3):
                fail(f"{pid}/{u['id']}: in/out {c['in']}-{c['out']} outside source 0-{d:.2f}s")

    # beats
    beats = np.array(C.song_beats(sub))
    times = []
    for u in units:
        times.append((f"{u['id']} lands", u['at']))
        if u.get('clip'): times.append((f"{u['id']} clip", C.clip_start(sub, u)))
        for c in u.get('captions', []): times.append((f"{u['id']} caption", c.get('at', u['at'])))
        for s in u.get('sfx', []): times.append((f"{u['id']} sfx {s['text']}", s['at']))
    if sub.get('transition'):
        tr = sub['transition']
        times.append(('transition start', tr['at'] - tr.get('dur', 0.4)))
    if len(beats):
        for w, t in times:
            e = float(np.min(np.abs(beats - t)))
            if e > 0.06: fail(f'{pid}: {w} at {t:.3f}s is {e*1000:.0f} ms off the beat grid')
    for w, t in times:
        if not (sub['song']['start'] - 1e-3 <= t <= sub['song']['end']):
            fail(f"{pid}: {w} at {t:.3f}s is outside the page ({sub['song']['start']}-{sub['song']['end']})")

    # empty paper: a page whose panels leave a big blank area needs a layout that fits its panel count
    for orient in ('landscape', 'vertical'):
        pf = C.paper_fraction(sub, orient)
        if pf > MAX_PAPER:
            fail(f"{pid} {orient}: {pf:.0%} of the page is empty paper (max {MAX_PAPER:.0%}) - use a layout for {len(sub['panels'])} panels (e.g. \"layout\": \"two-up\")")
        for p in sub['panels']:
            if sub.get('layout', 'three') in C.LAYOUTS and p['slot'] not in C.layout(orient, sub.get('layout', 'three')):
                fail(f"{pid}: {p['id']} slot '{p['slot']}' is not in layout '{sub.get('layout', 'three')}'")

    # text
    for orient in ('landscape', 'vertical'):
        W, H = C.SIZES[orient]
        items = C.text_items(sub, orient)
        sx, sy, sw, sh = C.TEXT_SAFE[orient]
        for it in items:
            x, y, w, h = it['rect']
            if x < 8 or y < 8 or x + w > W - 8 or y + h > H - 8:
                fail(f"{pid} {orient}: {it['who']} leaves the frame {it['rect']}")
            # no clipping: the box must sit inside its panel's lettering rect and the page safe area,
            # and the measured ink of every line must sit inside the box
            if not inside(it['rect'], it['slot'], 2):
                fail(f"{pid} {orient}: {it['who']} box {it['rect']} extends past its panel {tuple(it['slot'])}")
            if not inside(it['rect'], (sx, sy, sw, sh), 0):
                fail(f"{pid} {orient}: {it['who']} box {it['rect']} extends past the safe area {C.TEXT_SAFE[orient]}")
            if it.get('kind') == 'caption':
                for tb in C.caption_text_bounds(it['obj'], it['slot']):
                    if not inside(tb, it['rect'], 0):
                        fail(f"{pid} {orient}: {it['who']} text {tb} spills out of its box {it['rect']}")
        for a, b in itertools.combinations(items, 2):
            if max(a['from'], b['from']) < min(a['to'], b['to']) and overlap(a['rect'], b['rect']):
                both = a.get('obj', {}).get('lyric') and b.get('obj', {}).get('lyric')
                fail(f"{pid} {orient}: {a['who']} overlaps {'the next lyric caption ' if both else ''}{b['who']}")
        if orient == 'landscape':
            check_lyric_timing(sub, items, pid)

    if not have_media:
        (warn if draft else fail)(f'{pid}: panel art / clips not generated yet - slot + alignment checks skipped')
        return

    # alignment + slots
    for orient in ('landscape', 'vertical'):
        sc = C.Scene(sub, orient)
        if orient == 'landscape':
            for u in sc.all_units():
                if not u.get('clip'):
                    continue
                img = Image.open(C.resolve(sub, u['image'])).convert('RGB')
                rx, ry, rw, rh = u['reg']
                scale = rw / img.width
                rin, _ = C.register(img, C.read_clip(C.resolve(sub, u['clip']['src']), u['clip']['in'], u['clip']['in'] + 0.05, 30)[0])
                shift = max(abs(a - b) for a, b in zip(rin, u['reg'])) / img.width
                report[f"{pid}/{u['id']}"] = {'register': [round(v, 1) for v in u['reg']], 'ncc0': round(u['regScore'], 3), 'inShift': round(shift, 4)}
                if u['regScore'] < 0.75 or not (0.9 < scale < 1.1):
                    fail(f"{pid}/{u['id']}: clip does not line up with its panel (ncc {u['regScore']:.2f}, scale {scale:.2f})")
                elif shift > 0.03:
                    fail(f"{pid}/{u['id']}: first used frame (in={u['clip']['in']}s) is re-framed {shift:.1%} vs the panel")
        samples = set()
        for u in sc.all_units():
            samples.add(C.T(sub, u['at']) + 0.2)
            if u.get('clip'):
                c = u['clip']; t0 = C.T(sub, C.clip_start(sub, u))
                samples |= {t0 + 0.05, t0 + (c['out'] - c['in']) / 2, t0 + (c['out'] - c['in']) + 0.2}
        samples.add(C.scene_len(sub) - 0.05)
        tr_t = C.T(sub, sub['transition']['at']) if sub.get('transition') else 1e9
        for t in sorted(x for x in samples if x < C.scene_len(sub)):
            a = np.asarray(sc.frame(t), np.float32)
            live = [u for u in sc.units if t >= C.T(sub, u['at']) + 0.15] if t < tr_t else [sc.splash]
            for u in live:
                x, y, w, h = u['slotrect']
                r = a[y:y + h, x:x + w]
                lum = r.mean(axis=2)
                dark = float((lum < 12).mean())
                if r.std() < 18 or lum.mean() < 10 or dark > 0.85:   # dark art (silhouettes, night: n04 mean 21, std 40) is fine; flat/black is not
                    fail(f"{pid} {orient}: slot of {u['id']} looks empty/black at {t:.2f}s")


def check_unique(spec, subs):
    print('unique scenes:')
    n0 = len(problems)
    units = [(s.get('page', ''), u) for s in subs for u in all_units(s)]
    ids = [u['id'] for _, u in units]
    for d in {i for i in ids if ids.count(i) > 1}:
        fail(f'panel id {d} is used twice')
    seen = {}
    for pg, u in units:
        key = (u.get('location', '').lower(), u.get('camera', '').lower())
        if all(key) and key in seen:
            fail(f"{u['id']} repeats {seen[key]}'s location + camera ({key[0]} / {key[1]})")
        seen.setdefault(key, u['id'])
    texts = [(u['id'], words(u.get('scene') or u.get('prompt') or '')) for _, u in units]
    worst = (0, '')
    for (ia, wa), (ib, wb) in itertools.combinations(texts, 2):
        if not wa or not wb:
            continue
        j = jaccard(wa, wb)
        if j > worst[0]: worst = (j, f'{ia}~{ib}')
        if j >= PROMPT_SIM:
            fail(f'{ia} and {ib} have near-identical prompts (similarity {j:.2f})')
    hashes = []
    for pg, u in units:
        if media_ok(spec, u['image']):
            hashes.append((u['id'], u['image'], phash(C.resolve(spec, u['image']))))
    for (ia, pa, ha), (ib, pb, hb) in itertools.combinations(hashes, 2):
        if pa == pb:
            continue  # a splash may reuse its own page panel's art on purpose
        d = int((ha != hb).sum())
        if d <= PHASH_DIST:
            fail(f'{ia} and {ib} images are near-identical (pHash distance {d})')
    if len(problems) == n0:
        ok(f'{len(units)} panels, all different scenes (max prompt similarity {worst[0]:.2f} {worst[1]}; '
           f'{len(hashes)} images hashed)')


def check_layouts(spec, subs):
    print('layouts:')
    n0 = len(problems)
    names = [(s.get('page', ''), s.get('layout', 'three'), s.get('splashStyle') if s.get('splash') else None) for s in subs]
    for (pa, la, sa), (pb, lb, sb) in zip(names, names[1:]):
        if la == lb:
            fail(f'{pa} and {pb} both use layout {la!r} - never repeat a layout on consecutive pages')
        if sa and sb and sa == sb:
            fail(f'{pa} and {pb} both use splash style {sa!r} back to back')
    for pg, la, _ in names:
        if la not in C.LAYOUTS:
            fail(f'{pg}: unknown layout {la!r}')
    distinct = len({la for _, la, _ in names})
    if len(names) >= 4:
        want = math.ceil(len(names) / 2)
        if distinct < math.ceil(len(names) / 3):
            fail(f'low layout variety: {distinct} distinct layouts over {len(names)} pages (need >= {math.ceil(len(names) / 3)})')
        elif distinct < want:
            warn(f'low layout variety: {distinct} distinct layouts over {len(names)} pages (aim for >= {want})')
    if len(problems) == n0:
        ok(f"{distinct} distinct layouts over {len(names)} pages, no consecutive repeats: " + ', '.join(f'{la}{"+" + sa if sa else ""}' for _, la, sa in names))


def main(path):
    spec = C.load_spec(path)
    draft = bool(spec.get('draft'))
    subs = C.subspecs(spec)
    print(f"{'DRAFT ' if draft else ''}spec, {len(subs)} page(s):")
    for sub in subs:
        n0 = len(problems)
        check_page(sub, draft)
        if len(problems) == n0:
            ok(f"{sub.get('page', 'page')}: {len(all_units(sub))} panels - clips, hold {C.MIN_HOLD}-{C.MAX_HOLD}s, beats, text")
    check_layouts(spec, subs)
    check_unique(spec, subs)
    check_audio(spec)
    check_endcard(spec)
    out = os.path.join(C.ROOT, 'out', os.path.basename(os.path.dirname(spec['_path'])), 'qa')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'comic-qa.json'), 'w') as f:
        json.dump({'problems': problems, 'warnings': warnings, 'align': report}, f, indent=2)
    print(f"\nComic QA: {'PASS' if not problems else f'{len(problems)} problem(s)'}"
          f"{f', {len(warnings)} warning(s)' if warnings else ''}  (out/{os.path.basename(out[:-3])}/qa/comic-qa.json)")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))

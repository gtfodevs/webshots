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
            part = [l for l in lines if abs(l['t'] - at) < 4.0 and len(norm(l['text'])) > len(want) and norm(l['text'])[:len(want)] == want]
            if part:
                l = min(part, key=lambda l: abs(l['t'] - at))
                fail(f"{pid}: {it['who']} truncates the sung line - it goes on '{' '.join(norm(l['text'])[len(want):])}'")
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


def rotated_bounds(r, box, deg):
    """Axis-aligned bounds of rect r after rotating by deg (PIL convention, counter-clockwise) about box's centre."""
    cx, cy = box[0] + box[2] / 2 + 6, box[1] + box[3] / 2 + 6
    a = math.radians(deg)
    pts = []
    for x, y in ((r[0], r[1]), (r[0] + r[2], r[1]), (r[0], r[1] + r[3]), (r[0] + r[2], r[1] + r[3])):
        dx, dy = x - cx, y - cy
        pts.append((cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a)))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (int(min(xs)) - 1, int(min(ys)) - 1, int(max(xs) - min(xs)) + 2, int(max(ys) - min(ys)) + 2)


def check_intro(spec):
    """Standing rule: every video and Short opens on the title logo intro; its lettering is never clipped."""
    ic = C.intro(spec)
    if not ic:
        fail('intro: the title logo intro is missing/disabled (required on every video and Short)')
        return
    # standing rule (Jason, 2026-10-14): a custom per-song logotype, animated in over a moving background
    lp = ic.get('logotype')
    if not lp:
        fail('intro: no logotype asset (intro.logotype) - every video opens with a custom logotype designed for its song/world, animated in over a moving background')
    elif not os.path.exists(lp):
        fail(f'intro: logotype asset missing on disk: {lp}')
    else:
        ok(f'intro: logotype {os.path.basename(lp)} (rays sweep, draw-on, shine, glint over the live opening page)')
    bad = 0
    for orient in ('landscape', 'vertical'):
        W, H = C.SIZES[orient]
        lost = C.intro_ink_lost(ic, orient)
        if lost > 0:
            fail(f"intro {orient}: logo tile loses {lost} ink px vs the oversized-canvas reference"); bad += 1
        s0 = spec['song']['start'] if orient == 'landscape' or not spec.get('short') else spec['short']['start']
        ts = C.intro_slam(spec, s0)
        fps = spec.get('fps', 30)
        sx0, sy0, sx1, sy1 = C.SAFE[orient]
        for k in range(int((ts - 0.15) * fps), int((ts + ic['seconds']) * fps) + 1):
            t = k / fps
            st = C.intro_state(ic, orient, t, ts)
            if not st:
                continue
            r = C.intro_rect(ic, orient, st[0])
            if r[0] < sx0 or r[1] < sy0 or r[0] + r[2] > sx1 or r[1] + r[3] > sy1:
                fail(f"intro {orient}: logo {[int(v) for v in r]} leaves the title-safe area at {t:.2f}s"); bad += 1; break
            sb = C.intro_shake_box(orient, t, st[3], fps)
            if sb:
                r = [(r[0] - sb[0]) * W / sb[2], (r[1] - sb[1]) * H / sb[3], r[2] * W / sb[2], r[3] * H / sb[3]]
            if r[0] < 2 or r[1] < 2 or r[0] + r[2] > W - 2 or r[1] + r[3] > H - 2:
                fail(f"intro {orient}: logo sliced by the frame edge at {t:.2f}s (shake) -> {[int(v) for v in r]}"); bad += 1; break
    if not bad:
        ok(f"intro: '{ic['title']}' logo slams in on the first downbeat, {ic['seconds']}s, no ink lost, inside title-safe + frame (landscape + vertical, incl. shake)")


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
                # the box is drawn rotated: rotate all 4 text corners (+ box shadow offset) about the box centre
                rb = rotated_bounds(tb, it['rect'], it['rot'])
                if not inside(rb, safe):
                    fail(f"end card {orient}: rotated text {rb} is outside the title-safe area {C.SAFE[orient]}")
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
        # tempo-aware: a slow song's beat is longer than 0.6 s, so the one-beat hold may be up to one beat
        # beat spacing in a real timeline jitters a few % around the tempo, so allow the beat-grid tolerance (60 ms)
        limit = max(C.MAX_HOLD, C.beat_period(sub) + 0.06)
        if start - land > limit + 1e-6:
            fail(f"{pid}/{u['id']}: clip starts {start - land:.2f}s after the panel lands (max {limit:.2f}s = max({C.MAX_HOLD}s, one beat + 60 ms))")
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
            # box (at its peak: SFX stamp-in scale) inside the panel's real clip path (slanted / tilted
            # polygons, eroded by C.LETTER_INSET) - not just its bounding rect
            if not C.fits(it['rect'], it['geo']):
                fail(f"{pid} {orient}: {it['who']} box {it['rect']} crosses its panel edge (clip path incl. slanted/tilted gutters)")
            if not inside(it['rect'], (sx, sy, sw, sh), 0):
                fail(f"{pid} {orient}: {it['who']} box {it['rect']} extends past the safe area {C.TEXT_SAFE[orient]}")
            if it.get('kind') == 'caption':
                for tb in C.caption_text_bounds(it['obj'], it['slot'], it['geo'], C.TEXT_SAFE[orient]):
                    if not inside(tb, it['rect'], 0):
                        fail(f"{pid} {orient}: {it['who']} text {tb} spills out of its box {it['rect']}")
        for a, b in itertools.combinations(items, 2):
            if max(a['from'], b['from']) < min(a['to'], b['to']) and overlap(a['rect'], b['rect']):
                both = a.get('obj', {}).get('lyric') and b.get('obj', {}).get('lyric')
                fail(f"{pid} {orient}: {a['who']} overlaps {'the next lyric caption ' if both else ''}{b['who']}")
        # pixel check: render each unit's lettering alone at its peak frame; no lettering pixel may sit
        # outside the panel clip path (cut by a mask edge / hanging over a gutter) or the safe area
        for uid in sorted({it['unit'] for it in items}):
            lay, geo = C.letter_layer_cached(sub, orient, uid) if hasattr(C, 'letter_layer_cached') else C.lettering_layer(sub, orient, uid)
            outside = lay & ~C.clip_path_mask(geo, W, H, 4)
            safe = np.zeros_like(lay); safe[sy:sy + sh, sx:sx + sw] = True
            n_out, n_safe = int(outside.sum()), int((lay & ~safe).sum())
            if n_out:
                ys, xs = np.nonzero(outside)
                fail(f"{pid} {orient}: {uid} lettering has {n_out} px outside its panel clip path near ({int(xs.mean())},{int(ys.mean())})")
            if n_safe:
                fail(f"{pid} {orient}: {uid} lettering has {n_safe} px outside the safe area")
        # impact bursts (breakout splashes) must be solid: nothing underneath may show through the interior
        for u in all_units(sub):
            geo = C.layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full')).get(u.get('slot', 'splash'))
            if geo and geo.get('burst'):
                n_see, n_in = C.burst_see_through(geo, W, H)
                if n_see:
                    fail(f"{pid} {orient}: {u['id']} impact burst is see-through ({n_see}/{n_in} interior px show what is underneath) - fill it solid")
        # glyph overhang: every SFX tile must hold all its ink vs an oversized-canvas reference
        # (a tight pre-rotation canvas sliced the top-right of slanted Bangers glyphs)
        for it in items:
            if it.get('kind') == 'sfx':
                lost, _, _ = C.sfx_ink_lost(it['obj'], it['slot'])
                if lost > 0:
                    fail(f"{pid} {orient}: {it['who']} tile loses {lost} ink px vs the padded reference (glyph/stroke overhang cropped)")
        # rendered-frame geometry: map every visible caption / SFX through the frame's zoom (page transition)
        # and screen-shake crop at sampled times; nothing visible may be sliced by the frame edge
        sc = C.Scene.__new__(C.Scene)
        sc.spec, sc.orient, sc.W, sc.H, sc.fps = sub, orient, W, H, sub.get('fps', 30)
        sc.G = C.layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
        sc.units = [dict(p, geo=sc.G[p['slot']]) for p in sub['panels']]
        spu = C.splash_unit(sub); sc.splash = spu and dict(spu, geo=sc.G['splash'])
        tr = sub.get('transition')
        times = set()
        for it in items:
            times |= {it['from'] + d for d in (0.0, 0.03, 0.1, 0.2)}
        if tr:
            t1 = C.T(sub, tr['at']); d_ = tr.get('dur', 0.4)
            times |= {t1 - d_ + d_ * k / 8 for k in range(9)}
        for t in sorted(x for x in times if 0 <= x < C.scene_len(sub)):
            vb = sc.view_box(t); shb = sc.shake_box(t)
            for it in items:
                if not (it['from'] <= t < it['to']):
                    continue
                if tr and vb != (0, 0, W, H) and it['unit'] != tr['panel']:
                    continue   # renderer drops other panels' lettering during the zoom
                x, y, w, h = it['rect']
                sx_ = W / vb[2]; sy_ = H / vb[3]
                r = [(x - vb[0]) * sx_, (y - vb[1]) * sy_, w * sx_, h * sy_]
                if shb:
                    r = [(r[0] - shb[0]) * W / shb[2], (r[1] - shb[1]) * H / shb[3], r[2] * W / shb[2], r[3] * H / shb[3]]
                if r[0] < 2 or r[1] < 2 or r[0] + r[2] > W - 2 or r[1] + r[3] > H - 2:
                    fail(f"{pid} {orient}: {it['who']} is sliced by the frame edge at {t + sub['song']['start']:.2f}s "
                         f"({'zoom' if vb != (0, 0, W, H) else ''}{' shake' if shb else ''}) -> {[int(v) for v in r]}")
                    break
        if orient == 'landscape' and not C.overlay_on(sub):   # overlay specs: check_lyric_overlay instead
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
                # drift is reported separately: per-second NCC of each sampled frame against the clip's first frame
                # (a low score here is motion/morphing, not a bad handoff)
                c0 = C.gray_small(C.first_frame(C.resolve(sub, u['clip']['src'])), 160)
                drift = [round(C.ncc(c0, C.gray_small(fr, 160)), 2)
                         for fr in C.read_clip(C.resolve(sub, u['clip']['src']), u['clip']['in'], u['clip']['out'], 1)]
                report[f"{pid}/{u['id']}"] = {'register': [round(v, 1) for v in u['reg']], 'ncc0': round(u['regScore'], 3),
                                              'inShift': round(shift, 4), 'driftPerSecond': drift}
                if u['regScore'] < 0.75 or not (0.9 < scale < 1.1):
                    fail(f"{pid}/{u['id']}: clip's first frame does not line up with its panel (ncc {u['regScore']:.2f}, scale {scale:.2f})")
                elif shift > 0.03:
                    fail(f"{pid}/{u['id']}: first used frame (in={u['clip']['in']}s) is re-framed {shift:.1%} vs the panel")
                warn(f"{pid}/{u['id']}: drift vs the clip's first frame, per second: {drift}")
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
                # measure inside the panel's clip path only (a black 'blinking_eyes' gutter is not empty art)
                x, y, w, h = u['geo']['bbox']
                mk = np.asarray(u['mask'])[:max(0, min(h, a.shape[0] - y)), :max(0, min(w, a.shape[1] - x))] > 127
                r = a[y:y + h, x:x + w][:mk.shape[0], :mk.shape[1]][mk]
                lum = r.mean(axis=-1)
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


def check_entrances(spec, subs):
    """Level 1 of the two-level transition rule: every panel enters with its own entrance, never the same type as
    the panel before it (across the whole video), 0.2-0.4 s, finished before its clip starts; captions/SFX wait for it."""
    print('panel entrances:')
    n0 = len(problems)
    seq, prev = [], None
    for sub in subs:
        for u in sorted(sub['panels'], key=lambda u: u['at']):
            en = C.entrance_of(u)
            if en['type'] not in C.ENTRANCES:
                fail(f"{u['id']}: unknown entrance '{en['type']}' (use one of {', '.join(C.ENTRANCES)})")
            if en['type'] == prev:
                fail(f"{u['id']}: entrance '{en['type']}' repeats the previous panel's - vary them")
            if not C.ENTRANCE_MIN - 1e-6 <= en['dur'] <= C.ENTRANCE_MAX + 1e-6:
                fail(f"{u['id']}: entrance {en['dur']}s outside {C.ENTRANCE_MIN}-{C.ENTRANCE_MAX}s")
            if u.get('clip') and C.clip_start(sub, u) < u['at'] + en['dur'] - 1e-3:
                fail(f"{u['id']}: clip starts before its {en['type']} entrance finishes")
            prev = en['type']; seq.append(f"{u['id']}:{en['type']}")
    if len(problems) == n0:
        ok(f"{len(seq)} panels, no back-to-back entrance repeats, {C.ENTRANCE_MIN}-{C.ENTRANCE_MAX}s, each done before its clip; lettering waits for the entrance: " + ' '.join(seq))


def check_refs(spec, subs):
    """Reference-first rule (Jason, 2026-10-13): every panel showing a recurring character or setting must have been
    generated from reference images, never text alone. It must list them: panels[i].refs = ["refs/uno-front.png", ...]
    (files must exist). Text-only is allowed only for vehicle / effects shots: panels[i].shotKind = "vehicle" | "fx".
    A panel is a character panel when a focus region names a cast member (spec.cast, default Uno/Aura) or a
    face/head/eyes, or when it sets recurring: true."""
    print('reference images (reference-first rule):')
    n0 = len(problems)
    cast = [c.lower() for c in spec.get('cast', ['Uno', 'Aura'])]
    n = 0
    for sub in subs:
        for u in sub['panels']:
            if u.get('shotKind') in ('vehicle', 'fx'):
                continue
            labels = ' '.join(r.get('label', '') for r in (u.get('focusRegions') or [])).lower()
            if not (u.get('recurring') or any(c in labels for c in cast) or any(k in labels for k in ('face', 'head', 'eyes'))):
                continue
            n += 1
            refs = u.get('refs') or []
            if not refs:
                fail(f"{sub['page']}/{u['id']}: character/recurring panel lists no reference images (refs) - generate it from the locked sheets, never text alone")
            for r in refs:
                if not os.path.exists(C.resolve(spec, r)):
                    fail(f"{sub['page']}/{u['id']}: reference image missing: {r}")
    if len(problems) == n0:
        ok(f"{n} character/recurring panels all list existing reference images")


def check_focus(spec, subs):
    """Scene-aware cropping: every required focus region (faces, key action) of every panel must sit inside its
    cell (clip path eroded past the ink), inside the frame and not under a panel drawn above it - landscape (16:9)
    and vertical (the Short). Debug crops for every miss go to out/<shot>/qa/focus/."""
    print('focus regions:')
    n0 = len(problems)
    out = os.path.join(C.ROOT, 'out', os.path.basename(os.path.dirname(spec['_path'])), 'qa', 'focus')
    os.makedirs(out, exist_ok=True)
    nreg = nauto = 0
    short = spec.get('short')
    for sub in subs:
        for orient in ('landscape', 'vertical'):
            where = '16:9' if orient == 'landscape' else ('Short' if short and sub['song']['end'] > short['start'] and sub['song']['start'] < short['end'] else 'vertical (not in Short)')
            if C.is_reflow(sub):
                continue        # living panels: check_reflow tests every state and move instead of one static layout
            probs = C.page_focus_problems(spec, sub, orient)
            if orient == 'landscape':
                for u in sub['panels']:
                    G = C.layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
                    regs = C.unit_fit(spec, u, G[u['slot']])[2]
                    nreg += len(regs); nauto += sum(r['src'] == 'auto' for r in regs)
                    if not regs:
                        warn(f"{sub['page']}/{u['id']}: no focus regions (add focusRegions: faces + key action)")
            for uid, label, kind, frac in probs:
                (fail if 'not in Short' not in where else warn)(f"{sub['page']}/{uid} {where}: '{label}' {kind} ({frac:.0%} of it) - move the crop, widen the cell or change the layout")
                focus_debug(spec, sub, orient, uid, os.path.join(out, f"{sub['page']}-{uid}-{orient}.jpg"))
    if len(problems) == n0:
        ok(f"{nreg} focus regions ({nauto} auto) fit their cells in 16:9 and the Short, none clipped or occluded")


def focus_debug(spec, sub, orient, uid, path):
    """Source panel with the crop (cyan), the cell's clip path mapped back (white) and the focus regions (green ok / red miss)."""
    from PIL import ImageDraw
    G = C.layout_geo(orient, sub.get('layout', 'three'), sub.get('splashStyle', 'full'))
    u = next(x for x in sub['panels'] if x['id'] == uid)
    geo = G[u['slot']]
    (iw, ih), crop, regions, miss, within = C.unit_fit(spec, u, geo)
    img = Image.open(C.resolve(spec, u['image'])).convert('RGB')
    d = ImageDraw.Draw(img)
    cx, cy, cw, ch = crop; x, y, w, h = geo['bbox']
    d.rectangle([cx, cy, cx + cw, cy + ch], outline=(0, 255, 255), width=4)
    for poly in geo['polys']:
        d.line([(cx + (px - x) / w * cw, cy + (py - y) / h * ch) for px, py in poly + [poly[0]]], fill=(255, 255, 255), width=3)
    bad = {id(r) for r, _ in miss}
    for r in regions:
        b = r['box']
        d.rectangle([b[0] * iw, b[1] * ih, b[2] * iw, b[3] * ih], outline=(255, 40, 40) if id(r) in bad else (40, 255, 80), width=4)
        d.text((b[0] * iw + 4, b[1] * ih + 4), r['label'], fill=(255, 255, 0))
    img.save(C.next_free(path), quality=85)


def check_transitions(spec, subs, draft, deep=True):
    """Page transitions: valid types, 0.3-0.8 s, never the same type twice in a row, no sung line split across a
    boundary without its caption carried over, little clip time under a transition, and (rendered, non-draft)
    the lettering at mid-transition frames is pixel-identical to the plain frame (never moved, masked or cut)."""
    print('transitions:')
    n0 = len(problems)
    trs = C.page_transitions(spec)
    if not trs:
        ok('single page - no transitions'); return
    lines = timeline(spec).get('lyrics', [])
    prev = None
    for k, tr in enumerate(trs):
        A, B = subs[k], subs[k + 1]
        if tr['type'] not in C.TRANSITIONS:
            fail(f"{tr['into']}: unknown transition '{tr['type']}' (use one of {', '.join(C.TRANSITIONS)})")
        if tr['type'] == prev:
            fail(f"{tr['into']}: '{tr['type']}' twice in a row - vary the transitions")
        elif prev and C.TRANSITION_FAMILY.get(tr['type']) == C.TRANSITION_FAMILY.get(prev) and tr['auto']:
            warn(f"{tr['into']}: auto-picked '{tr['type']}' is the same family as the previous '{prev}'")
        prev = tr['type']
        if tr['type'] != 'cut' and not C.TRANS_MIN - 1e-6 <= tr['dur'] <= C.TRANS_MAX + 1e-6:
            fail(f"{tr['into']}: transition {tr['dur']}s outside {C.TRANS_MIN}-{C.TRANS_MAX}s")
        b, h = tr['at'], tr['dur'] / 2
        # a line sung across the boundary must be carried onto the incoming page (lettering swaps at the boundary)
        for l in ([] if C.overlay_on(spec) else lines):   # the floating overlay carries every line by design
            if l['t'] < b - 0.1 and sung_end(l) > b + 0.1:
                want = norm(l['text'])
                carried = any(c.get('lyric') and norm(c['text']) == want and c.get('at', u['at']) <= b + 0.05
                              for u in B['panels'] for c in u.get('captions', []))
                if not carried:
                    fail(f"{tr['into']}: '{l['text']}' is sung across the page turn at {b:.2f}s but its caption is not carried onto the new page")
        # clip time under the transition (the clip keeps playing underneath, but keep it short)
        for sub in (A, B):
            for u in sub['panels']:
                if not u.get('clip'):
                    continue
                c0 = C.clip_start(sub, u); L = u['clip']['out'] - u['clip']['in']
                ov = max(0.0, min(c0 + L, b + h) - max(c0, b - h))
                if ov > 0.15 * L:
                    warn(f"{tr['into']}: {u['id']} clip has {ov:.2f}s of its {L:.2f}s under the {tr['type']} transition")
    if not draft and deep and len(problems) == n0:
        bad = 0
        for orient in ('landscape', 'vertical'):
            for k, tr in enumerate(trs):
                if tr['dur'] <= 0:
                    continue
                A, B = subs[k], subs[k + 1]
                scA, scB = C.Scene(A, orient), C.Scene(B, orient)
                for s in (tr['at'] - tr['dur'] * 0.3, tr['at'] - 0.5 / 30, tr['at'], tr['at'] + tr['dur'] * 0.3):
                    f = np.asarray(C.transition_frame(scA, s - A['song']['start'], scB, s - B['song']['start'], tr, s), np.int16)
                    sc, ts = (scA, s - A['song']['start']) if s < tr['at'] else (scB, s - B['song']['start'])
                    full = np.asarray(sc.frame(ts), np.int16)
                    m = C.lettering_mask(full, np.asarray(sc.frame(ts, letters=False)))
                    diff = int((np.abs(f - full).max(-1)[m] > 3).sum())
                    if diff:
                        fail(f"{orient} {tr['type']} into {tr['into']} at {s:.2f}s: {diff} lettering px differ from the plain frame"); bad += 1
                del scA, scB
    if len(problems) == n0:
        seq = ' > '.join(f"{t['type']}({t['dur']:.2f})" for t in trs)
        ok(f"{len(trs)} transitions, no consecutive repeats, {C.TRANS_MIN}-{C.TRANS_MAX}s, sung lines carried across turns"
           + ('' if draft or not deep else ', lettering pixel-identical mid-transition') + f": {seq}")
    tb = C.tbc(spec)
    if tb:
        for orient in ('landscape', 'vertical'):
            lost = C.intro_ink_lost(C.tbc_ic(tb), orient)
            r = C.tbc_rect(tb, orient); x0, y0, x1, y1 = C.SAFE[orient]
            if lost > 0:
                fail(f"TO BE CONTINUED {orient}: tile loses {lost} ink px")
            if r[0] < x0 or r[1] < y0 or r[0] + r[2] > x1 or r[1] + r[3] > y1:
                fail(f"TO BE CONTINUED {orient}: lettering {[int(v) for v in r]} leaves the title-safe area")
        if len(problems) == n0:
            ok(f"'{tb['text']}' card ({tb['seconds']}s, hard cut to black, before the end card): no ink lost, title-safe")


def check_lyric_overlay(spec, subs):
    """Floating lyric overlay: no caption over a tracked face at ANY video frame, none clipped by the safe band
    (16:9: 4 % / 5 % margins; Short: clear of platform UI), no two captions overlapping, no lyric caption left inside
    a panel, and no page whose timing depends on a caption."""
    if not C.overlay_on(spec):
        return
    n0 = len(problems)
    for sub in subs:
        for u in all_units(sub):
            for c in u.get('captions', []):
                if c.get('lyric'):
                    fail(f"{sub['page']}/{u['id']}: lyric caption '{c['text'][:30]}' is attached to a panel - lyrics live on the overlay")
                if 'until' in c and c.get('lyric'):
                    fail(f"{sub['page']}/{u['id']}: lyric caption has 'until' - page timing must not wait on captions")
    sh = spec.get('short') or {}
    for orient, t0, t1 in (('landscape', spec['song']['start'], spec['song']['end']),
                           ('vertical', sh.get('start', spec['song']['start']), sh.get('end', spec['song']['end']))):
        ov = C.lyric_overlay(spec, orient, t0, t1)
        pr = ov.problems(t0, t1, fps=spec.get('fps', 30), face_tol=0.0)
        bad = {}
        for t, text, kind, v in pr:
            bad.setdefault((text, kind), []).append((t, v))
        for (text, kind), xs in bad.items():
            fail(f"lyric overlay {orient}: '{text[:34]}' {kind} at {len(xs)} frame(s) {xs[0][0]:.2f}-{xs[-1][0]:.2f}s (max {max(v for _, v in xs):.3f})")
        hops = sum(len(p.get('hops', [])) for p in ov.paths)
        blk = sum(len(p.get('blocked', [])) for p in ov.paths)
        if blk > 0.02 * sum(len(p['ts']) for p in ov.paths):
            fail(f"lyric overlay {orient}: captions hidden for {blk} frame(s) (no face-free spot) - over 2 % of sung frames")
        elif blk:
            warn(f"lyric overlay {orient}: captions hidden for {blk} frame(s) where no face-free spot exists")
        if not bad:
            ok(f"lyric overlay {orient}: {len(ov.paths)} lines, clear of every tracked face at every frame, inside the safe band"
               + (f" ({hops} fade-hop(s))" if hops else ''))
    return len(problems) == n0


def check_reflow(spec, subs):
    """Living panels: no collisions between settled / settling cells, and every promised face inside its cell at
    every layout state AND through every move (sampled at 15 fps), 16:9 and Short."""
    import reflow as RF
    for sub in subs:
        ff = any(u.get('fullFrame') for u in sub['panels'])
        if not C.is_reflow(sub) and not ff:
            continue
        order = sorted(sub['panels'], key=lambda p: p['at'])
        if not C.is_reflow(sub):      # full frame <-> panel on a static layout: gate only the panels that move
            order = [u for u in order if u.get('fullFrame')]
        lands = [C.T(sub, p['at']) for p in order]
        beat = C.beat_period(sub)
        for orient in ('landscape', 'vertical'):
            col = RF.collisions(lands, beat, sub.get('reflowArrive', 1.0), sub.get('reflowMove', 1.0),
                               family=C.LAYOUTS[sub['layout']]['family'][orient]) if C.is_reflow(sub) else []
            if col:
                fail(f"{sub['page']} {orient}: living panels collide {col[:3]}")
            G = C.layout_geo(orient, sub['layout'], sub.get('splashStyle', 'full'))
            worst = (0, None, None); lead = {}
            dur = sub['song']['end'] - sub['song']['start']
            for u in order:
                size, crop, regions, _, within = C.unit_fit(sub, u, G[u['slot']], sub.get('fps', 30))
                plan = C.unit_plan(sub, u, G[u['slot']], sub.get('fps', 30), regions, size, within)
                for t in np.arange(C.T(sub, u['at']), dur, 1 / 15):
                    geo, _ = C.reflow_geo(sub, orient, u, t, G)
                    if geo is None:
                        continue
                    win = C.cell_window(plan, t, geo, size, within)
                    fs = plan.faces_at(t)
                    iw, ih = size
                    wb = within or (0, 0, iw, ih)
                    # every required region; when the cell shape cannot hold them all (C.cell_fits_faces), the
                    # faces the camera plan promises (a wide two-shot in a tall full-frame arrival shows its lead)
                    keep = range(len(fs))
                    if fs and not C.cell_fits_faces(list(fs), geo['bbox'][2] / max(geo['bbox'][3], 1), wb):
                        keep = plan.expected(t) or [0]
                        lead[orient] = lead.get(orient, 0) + 1
                    for k in keep:
                        f = fs[k]; a = max((f[2] - f[0]) * (f[3] - f[1]), 1)
                        ix = max(0, min(f[2], win[0] + win[2]) - max(f[0], win[0])); iy = max(0, min(f[3], win[1] + win[3]) - max(f[1], win[1]))
                        miss = 1 - ix * iy / a
                        if miss > worst[0]:
                            worst = (miss, u['id'], t + sub['song']['start'])
            short = spec.get('short') or {}
            in_short = sub['song']['end'] > short.get('start', 0) and sub['song']['start'] < short.get('end', 0)
            if worst[0] > 0.05:
                (fail if orient == 'landscape' or in_short else warn)(f"{sub['page']} {orient}: living panels - {worst[1]} face {worst[0]:.0%} out of its cell at {worst[2]:.2f}s")
            else:
                ok(f"{sub['page']} {orient}: living panels - no collisions, faces in frame through every state and move (worst {worst[0]:.0%})"
                   + (f"; {lead[orient]} sample(s) lead-face only (cell shape cannot hold every face)" if lead.get(orient) else ''))


def check_no_still_cards(spec):
    """Nothing on screen is a still (Jason, 2026-10-14): the end card / TO BE CONTINUED must sit over the live
    last page (the renderer default), never over a frozen frame or a still image."""
    for name, cfg in (('endCard', spec.get('endCard') or {}), ('tbc', spec.get('tbc') or {})):
        if cfg.get('bg') not in (None, 'live') and not str(cfg.get('bg', '')).endswith('.mp4'):
            fail(f"{name}: background '{cfg.get('bg')}' is a still - use the live last page (default) or a looping clip")
    ok('end card / TO BE CONTINUED over the live last page (clips keep moving underneath)')


def check_no_repeats(spec):
    """No shot may repeat within a video (16:9 or Short); title intro + end card exempt."""
    for name, (a, b) in (('16:9', (None, None)), ('Short', ((spec.get('short') or {}).get('start'), (spec.get('short') or {}).get('end')))):
        if name == 'Short' and a is None:
            continue
        reps = C.repeat_report(spec, a, b)
        for r in reps:
            fail(f"{name}: {r[0]} repeats {r[1]} {r[2]:.2f}-{r[3]:.2f}s ({r[4]}s): {r[5]}")
        if not reps:
            ok(f'{name}: no repeated shots')


def check_all_clips(spec, subs):
    """HARD GATE (Jason, 2026-10-14): every panel (and splash) in a comic video has a QA-passed animated clip.
    No still-only panels. Fails unless the spec is an explicit preview (`allowStills: true` or `draft`)."""
    missing = [u['id'] for sub in subs for u in all_units(sub) if not u.get('clip') and not u.get('stillOk')]   # stillOk: sequence lead-up insets
    if not missing:
        ok(f'clips: every panel animated ({sum(len(all_units(s)) for s in subs)} panels)'); return
    msg = f"{len(missing)} panel(s) without a clip (still-only is not allowed): {', '.join(dict.fromkeys(missing))}"
    if spec.get('allowStills') or spec.get('draft') or '--allow-stills' in sys.argv:
        warn('PREVIEW ONLY, not deliverable: ' + msg)
    else:
        fail(msg)


def main(path):
    spec = C.load_spec(path)
    draft = bool(spec.get('draft'))
    subs = C.subspecs(spec)
    check_no_repeats(spec)
    print(f"{'DRAFT ' if draft else ''}spec, {len(subs)} page(s):")
    for sub in subs:
        n0 = len(problems)
        check_page(sub, draft)
        if len(problems) == n0:
            ok(f"{sub.get('page', 'page')}: {len(all_units(sub))} panels - clips, hold {C.MIN_HOLD}-{C.MAX_HOLD}s, beats, text")
    check_all_clips(spec, subs)
    check_no_still_cards(spec)
    check_layouts(spec, subs)
    check_unique(spec, subs)
    check_audio(spec)
    check_intro(spec)
    check_endcard(spec)
    check_entrances(spec, subs)
    check_focus(spec, subs)
    check_refs(spec, subs)
    check_transitions(spec, subs, draft, deep='--deep' in sys.argv)
    check_lyric_overlay(spec, subs)
    check_reflow(spec, subs)
    out = os.path.join(C.ROOT, 'out', os.path.basename(os.path.dirname(spec['_path'])), 'qa')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'comic-qa.json'), 'w') as f:
        json.dump({'problems': problems, 'warnings': warnings, 'align': report}, f, indent=2)
    print(f"\nComic QA: {'PASS' if not problems else f'{len(problems)} problem(s)'}"
          f"{f', {len(warnings)} warning(s)' if warnings else ''}  (out/{os.path.basename(out[:-3])}/qa/comic-qa.json)")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith('--')][0]))

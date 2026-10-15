#!/usr/bin/env python3
"""Comic mode renderer.

  python3 scripts/comic_render.py shots/<name>/<name>.comic.json [--out DIR] [--only landscape|vertical]

Writes (never overwriting; -v2, -v3 ... suffixes):
  DIR/comic-scene-1080p.mp4   1920x1080, song section, loudnorm to spec.song.loudness (default -14 LUFS)
  DIR/comic-scene-short.mp4   1080x1920 vertical variant
  DIR/comic-scene-sheet.png   contact sheet of the beats
Page boundaries get smooth transitions (C.page_transitions: per-page pageTransition or the mood auto-picker;
lettering is never moved or masked by them); spec.tbc adds a hard cut to black + 'TO BE CONTINUED...' card before the end card.
Every video and Short opens on the title logo intro (spec.intro, default on; --intro-test writes the stills) and ends on an end card (spec.endCard, default C.ENDCARD_DEFAULT: ~3 s,
'BROUGHT TO YOU BY PROGRESSIVE SLOP' / 'LIKE AND SUBSCRIBE FOR MORE!'); the song tail fades under it.
"""
import argparse, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_lib as C
from PIL import Image, ImageDraw


def master_audio(spec, wav, t0=None, t1=None):
    s = dict(spec['song'], **({'start': t0, 'end': t1} if t0 is not None else {}))
    src = C.resolve(spec, s['audio'])
    dur = s['end'] - s['start']
    lufs = s.get('loudness', -14)
    ec = C.endcard(spec)
    tb = None if ((spec.get('short') or {}).get('trailer') and t0 is not None) else C.tbc(spec)   # trailer Short: no TBC card
    card = (ec['seconds'] if ec else 0.0) + (tb['seconds'] if tb else 0.0)
    # no hard cut at the end: let the song ring on under the end card when there is more of it,
    # and fade the tail naturally (C.TAIL_FADE s, longer when the song continues), then pad silence
    ext = max(0.0, min(card, C.probe_duration(src) - s['end']))
    take = dur + ext
    fl = min(take, max(C.TAIL_FADE, ext + 1.5))
    pre = ['-ss', f"{s['start']:.3f}", '-t', f'{take:.3f}', '-i', src]
    fade = f'afade=t=in:d={0.03 if s["start"] < 0.05 else 0.25}:curve=qsin,afade=t=out:st={take - fl:.3f}:d={fl:.3f}:curve=qsin'
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *pre, '-af', f'{fade},loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json',
                           '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *pre, '-af', f'{fade},{ln},apad=whole_dur={dur + card:.3f}', '-ar', '48000', wav], check=True)


def measure_lufs(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    tail = err[err.rindex('Summary:'):]
    return float(tail.split('I:')[1].split('LUFS')[0])


STATIC_FAIL = []


def render(spec, orient, out_path, wav, sheet_path=None, t0=None, t1=None):
    """Renders every page of the spec back to back into one MP4 (single-page specs are one page)."""
    reps = [] if ((spec.get('short') or {}).get('trailer') and orient == 'vertical' and t0 is not None) else C.repeat_report(spec, t0, t1)   # trailer glimpses: overlap-checked below
    if reps and not spec.get('allowRepeats') and '--allow-repeats' not in sys.argv:
        for r in reps:
            print(f'  REPEAT {r[0]} {r[1]} {r[2]:.2f}-{r[3]:.2f}s ({r[4]}s): {r[5]}')
        raise SystemExit(f'NO-REPEAT GATE FAIL ({orient}): {len(reps)} repeated segment(s), {sum(r[4] for r in reps):.1f}s - add NEW shots (no shot may replay)')
    if not (orient == 'vertical' and (spec.get('short') or {}).get('trailer') and t0 is not None):
        sf = C.sfx_face_report(spec, orient)
        for r in sf:
            print(f'  sfx {r[0]} {r[1]}: {r[2]}')
        if any(r[2] == 'OVER A FACE' for r in sf):
            raise SystemExit(f'SFX-FACE GATE FAIL ({orient}): lettering over a face')
    W, H = C.SIZES[orient]
    fps = spec.get('fps', 30)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                            '-r', str(fps), '-i', '-', '-i', wav, '-map', '0:v', '-map', '1:a',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                            '-c:a', 'aac', '-b:a', '256k', '-shortest', out_path], stdin=subprocess.PIPE)
    t_song0 = spec['song']['start'] if t0 is None else t0
    t_song1 = spec['song']['end'] if t1 is None else t1
    written = 0
    shots = []
    ic = C.intro(spec)
    ts_intro = C.intro_slam(spec, t_song0) if ic else None
    subs = C.subspecs(spec)
    # page transitions replace the hard cuts; in a Short only boundaries fully inside the window get one
    # Trailer Short (spec.short.trailer = [[song_start, beats], ...]): the audio is the contiguous window, the picture is
    # a montage of glimpses from the whole story, cut on the window's beats with a quick crossfade (Jason 2026-10-14)
    trailer = (spec.get('short') or {}).get('trailer') if (orient == 'vertical' and t0 is not None) else None
    segs = []
    if trailer:
        bts = [b - t_song0 for b in C.song_beats(spec) if t_song0 - 1e-3 <= b <= t_song1 + 1e-3]
        bi = 0; prev_end = -1
        for k_, ent in enumerate(trailer):
            src, nb = ent[0], ent[1]
            a_ = 0.0 if k_ == 0 else bts[bi]
            bi = min(bi + nb, len(bts) - 1)
            b_ = (t_song1 - t_song0) if k_ == len(trailer) - 1 else bts[bi]
            if src < prev_end - 1e-3:
                raise SystemExit(f'NO-REPEAT GATE FAIL (trailer): segment {k_} at {src}s overlaps the previous glimpse')
            segs.append((a_, b_, src, ent[2] if len(ent) > 2 else None)); prev_end = src + (b_ - a_)
        print('trailer:', ', '.join(f'{x[2]:.1f}s x{x[1] - x[0]:.1f}' for x in segs))
    trs = [tr for tr in C.page_transitions(spec)
           if tr['dur'] > 0 and (trailer or t_song0 + tr['dur'] / 2 < tr['at'] < t_song1 - tr['dur'] / 2)]
    cache = {}
    def scene(i):
        if i not in cache:
            for k in [k for k in cache if k < i - 1]:
                del cache[k]
            cache[i] = C.Scene(subs[i], orient)
        return cache[i]
    keep = {}
    for i, sub in enumerate(subs):
        if sub['song']['end'] <= t_song0 + 1e-3 or sub['song']['start'] >= t_song1 - 1e-3:
            continue
        # contact sheet moments: each panel landing, each clip mid/freeze, zoom
        for u in sub['panels']:
            keep[sub['song']['start'] - t_song0 + C.T(sub, u['at']) + 0.3] = f"{u['id']} lands"
        tr = sub.get('transition')
        if tr:
            keep[C.T(sub, tr['at']) + sub['song']['start'] - t_song0 - tr['dur'] / 2] = 'zoom into ' + tr['panel']
    for tr in trs:
        keep[tr['at'] - t_song0 - tr['dur'] / 4] = f"{tr['type']} -> {tr['into']}"
    keep = {int(round(k * fps)): v for k, v in keep.items()}
    end_frame = int(round((t_song1 - t_song0) * fps))
    starts = [x['song']['start'] for x in subs]
    ov = C.lyric_overlay(spec, orient, t_song0, t_song1)
    # native 9:16 glimpses (trailer entries with a cell list): full-bleed frames straight from the source clips
    vsh = {}
    if segs and any(x[3] for x in segs):
        import vshot as VS
        for k_, x in enumerate(segs):
            if x[3]:
                tail_ = ((C.endcard(spec) or {}).get('seconds', 0.0) + 0.5) if k_ == len(segs) - 1 else 0.0   # last glimpse keeps moving under the end card
                vsh[k_] = VS.VShot(VS.resolve_cells(spec, C.resolve, x[3]), (W, H), x[1] - x[0] + tail_, fps)
        if ov:   # re-plan the lyrics around the faces actually on screen in the vertical shots
            def vfaces(s_, segs=segs, vsh=vsh):
                tau_ = s_ - t_song0
                k2 = max(k for k, x in enumerate(segs) if x[0] <= tau_ + 1e-9)
                return vsh[k2].faces(tau_ - segs[k2][0]) if k2 in vsh else []
            import lyric_overlay as LO
            ov.faces_fn, ov.obstacles_fn, ov.paths = vfaces, (lambda s_: []), []
            tl = spec['song'].get('timeline'); tl = tl if os.path.isabs(tl) else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', tl)
            ov.plan(LO.cues_from_lines(json.load(open(tl))['lyrics'], t_song0, t_song1))   # floating lyric layer: song clock only, above pages + turns
    f = None
    TXF = 0.2
    seg_k, prev_last, last_f = -1, None, None
    while written < end_frame:
        s = t_song0 + written / fps
        s_audio = s
        if segs:
            tau = written / fps
            k_ = max(k for k, x in enumerate(segs) if x[0] <= tau + 1e-9)
            if k_ != seg_k:
                prev_last, seg_k = last_f, k_
            s = segs[k_][2] + (tau - segs[k_][0])
        i = max(0, sum(1 for st in starts if st <= s + 1e-9) - 1)
        tr = next((x for x in trs if abs(s - x['at']) < x['dur'] / 2), None)
        if segs and seg_k in vsh:
            for k3 in [k for k in vsh if k < seg_k]:
                vsh[k3].free()
            f = vsh[seg_k].frame(written / fps - segs[seg_k][0])
        elif tr:
            j = next(k for k, x in enumerate(subs) if abs(x['song']['start'] - tr['at']) < 1e-6)
            scA, scB = scene(j - 1), scene(j)
            f = C.transition_frame(scA, s - subs[j - 1]['song']['start'], scB, s - subs[j]['song']['start'], tr, s)
        else:
            f = scene(i).frame(max(s - subs[i]['song']['start'], 0.0))
        last_f = f
        if segs and prev_last is not None and s - segs[seg_k][2] < TXF:
            f = Image.blend(prev_last, f, (s - segs[seg_k][2]) / TXF)
        if ov:
            f = ov.draw(f, s_audio)
        if ic:
            f = C.intro_frame(f, orient, ic, written / fps, ts_intro, fps)
            if written == int(round((ts_intro + 0.5) * fps)):
                shots.append((written / fps, 'title intro', f))
        enc.stdin.write(f.tobytes())
        if written in keep:
            shots.append((written / fps, keep[written], f))
        written += 1
    last = f
    # Nothing is ever a still (Jason): the TO BE CONTINUED card and the end card sit over the LIVE last page,
    # whose clips keep ping-ponging and whose camera keeps moving, instead of a frozen last frame.
    s_end = (segs[-1][2] + segs[-1][1] - segs[-1][0]) if segs else t_song1
    li = len(subs) - 1
    while li > 0 and subs[li]['song']['start'] >= s_end - 1e-3:
        li -= 1
    t_live = s_end - subs[li]['song']['start']
    def live(k):
        if segs and (len(segs) - 1) in vsh:
            return vsh[len(segs) - 1].frame(segs[-1][1] - segs[-1][0] + k / fps)
        return scene(li).frame(t_live + k / fps)
    k_live = 0
    tb = None if segs else C.tbc(spec)   # trailer: cut straight from the cliffhanger glimpse to the end card
    if tb and written:   # cut to the dimmed live page, TO BE CONTINUED...
        n = int(round(tb['seconds'] * fps))
        for k in range(n):
            card = C.tbc_frame(orient, tb, k / fps, base=live(k_live)); k_live += 1
            enc.stdin.write(card.tobytes())
            if k == int(n * 0.6):
                shots.append((written / fps, 'to be continued', card))
            written += 1
    ec = C.endcard(spec)
    if ec and orient == 'vertical' and ec.get('shortLines'):   # Short-only end card text
        ec = dict(ec, lines=ec['shortLines'])
    if ec and written:
        n = int(round(ec['seconds'] * fps))
        for k in range(n):
            card = C.endcard_frame(live(k_live), orient, ec, t=k / fps); k_live += 1
            if k == int(0.5 * fps):
                shots.append((written / fps, 'end card', card))
            enc.stdin.write(card.tobytes()); written += 1
    enc.stdin.close()
    if enc.wait():
        raise SystemExit('ffmpeg encode failed')
    # delivery gate: no near-static stretch > 0.4 s anywhere in the final render (frame differencing)
    sc = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'static_check.py'), out_path, '--max', '0.4',
                         '--json', os.path.splitext(out_path)[0] + '-static.json'], capture_output=True, text=True)
    print(sc.stdout.strip().splitlines()[-1] if sc.stdout.strip() else 'static check: no output')
    if sc.returncode:
        print(sc.stdout)
        STATIC_FAIL.append(out_path)
    # dead-air gate: ffmpeg blackdetect + freezedetect (scripts/motion_qa.py) - any black/frozen segment fails
    mq = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'motion_qa.py'), out_path,
                         '--json', os.path.splitext(out_path)[0] + '-motion.json'], capture_output=True, text=True)
    print(mq.stdout.strip())
    if mq.returncode:
        STATIC_FAIL.append(out_path)
    if sheet_path:
        shots.sort(key=lambda s: s[0])
        tw = 480 if orient == 'landscape' else 270
        th = int(tw * H / W)
        cols = 4
        rows = (len(shots) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * (tw + 10) + 10, rows * (th + 34) + 10), (30, 30, 30))
        d = ImageDraw.Draw(sheet)
        for k, (t, lbl, f) in enumerate(shots):
            x = 10 + (k % cols) * (tw + 10); y = 10 + (k // cols) * (th + 34)
            sheet.paste(f.resize((tw, th), Image.LANCZOS), (x, y))
            d.text((x, y + th + 4), f"{t:5.2f}s ({t_song0 + t:.2f})  {lbl}", font=C.font(20), fill=(240, 240, 240))
        sheet.save(sheet_path)


def transition_test(spec, out):
    """Sheet of every transition type at 25/50/75% (synthetic pages: A = warm paper w/ caption, B = cool) + TBC card."""
    import numpy as np
    W, H = 640, 360
    A = np.zeros((H, W, 3), np.float32); A[:] = (200, 120, 60); A[60:300, 40:300] = (240, 220, 160)
    B = np.zeros((H, W, 3), np.float32); B[:] = (40, 70, 130); B[80:280, 340:600] = (120, 200, 230)
    types = [t for t in C.TRANSITIONS if t != 'cut']
    sheet = Image.new('RGB', (3 * (W // 2 + 8) + 180, len(types) * (H // 2 + 8) + 8), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for r, typ in enumerate(types):
        d.text((8, 8 + r * (H // 2 + 8) + H // 4 - 12), typ, font=C.font(26), fill=(240, 240, 240))
        for k, p in enumerate((0.25, 0.5, 0.75)):
            im = Image.fromarray(np.clip(C.transition_mix(A, B, typ, p, 3), 0, 255).astype('uint8')).resize((W // 2, H // 2))
            sheet.paste(im, (180 + k * (W // 2 + 8), 8 + r * (H // 2 + 8)))
    p = C.next_free(os.path.join(out, 'transition_test.png')); sheet.save(p); print('transitions', p)
    tb = C.tbc(spec) or dict(C.TBC_DEFAULT, enabled=True)
    L = C.tbc_frame('landscape', tb, 1.5); V = C.tbc_frame('vertical', tb, 1.5)
    V = V.resize((int(V.width * 1080 / 1920), 1080), Image.LANCZOS)
    im = Image.new('RGB', (L.width + V.width + 30, 1080), (30, 30, 30)); im.paste(L, (0, 0)); im.paste(V, (L.width + 30, 0))
    p = C.next_free(os.path.join(out, 'tbc_test.png')); im.save(p); print('tbc', p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('--out', default='/workspace/comic-experiment/out')
    ap.add_argument('--only', choices=['landscape', 'vertical'])
    ap.add_argument('--intro-test', action='store_true', help='only write OUT/intro_test_landscape.png + intro_test_vertical.png (title logo over the opening frame) and exit')
    ap.add_argument('--transition-test', action='store_true', help='write OUT/transition_test.png: every transition type at 25/50/75%% over two synthetic pages, plus the TO BE CONTINUED card; works on drafts')
    ap.add_argument('--endcard-test', action='store_true', help='only write OUT/endcard_test.png (both orientations side by side) and exit; works on drafts')
    ap.add_argument('--short', choices=['full', 'cut'], default='cut',
                    help='vertical: "cut" uses spec.short {start,end} when present (a ~45 s Short), "full" renders the whole spec')
    a = ap.parse_args()
    spec = C.load_spec(a.spec)
    if a.intro_test:
        os.makedirs(a.out, exist_ok=True)
        ic = C.intro(spec) or C.intro(dict(spec, intro=dict(spec.get('intro') or {}, enabled=True)))
        for orient in ('landscape', 'vertical'):
            s0 = spec['song']['start'] if orient == 'landscape' or not spec.get('short') else spec['short']['start']
            ts = C.intro_slam(spec, s0)
            sub = next((x for x in C.subspecs(spec) if x['song']['start'] <= s0 + ts + 0.5 < x['song']['end']), C.subspecs(spec)[0])
            try:
                base = C.Scene(sub, orient).frame(s0 + ts + 0.5 - sub['song']['start'])
            except Exception:
                base = C.paper(*C.SIZES[orient])
            im = C.intro_frame(base, orient, ic, ts + 0.5, ts, spec.get('fps', 30))
            p = C.next_free(os.path.join(a.out, f'intro_test_{orient}.png')); im.save(p); print('intro', orient, p)
        return
    if a.transition_test:
        os.makedirs(a.out, exist_ok=True)
        transition_test(spec, a.out); return
    if a.endcard_test:
        os.makedirs(a.out, exist_ok=True)
        ec = C.endcard(spec) or C.ENDCARD_DEFAULT
        L = C.endcard_frame(C.paper(*C.SIZES['landscape']), 'landscape', ec)
        V = C.endcard_frame(C.paper(*C.SIZES['vertical']), 'vertical', ec)
        V = V.resize((int(V.width * 1080 / 1920), 1080), Image.LANCZOS)
        im = Image.new('RGB', (L.width + V.width + 30, 1080), (30, 30, 30)); im.paste(L, (0, 0)); im.paste(V, (L.width + 30, 0))
        p = C.next_free(os.path.join(a.out, 'endcard_test.png')); im.save(p); print('endcard', p); return
    if spec.get('draft'):
        raise SystemExit('spec is marked "draft": true (art/clips not generated yet). Fill in images + clip in/out, remove "draft", run npm run check, then render.')
    os.makedirs(a.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'song.wav')
        master_audio(spec, wav)
        results = {}
        if a.only != 'vertical':
            out = C.next_free(os.path.join(a.out, f"{spec.get('outName', 'comic-scene')}-1080p.mp4"))
            sheet = C.next_free(os.path.join(a.out, f"{spec.get('outName', 'comic-scene')}-sheet.png"))
            render(spec, 'landscape', out, wav, sheet)
            results['landscape'] = out; results['sheet'] = sheet
        if a.only != 'landscape':
            out = C.next_free(os.path.join(a.out, f"{spec.get('outName', 'comic-scene')}-short.mp4"))
            vsheet = C.next_free(os.path.join(a.out, f"{spec.get('outName', 'comic-scene')}-short-sheet.png"))
            results['short-sheet'] = vsheet
            cut = spec.get('short') if a.short == 'cut' else None
            if cut:
                wav2 = os.path.join(td, 'short.wav')
                master_audio(spec, wav2, cut['start'], cut['end'])
                render(spec, 'vertical', out, wav2, vsheet, cut['start'], cut['end'])
            else:
                render(spec, 'vertical', out, wav, vsheet)
            results['vertical'] = out
    for k, p in results.items():
        extra = f'  {measure_lufs(p):.1f} LUFS' if p.endswith('.mp4') else ''
        print(f'{k:10s} {p}{extra}')
    if STATIC_FAIL:
        raise SystemExit('DELIVERY GATE FAIL: static stretch > 0.4 s in ' + ', '.join(STATIC_FAIL) + ' (see *-static.json); not deliverable')


if __name__ == '__main__':
    main()

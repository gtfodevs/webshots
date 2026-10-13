#!/usr/bin/env python3
"""Comic mode renderer.

  python3 scripts/comic_render.py shots/<name>/<name>.comic.json [--out DIR] [--only landscape|vertical]

Writes (never overwriting; -v2, -v3 ... suffixes):
  DIR/comic-scene-1080p.mp4   1920x1080, song section, loudnorm to spec.song.loudness (default -14 LUFS)
  DIR/comic-scene-short.mp4   1080x1920 vertical variant
  DIR/comic-scene-sheet.png   contact sheet of the beats
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
    pre = ['-ss', f"{s['start']:.3f}", '-t', f'{dur:.3f}', '-i', src]
    fade = f'afade=t=in:d=0.03,afade=t=out:st={dur - 0.6:.3f}:d=0.6'
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *pre, '-af', f'{fade},loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json',
                           '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *pre, '-af', f'{fade},{ln}', '-ar', '48000', wav], check=True)


def measure_lufs(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    tail = err[err.rindex('Summary:'):]
    return float(tail.split('I:')[1].split('LUFS')[0])


def render(spec, orient, out_path, wav, sheet_path=None, t0=None, t1=None):
    """Renders every page of the spec back to back into one MP4 (single-page specs are one page)."""
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
    for sub in C.subspecs(spec):
        if sub['song']['end'] <= t_song0 + 1e-3 or sub['song']['start'] >= t_song1 - 1e-3:
            continue
        sc = C.Scene(sub, orient)
        # contact sheet moments: each panel landing, each clip mid/freeze, transition
        marks = {}
        for u in sc.all_units():
            marks[C.T(sub, u['at']) + 0.3] = f"{u['id']} lands"
            if u.get('clip'):
                c = u['clip']; t0 = C.T(sub, C.clip_start(sub, u))
                marks[t0 + (c['out'] - c['in']) / 2] = f"{u['id']} clip {c['in']:.1f}-{c['out']:.1f}s"
                marks[t0 + (c['out'] - c['in']) + 0.3] = f"{u['id']} freeze"
        tr = sub.get('transition')
        if tr:
            marks[C.T(sub, tr['at']) - tr['dur'] / 2] = 'zoom into ' + tr['panel']
        # frames are counted on the global clock so pages butt together without drift
        end_frame = int(round((min(sub['song']['end'], t_song1) - t_song0) * fps))
        keep = {}
        for t, lbl in marks.items():
            keep[int(round((sub['song']['start'] - t_song0 + t) * fps))] = lbl
        while written < end_frame:
            t = (written / fps) - (sub['song']['start'] - t_song0)
            f = sc.frame(max(t, 0.0))
            enc.stdin.write(f.tobytes())
            if written in keep:
                shots.append((written / fps, keep[written], f))
            written += 1
    enc.stdin.close()
    if enc.wait():
        raise SystemExit('ffmpeg encode failed')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('--out', default='/workspace/comic-experiment/out')
    ap.add_argument('--only', choices=['landscape', 'vertical'])
    ap.add_argument('--short', choices=['full', 'cut'], default='cut',
                    help='vertical: "cut" uses spec.short {start,end} when present (a ~45 s Short), "full" renders the whole spec')
    a = ap.parse_args()
    spec = C.load_spec(a.spec)
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
            cut = spec.get('short') if a.short == 'cut' else None
            if cut:
                wav2 = os.path.join(td, 'short.wav')
                master_audio(spec, wav2, cut['start'], cut['end'])
                render(spec, 'vertical', out, wav2, None, cut['start'], cut['end'])
            else:
                render(spec, 'vertical', out, wav)
            results['vertical'] = out
    for k, p in results.items():
        extra = f'  {measure_lufs(p):.1f} LUFS' if p.endswith('.mp4') else ''
        print(f'{k:10s} {p}{extra}')


if __name__ == '__main__':
    main()

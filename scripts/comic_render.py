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


def master_audio(spec, wav):
    s = spec['song']
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


def render(spec, orient, out_path, wav, sheet_path=None):
    sc = C.Scene(spec, orient)
    fps = sc.fps
    n = int(round(C.scene_len(spec) * fps))
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{sc.W}x{sc.H}',
                            '-r', str(fps), '-i', '-', '-i', wav, '-map', '0:v', '-map', '1:a',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                            '-c:a', 'aac', '-b:a', '256k', '-shortest', out_path], stdin=subprocess.PIPE)
    # contact sheet moments: each panel landing, each clip mid/freeze, transition, splash, SFX
    marks = {}
    for u in sc.units + [sc.splash]:
        marks[C.T(spec, u['at']) + 0.3] = f"{u['id']} lands"
        if u.get('clip'):
            c = u['clip']; t0 = C.T(spec, c['at'])
            marks[t0 + (c['out'] - c['in']) / 2] = f"{u['id']} clip {c['in']:.1f}-{c['out']:.1f}s"
            marks[t0 + (c['out'] - c['in']) + 0.3] = f"{u['id']} freeze"
    tr = spec['transition']
    marks[C.T(spec, tr['at']) - tr['dur'] / 2] = 'zoom into ' + tr['panel']
    keep = {int(round(t * fps)): lbl for t, lbl in marks.items() if 0 <= t < n / fps}
    shots = []
    for i in range(n):
        f = sc.frame(i / fps)
        enc.stdin.write(f.tobytes())
        if i in keep:
            shots.append((i / fps, keep[i], f))
    enc.stdin.close()
    if enc.wait():
        raise SystemExit('ffmpeg encode failed')
    if sheet_path:
        shots.sort(key=lambda s: s[0])
        tw = 480 if orient == 'landscape' else 270
        th = int(tw * sc.H / sc.W)
        cols = 4
        rows = (len(shots) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * (tw + 10) + 10, rows * (th + 34) + 10), (30, 30, 30))
        d = ImageDraw.Draw(sheet)
        for k, (t, lbl, f) in enumerate(shots):
            x = 10 + (k % cols) * (tw + 10); y = 10 + (k // cols) * (th + 34)
            sheet.paste(f.resize((tw, th), Image.LANCZOS), (x, y))
            d.text((x, y + th + 4), f"{t:5.2f}s ({spec['song']['start'] + t:.2f})  {lbl}", font=C.font(20), fill=(240, 240, 240))
        sheet.save(sheet_path)
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('--out', default='/workspace/comic-experiment/out')
    ap.add_argument('--only', choices=['landscape', 'vertical'])
    a = ap.parse_args()
    spec = C.load_spec(a.spec)
    os.makedirs(a.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'song.wav')
        master_audio(spec, wav)
        results = {}
        if a.only != 'vertical':
            out = C.next_free(os.path.join(a.out, 'comic-scene-1080p.mp4'))
            sheet = C.next_free(os.path.join(a.out, 'comic-scene-sheet.png'))
            render(spec, 'landscape', out, wav, sheet)
            results['landscape'] = out; results['sheet'] = sheet
        if a.only != 'landscape':
            out = C.next_free(os.path.join(a.out, 'comic-scene-short.mp4'))
            render(spec, 'vertical', out, wav)
            results['vertical'] = out
    for k, p in results.items():
        extra = f'  {measure_lufs(p):.1f} LUFS' if p.endswith('.mp4') else ''
        print(f'{k:10s} {p}{extra}')


if __name__ == '__main__':
    main()

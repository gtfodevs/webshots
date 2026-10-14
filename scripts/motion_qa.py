#!/usr/bin/env python3
"""Dead-air gate for rendered videos (Jason 2026-10-14): no black frames, no frozen holds.

  python3 scripts/motion_qa.py VIDEO.mp4 [--black 0.25] [--freeze 0.5] [--json OUT]

ffmpeg blackdetect (pix_th 0.10, picture_black_ratio 0.98) and freezedetect (noise -60 dB) over the whole file.
Exit 1 when any black segment >= --black s or frozen segment >= --freeze s is found."""
import json, re, subprocess, sys, argparse


def scan(path, black=0.25, freeze=0.5):
    vf = f'blackdetect=d={black}:pix_th=0.10:pic_th=0.98,freezedetect=n=-60dB:d={freeze}'
    err = subprocess.run(['ffmpeg', '-v', 'info', '-hide_banner', '-nostats', '-i', path, '-vf', vf, '-an', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    blacks = [{'start': float(a), 'end': float(b), 'dur': float(c)} for a, b, c in
              re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', err)]
    fs = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', err)]
    fe = re.findall(r'freeze_duration: ([\d.]+)', err)
    freezes = [{'start': s, 'dur': float(d)} for s, d in zip(fs, fe)]
    if len(fs) > len(fe):   # frozen through the end of the file
        freezes.append({'start': fs[-1], 'dur': None})
    return {'file': path, 'black': blacks, 'freeze': freezes, 'pass': not blacks and not freezes}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--black', type=float, default=0.25)
    ap.add_argument('--freeze', type=float, default=0.5); ap.add_argument('--json')
    a = ap.parse_args()
    r = scan(a.video, a.black, a.freeze)
    if a.json:
        json.dump(r, open(a.json, 'w'), indent=1)
    for b in r['black']:
        print(f"FAIL black {b['start']:.2f}-{b['end']:.2f}s ({b['dur']:.2f}s)")
    for f in r['freeze']:
        print(f"FAIL frozen from {f['start']:.2f}s ({f['dur']}s)")
    print('motion check:', 'PASS' if r['pass'] else 'FAIL', f"({a.video})")
    sys.exit(0 if r['pass'] else 1)

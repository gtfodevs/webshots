#!/usr/bin/env python3
"""Short engine test render: a mid-lyric page turn with living panels, full frame <-> panel and the floating lyric
overlay, 16:9 + vertical, from the CJC spec (edited in memory only).

  python3 scripts/living_test.py [--out /workspace/crime-comic/out] [--t0 124] [--t1 139]
Writes test_living_landscape.mp4 / test_living_vertical.mp4 (+ -static.json) and *_contact.jpg (6 frames each)."""
import argparse, copy, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_lib as C
import comic_render as R

SPEC = os.path.join(C.ROOT, 'shots/concrete-jungle-cold-comic/concrete-jungle-cold-comic.comic.json')


def snap(B, t):
    return round(min(B, key=lambda b: abs(b - t)), 3)


def test_spec(turn=132.6):
    spec = C.load_spec(SPEC)
    B = C.song_beats(spec)
    turn = snap(B, turn)                       # mid "Soul's true letter, we get better" (131.08-134.26)
    p07, p08 = spec['pages'][6], spec['pages'][7]
    p07['end'] = p08['start'] = turn
    f20, f21 = p07['panels']
    f20['fullFrame'] = {'mode': 'grow', 'at': snap(B, 125.0), 'dur': 1, 'back': 2}   # cell -> full screen -> back
    f21['fullFrame'] = {'mode': 'open', 'hold': 1, 'dur': 1}                          # lands full screen, shrinks in
    p08['layout'] = 'reflow-grid-three'
    p08['reflowArrive'], p08['reflowMove'] = 1.0, 1.0
    for u, t in zip(p08['panels'], (turn, 134.9, 136.9)):
        u['at'] = snap([b for b in B if b >= turn], t)
        u['clip'].pop('at', None)
    spec['tbc'] = None; spec['endCard'] = {'enabled': False}   # test clip: no cards
    return spec


def contact(video, out_jpg, n=6):
    d = C.probe_duration(video)
    with tempfile.TemporaryDirectory() as td:
        ims = []
        for k in range(n):
            p = os.path.join(td, f'{k}.jpg')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{(k + 0.5) * d / n:.2f}', '-i', video, '-frames:v', '1',
                            '-vf', 'scale=-2:540', p], check=True)
            ims.append(p)
        cols = 3 if 'landscape' in video else 6
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *sum([['-i', p] for p in ims], []), '-filter_complex',
                        ''.join(f'[{i}]' for i in range(n)) + f'xstack=inputs={n}:layout=' +
                        '|'.join(f'{"+".join(["w0"] * (i % cols)) or 0}_{"+".join(["h0"] * (i // cols)) or 0}' for i in range(n)),
                        '-q:v', '3', out_jpg], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/workspace/crime-comic/out')
    ap.add_argument('--t0', type=float, default=124.0)
    ap.add_argument('--t1', type=float, default=139.0)
    a = ap.parse_args()
    spec = test_spec()
    os.makedirs(a.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 's.wav')
        R.master_audio(spec, wav, a.t0, a.t1)
        for orient in ('landscape', 'vertical'):
            out = os.path.join(a.out, f'test_living_{orient}.mp4')
            if os.path.exists(out):
                os.remove(out)
            R.render(spec, orient, out, wav, None, a.t0, a.t1)
            contact(out, os.path.join(a.out, f'test_living_{orient}_contact.jpg'))
            print(orient, out)
    if R.STATIC_FAIL:
        raise SystemExit('static gate FAIL: ' + ', '.join(R.STATIC_FAIL))


if __name__ == '__main__':
    main()

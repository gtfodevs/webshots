#!/usr/bin/env python3
"""Deterministic animated logotype intro (music-mode FX engine).

  python3 scripts/logo_intro.py --logo logo.jpg --audio song.mp3 --drop 4.95 --dur 6.5 -o intro.mp4 [--contact sheet.jpg]

Timeline: black -> dark crypt fade-in (dust, green torch flicker, floor mist), logo held dim under a locked_subtle
parallax (translation only, never scaled/warped). A soft light band sweeps across the carved gold (left->right),
then the full reveal slams on the first frame at/after the drop with a brief green glow pulse, dust burst and a
small decaying camera shake (few px). Hold until the end, clean for a cut. Same inputs -> same frames.
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from music_fx import Parallax, build_overlays, shift, rng, ease, Particles, blend


def gold_mask(rgb):
    import cv2
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1] / 255, hsv[..., 2] / 255
    m = ((h > 12) & (h < 35)).astype(np.float32) * np.clip((s - 0.25) * 3, 0, 1) * np.clip((v - 0.25) * 3, 0, 1)
    lum = rgb.astype(np.float32).mean(2) / 255  # silver/grey carved letters too
    m = np.maximum(m, np.clip((lum - 0.35) * 3, 0, 1) * 0.7)
    return cv2.GaussianBlur(m, (0, 0), 1.5)


def render_intro(logo, audio, out, drop=4.95, dur=6.5, fps=30, W=1920, H=1080, seed=7, contact=None):
    import cv2
    base = np.asarray(Image.open(logo).convert('RGB').resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    gm = gold_mask((base * 255).astype(np.uint8))
    par = Parallax('locked_subtle', seed, W / 1280)
    ovs = build_overlays([
        {'type': 'torch', 'torches': [[0.05, 0.56], [0.95, 0.56]], 'color': [0.45, 1.0, 0.4], 'strength': 0.35, 'radius': 0.16},
        {'type': 'mist', 'region': 'floor', 'strength': 0.22},
        {'type': 'dust', 'region': 'full', 'density': 1.0},
        {'type': 'embers', 'region': {'ellipse': [0.05, 0.45, 0.05, 0.2]}, 'color': [0.5, 1.0, 0.35]},
        {'type': 'embers', 'region': {'ellipse': [0.95, 0.45, 0.05, 0.2]}, 'color': [0.5, 1.0, 0.35]},
    ], W, H, seed)
    burst = Particles('dust', W, H, seed=seed * 31, loop=6.0, density=3.0, strength=2.2)
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :].repeat(H, 0)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None].repeat(W, 1)
    diag = xx + 0.25 * (yy - 0.5)  # slightly slanted sweep front
    glow_src = cv2.GaussianBlur(gm, (0, 0), 18)
    r = rng(seed, 'shake'); sph = r.uniform(0, 6.28, 2)
    f_drop = math.ceil(drop * fps - 1e-6)  # first frame at/after the drop
    t_drop = f_drop / fps
    s0, s1 = 1.0, t_drop - 0.25  # sweep window
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(fps), '-i', '-', '-i', audio, '-t', str(dur), '-map', '0:v', '-map', '1:a',
                           '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '256k', '-shortest', out], stdin=subprocess.PIPE)
    N = int(round(dur * fps)); keep = {}
    picks = [int(round(x * (N - 1))) for x in (0.12, 0.3, 0.5, 0.68)] + [f_drop, N - 1]
    for i in range(N):
        t = i / fps; post = t - t_drop
        fade = ease(t / 1.2)
        # reveal level: dim carved stone before the sweep, lit trail behind the front, full at the drop
        if post >= 0: lvl = np.float32(1.0); front = None
        else:
            p = ease((t - s0) / (s1 - s0)) if t > s0 else 0.0
            fx = -0.25 + p * 1.5
            trail = np.clip((fx - diag) / 0.35, 0, 1) * 0.35 * (t > s0)
            lvl = 0.28 + trail; front = np.exp(-((diag - fx) / 0.07) ** 2) * (s0 < t)
        img = base * lvl[..., None] if np.ndim(lvl) else base * lvl
        if front is not None:  # specular band on gold
            img = blend(img, np.broadcast_to(np.float32([1.0, 0.86, 0.5]), img.shape), front * gm * 0.75, 'screen')
        if post >= 0:  # green glow pulse
            g = math.exp(-post / 0.22) * 0.7
            img = blend(img, np.broadcast_to(np.float32([0.45, 1.0, 0.4]), img.shape), glow_src * g, 'screen')
        dx, dy = par.offset(1, t)
        if post >= 0:  # subtle decaying shake, max ~4 px
            k = 4.0 * math.exp(-post / 0.12)
            dx += k * math.sin(2 * math.pi * 23 * post + sph[0]); dy += k * 0.7 * math.sin(2 * math.pi * 19 * post + sph[1])
        img = shift(img, dx, dy)
        f8 = (np.clip(img * fade, 0, 1) * 255).astype(np.uint8)
        f = f8.astype(np.float32) / 255
        for L in ovs:
            c, a = L.render(t); f = blend(f, c, a * fade, L.mode)
        if post >= 0:
            c, a = burst.render(t); f = blend(f, c, a * math.exp(-post / 0.45), 'screen')
        fr = (np.clip(f, 0, 1) * 255).astype(np.uint8)
        ff.stdin.write(fr.tobytes())
        if i in picks: keep[i] = fr
    ff.stdin.close(); ff.wait()
    if contact:
        tw, th = 640, 360; sheet = Image.new('RGB', (tw * 3, th * 2))
        for j, i in enumerate(picks):
            sheet.paste(Image.fromarray(keep[i]).resize((tw, th), Image.LANCZOS), ((j % 3) * tw, (j // 3) * th))
        sheet.save(contact, quality=90)
    return f_drop


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--logo', required=True); a.add_argument('--audio', required=True); a.add_argument('-o', '--out', required=True)
    a.add_argument('--drop', type=float, default=4.95); a.add_argument('--dur', type=float, default=6.5)
    a.add_argument('--fps', type=int, default=30); a.add_argument('--seed', type=int, default=7); a.add_argument('--contact')
    o = a.parse_args()
    fd = render_intro(o.logo, o.audio, o.out, o.drop, o.dur, o.fps, seed=o.seed, contact=o.contact)
    print(f'{o.out}  drop frame {fd} ({fd / o.fps:.3f}s)')


if __name__ == '__main__':
    main()

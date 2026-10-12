#!/usr/bin/env python3
"""Cut a character sheet (N poses side by side on a plain light background) into N transparent PNGs.

  python3 scripts/cutout_sheet.py sheet.jpg --count 4 --names neutral,sword,surprised,cheer -o outdir/kael

Splits on the widest background-only column gaps, then removes the background with rembg
(isnet-general-use) and cleans the alpha (keep the largest blobs, soften the edge), trimming to content.
Falls back to a background-color key if rembg isn't installed.
"""
import argparse, os
import numpy as np
from PIL import Image, ImageFilter


def bg_color(a):
    edge = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    return np.median(edge, axis=0)


def split_columns(a, count):
    bg = bg_color(a)
    fg = (np.abs(a.astype(int) - bg).sum(axis=2) > 40)
    col = fg.sum(axis=0) > 2
    # runs of empty columns
    gaps, i, W = [], 0, len(col)
    while i < W:
        if not col[i]:
            j = i
            while j < W and not col[j]: j += 1
            if i > 0 and j < W: gaps.append((j - i, (i + j) // 2))
            i = j
        else: i += 1
    cuts = sorted(c for _, c in sorted(gaps, reverse=True)[:count - 1])
    if len(cuts) < count - 1:  # touching poses: fall back to equal widths
        cuts = [int(W * k / count) for k in range(1, count)]
    edges = [0] + cuts + [W]
    return [(edges[k], edges[k + 1]) for k in range(count)]


def remove_bg(img, session):
    if session is not None:
        from rembg import remove
        out = remove(img, session=session, alpha_matting=True, alpha_matting_foreground_threshold=240,
                     alpha_matting_background_threshold=15, alpha_matting_erode_size=8)
        return out.convert('RGBA')
    a = np.asarray(img.convert('RGB')).astype(int); bg = bg_color(a)
    d = np.abs(a - bg).sum(axis=2)
    alpha = np.clip((d - 25) * 6, 0, 255).astype(np.uint8)
    out = img.convert('RGBA'); out.putalpha(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.7)))
    return out


def clean(im):
    a = np.asarray(im).copy()
    al = a[:, :, 3]
    try:
        from scipy import ndimage
        lab, n = ndimage.label(al > 40)
        if n > 1:
            sizes = ndimage.sum(np.ones_like(al), lab, range(1, n + 1))
            keep = {i + 1 for i, s in enumerate(sizes) if s >= max(150, 0.02 * sizes.max())}
            mask = np.isin(lab, list(keep))
            mask = ndimage.binary_dilation(mask, iterations=2)
            al[~mask] = 0
    except Exception:
        pass
    a[:, :, 3] = al
    out = Image.fromarray(a)
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('sheet'); ap.add_argument('--count', type=int, required=True)
    ap.add_argument('--names', required=True); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--model', default='isnet-general-use')
    a = ap.parse_args()
    names = a.names.split(',')
    img = Image.open(a.sheet).convert('RGB'); arr = np.asarray(img)
    try:
        from rembg import new_session
        session = new_session(a.model)
    except Exception as e:
        print('rembg unavailable, using color key:', e); session = None
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    for (x0, x1), n in zip(split_columns(arr, a.count), names):
        crop = img.crop((max(0, x0 - 4), 0, min(img.width, x1 + 4), img.height))
        out = clean(remove_bg(crop, session))
        path = f'{a.out}-{n}.png'; out.save(path); print(path, out.size)


if __name__ == '__main__':
    main()

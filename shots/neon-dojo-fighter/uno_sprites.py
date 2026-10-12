#!/usr/bin/env python3
"""Neon Dojo: build fighter sprites (any char; per-char CFG below) from per-pose AI frames on #00FF00 (THE sprite method, fighter edition).
python3 shots/neon-dojo-fighter/uno_sprites.py [char]     (repo root; default char = uno)
Source: channels/progressiveslop/assets/neon-dojo-fighter/source/<char>/<pose>.jpg (ASSET_LIST pose names).
Steps: key #00FF00 + despill -> largest components -> landmarks (head top, belt = widest gold row, lowest pixel)
-> normalise scale on head-top..belt of the upright poses -> MASTER UPPER BODY (idle_a head+torso) pasted on
idle_b + walk frames aligned on the belt (block: master head only, its arms cross the chest) -> downscale to the
960x540 world (Uno ~200px tall = SF2-crisp 2x2 blocks at 1080p) -> one shared palette + 1px dark outline ->
anchor = (belt centre x, lowest opaque row) so the ground row is exact; walk frames get the bob table from their hip.
Writes stage/assets/px/<char>.png + <char>.json (atlas) and out/neon-dojo-fighter/<char>-report.json."""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CH = sys.argv[1] if len(sys.argv) > 1 else 'uno'
SRC = f'{ROOT}/channels/progressiveslop/assets/neon-dojo-fighter/source/{CH}'
PX = f'{os.path.dirname(os.path.abspath(__file__))}/stage/assets/px'; os.makedirs(PX, exist_ok=True)
REP = f'{ROOT}/out/neon-dojo-fighter'; os.makedirs(REP, exist_ok=True)
POSES = ['idle_a', 'idle_b', 'walk_contact_L', 'walk_pass_L', 'walk_contact_R', 'walk_pass_R', 'punch_windup', 'punch_extend',
         'kick_chamber', 'kick_extend', 'special_charge', 'special_release', 'block', 'hit', 'ko_fall', 'ko_down', 'victory']
WALK = ['walk_contact_L', 'walk_pass_L', 'walk_contact_R', 'walk_pass_R']
# per character: master frames (full upper body), head-only master frames, mirrored poses, idle_a height in
# 960x540 world px, belt landmark ('gold' belt row or 'waist' for outfits without one), cyan effect handling
# (fx: cyan energy pulled OUT of the body into a separate additive <pose>__fx layer; strip: cyan haze deleted)
CFG = {
  'uno':  dict(master=['idle_b'] + WALK, head_only=['block'], mirror={'ko_fall'}, target=198, belt='gold', fx=set(), strip=set()),
  'aura': dict(master=WALK, head_only=['block'], mirror={'ko_fall'}, target=188, belt='waist',
               fx={'idle_a', 'punch_extend', 'kick_extend', 'special_charge', 'special_release', 'victory', 'kick_chamber', 'punch_windup'}, strip={'ko_fall'}),
  # TEKKO: walk L/R sources are identical -> the _R frames get their lower body mirrored about the hip so the shuffle
  # alternates; special_release afterimages are green-tinted chrome -> ghost fx layer; hit has a baked spark -> removed;
  # no ko_fall source -> synthesised from hit, tilted back 40 degrees
  'tekko': dict(master=WALK, head_only=['block'], mirror=set(), target=172, belt='dark', fx=set(), strip=set(),
                legswap={'walk_contact_R', 'walk_pass_R'}, core='full', ghost={'special_release'}, spark={'hit'}, synth={'ko_fall': ('hit', 40)}),
  # LOTUS: duplicate sources (punch_windup = idle_a, kick_chamber = walk_pass, special_charge = block) are flagged;
  # special_charge is re-derived from block with a small crouch; petal ring / drifting petals = separate components -> fx
  'lotus': dict(master=WALK, head_only=['block'], mirror=set(), target=208, belt='waist', fx=set(), strip=set(),
                legswap={'walk_contact_R', 'walk_pass_R'}, ccfx={'special_release', 'victory'}, air={'special_release'},
                synth={'ko_fall': ('hit', 40), 'special_charge': ('block', 'crouch')}),
}[CH]
CCFX, AIR = CFG.get('ccfx', set()), CFG.get('air', set())
LEGSWAP, GHOST, SPARK, SYNTH = CFG.get('legswap', set()), CFG.get('ghost', set()), CFG.get('spark', set()), CFG.get('synth', {})
POSES = [p for p in POSES if os.path.exists(f'{SRC}/{p}.jpg') or os.path.exists(f'{SRC}/{p}.png')]
MASTER = [p for p in CFG['master'] if p in POSES]; HEAD_ONLY = CFG['head_only']; MIRROR = CFG['mirror']; TARGET_H = CFG['target']
FX, STRIP = CFG['fx'], CFG['strip']
NCOL = 56

def key(path, mirror=False, fx=False, strip=False, ghost=False, spark=False, ccfx=False):
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    if mirror: im = im[:, ::-1]
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    green = (g > 120) & (g > r + 45) & (g > b + 45)
    a = ~green
    fxm = np.zeros_like(a)
    if fx or strip:   # cyan energy / haze: low red, high green + blue; plus the white-hot cores inside the crackle
        cyan = a & (g - r > 40) & (b - r > 40) & (b > 120)
        core = a & ndimage.binary_dilation(cyan, iterations=4) & (r > 200) & (g > 215) & (b > 215)
        fxm = cyan | core
        a = a & ~fxm
        if strip:   # haze over the body tints chrome blue: pull tinted pixels back to neutral grey
            t = a & (b - r > 22) & (g - r > 12); gr = ((r + g + b) // 3); im = im.copy()
            for i in range(3): im[..., i][t] = gr[t]
            fxm[:] = False
    if ghost:   # translucent afterimages over green: chrome with a green cast -> separate ghost fx (neutral grey-cyan)
        gh = a & (g > r + 12) & (g > b + 8)
        gh = ndimage.binary_opening(gh, iterations=1); gh = ndimage.binary_dilation(gh, iterations=1) & a
        a = a & ~gh; im = im.copy(); lum = (r + b) // 2
        im[..., 0][gh] = lum[gh] * 0.8; im[..., 1][gh] = lum[gh] * 0.95; im[..., 2][gh] = np.minimum(255, lum[gh] * 1.15)
        fxm = fxm | gh
    if spark:   # baked-in hit spark (yellow/white burst): removed, the engine draws its own sparks
        y_ = a & (r > 190) & (g > 160) & (b < 150) & (r - b > 60)
        w_ = a & ndimage.binary_dilation(y_, iterations=6) & (r > 225) & (g > 225) & (b > 200)
        a = a & ~(y_ | w_)
    lab, n = ndimage.label(a); sizes = ndimage.sum(a, lab, range(1, n + 1))
    if ccfx:   # effect drawn as separate shapes (petal ring, drifting petals): every component but the body -> fx
        body = lab == 1 + int(np.argmax(sizes)); fxm = fxm | (a & ~body & np.isin(lab, 1 + np.where(sizes >= 30)[0])); a = body
    keep = np.isin(lab, 1 + np.where(sizes >= max(400, sizes.max() * 0.02))[0]) & a if not ccfx else a; a = keep
    a = ndimage.binary_opening(a, iterations=1)
    # despill: edge band pulls green down to max(r, b)
    edge = a & ~ndimage.binary_erosion(a, iterations=3)
    out = im.copy(); m = np.maximum(r, b); sp = edge & (g > m)
    out[..., 1][sp] = m[sp]
    gs = a & (g > m + 25); out[..., 1][gs] = (m[gs] + 25)  # interior spill clamp
    body = np.dstack([np.clip(out, 0, 255).astype(np.uint8), (a * 255).astype(np.uint8)])
    fxl = np.dstack([np.clip(im, 0, 255).astype(np.uint8), (fxm * 255).astype(np.uint8)])
    return body, (fxl if fxm.sum() > 50 else None)

def landmarks(rgba):
    a = rgba[..., 3] > 0; ys, xs = np.where(a); top, low = ys.min(), ys.max()
    r, g, b = [rgba[..., i].astype(int) for i in range(3)]
    gold = a & (r > 170) & (g > 110) & (b < 90) & (r - b > 90)
    H = low - top; band = range(int(top + H * 0.28), int(top + H * 0.62))
    hx = int(np.median(np.where(a[top:top + 25].any(0))[0]))
    if CFG['belt'] == 'gold':
        cnt = [(gold[y].sum(), y) for y in band]; belt_n, belt = max(cnt)
        gx = np.where(gold[belt])[0]; bx = int(np.median(gx)) if len(gx) else int(xs.mean())
    elif CFG['belt'] == 'dark':   # black mawashi: widest near-black row in the middle band
        dk = a & (r < 75) & (g < 75) & (b < 80); band2 = range(int(top + H * 0.35), int(top + H * 0.75))
        def run(row):   # longest contiguous dark run (the mawashi is one wide band; shading is broken up)
            best = (0, 0); st = None
            for i, v in enumerate(np.append(row, False)):
                if v and st is None: st = i
                elif not v and st is not None: best = max(best, (i - st, st)); st = None
            return best
        cnt = [(run(dk[y]), y) for y in band2]; (belt_n, bs), belt = max(cnt)
        ox_ = np.where(a[belt])[0]; lab_, _ = ndimage.label(a[belt]); seg = np.where(lab_ == lab_[bs])[0]; bx = int((seg.min() + seg.max()) // 2)  # centre of the body segment holding the belt
    else:   # waist: 40% down the figure; centre of the body pixels near the head column (ignores arms)
        belt = int(top + H * 0.40); belt_n = 99; win = int(H * 0.10)
        cols = np.where(a[belt - 4:belt + 4, max(0, hx - win):hx + win].any(0))[0]
        bx = int(np.median(cols) + max(0, hx - win)) if len(cols) else hx
    return dict(top=int(top), low=int(low), belt=int(belt), beltx=bx, headx=hx, x0=int(xs.min()), x1=int(xs.max()), belt_px=int(belt_n))

raw = {}; L = {}; FXR = {}
for p in POSES:
    f = f'{SRC}/{p}.jpg'
    if not os.path.exists(f): f = f'{SRC}/{p}.png'
    raw[p], FXR[p] = key(f, p in MIRROR, p in FX, p in STRIP, p in GHOST, p in SPARK, p in CCFX); L[p] = landmarks(raw[p])
SRC_CUT = []   # source art touching the image border = the generator cut a limb off: regenerate
for p in POSES:
    al = raw[p][..., 3] > 0; sides = {'top': al[:2].sum(), 'bottom': al[-2:].sum(), 'left': al[:, :2].sum(), 'right': al[:, -2:].sum()}
    if FXR.get(p) is not None:
        fa_ = FXR[p][..., 3] > 0; sides = {k: v + {'top': fa_[:2].sum(), 'bottom': fa_[-2:].sum(), 'left': fa_[:, :2].sum(), 'right': fa_[:, -2:].sum()}[k] for k, v in sides.items()}
    cut = [k for k, v in sides.items() if v > 3]
    if cut: SRC_CUT.append(f'{p}: source art touches the image {"/".join(cut)} edge (cut off) - regenerate with margin')
upright = [p for p in POSES if p not in ('ko_fall', 'ko_down')]
def head_w(a, Lm):  # the round chrome head is rigid: widest contiguous run through the head column, top 45 rows
    al = a[..., 3] > 0; best = 0
    for y in range(Lm['top'], Lm['top'] + 45):
        row = al[y]; c = Lm['headx']
        if not row[c]: continue
        l = r = c
        while l > 0 and row[l - 1]: l -= 1
        while r < len(row) - 1 and row[r + 1]: r += 1
        best = max(best, r - l + 1)
    return best
HW = {p: head_w(raw[p], L[p]) for p in upright}; med = float(np.median(list(HW.values())))
scale_src = {}
for p in POSES:
    r_ = HW.get(p, med) / med
    # only rescale a clear outlier with a believable head reading (fists above the head fool the reading)
    scale_src[p] = 1 / r_ if 0.85 < r_ < 1.15 and abs(r_ - 1) > 0.08 else 1.0
# 1. normalise every pose to idle_a's head..belt span (source space)
norm = {}
for p in POSES:
    s = scale_src[p]; im = Image.fromarray(raw[p])
    if abs(s - 1) > 0.01: im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    a = np.asarray(im).copy(); a[..., 3] = np.where(a[..., 3] > 127, 255, 0); norm[p] = a; L[p] = landmarks(a)
    if FXR.get(p) is not None:
        fi = Image.fromarray(FXR[p]); FXR[p] = np.asarray(fi.resize(im.size, Image.LANCZOS) if abs(s - 1) > 0.01 else fi)
# 2. master upper body: idle_a head + torso core (head top .. belt+4, the torso column), pasted aligned on the belt centre
M = norm['idle_a']; ML = L['idle_a']
def core_mask(arr, Lm, head_only=False):
    a = arr[..., 3] > 0; m = np.zeros_like(a); H = Lm['low'] - Lm['top']
    y1 = Lm['top'] + int(H * 0.17) if head_only else Lm['belt'] + 6
    hw = int(H * 0.085); tw = int(H * 0.14)
    if CFG.get('core') == 'full' and not head_only:   # wide bodies (sumo): the whole upper body incl. guard arms
        m[Lm['top']:y1, :] = True; return m & a
    for y in range(Lm['top'], y1):
        w = hw if y < Lm['top'] + H * 0.15 else tw
        cx = Lm['headx'] if y < Lm['top'] + H * 0.15 else Lm['beltx']
        m[y, max(0, cx - w):cx + w] = True
    return m & a
report = {'char': CH, 'source_cut': SRC_CUT, 'head_w': HW, 'scale_src': {k: round(v, 3) for k, v in scale_src.items()}, 'flags': [], 'master': {}}
comp = {}
for p in POSES:
    a = norm[p].copy()
    if p in MASTER or p in HEAD_ONLY:
        mm = core_mask(M, ML, p in HEAD_ONLY); Lp = L[p]
        dx = (Lp['headx'] - ML['headx']) if p in HEAD_ONLY else (Lp['beltx'] - ML['beltx'])
        dy = (Lp['top'] - ML['top']) if p in HEAD_ONLY else (Lp['belt'] - ML['belt'])
        tgt = core_mask(a, Lp, p in HEAD_ONLY)
        a[tgt] = 0   # clear the pose's own core, then paste the master core
        ys, xs = np.where(mm); ty, tx = ys + dy, xs + dx; ok = (ty >= 0) & (ty < a.shape[0]) & (tx >= 0) & (tx < a.shape[1])
        a[ty[ok], tx[ok]] = M[ys[ok], xs[ok]]
        report['master'][p] = 'head' if p in HEAD_ONLY else 'upper body'
    if p in LEGSWAP:   # mirror the lower body (below the belt) about the hip column so the leading leg alternates
        Lp = L[p]; y0 = Lp['belt'] + 8; bx = Lp['beltx']; low = a[y0:].copy(); a[y0:] = 0
        ys, xs = np.where(low[..., 3] > 0); nx = 2 * bx - xs; ok = (nx >= 0) & (nx < a.shape[1])
        a[y0 + ys[ok], nx[ok]] = low[ys[ok], xs[ok]]
        report['master'][p + '_legs'] = 'lower body mirrored about the hip'
    comp[p] = a
for p, (srcp, ang) in SYNTH.items():   # ko_fall from hit, tilted back (counter-clockwise = head goes back/left); 'crouch' = upper body down 3%
    if ang == 'crouch':
        o = comp[srcp]; Ls = L[srcp]; c = int((Ls['low'] - Ls['top']) * 0.03); bl = Ls['belt']; a = o.copy(); a[:bl] = 0
        up = o[:bl]; dst = a[c:bl + c]; m_ = up[..., 3] > 0; dst[m_] = up[m_]; FXR.pop(p, None)
    else:
        a = np.asarray(Image.fromarray(comp[srcp]).rotate(ang, resample=Image.NEAREST, expand=True)).copy()
    a = a.copy(); comp[p] = a; L[p] = landmarks(a); scale_src[p] = 1.0; norm[p] = a
    if p not in POSES: POSES.append(p)
    report['master'][p] = f'synthesised from {srcp}, rotated {ang} deg'
# 3. downscale to the world size (box filter on premultiplied colour), alpha threshold, crop
k = TARGET_H / (L['idle_a']['low'] - L['idle_a']['top'] + 1)
small = {}
for p in POSES:
    a = comp[p].astype(np.float32); al = a[..., 3:4] / 255; pm = np.dstack([a[..., :3] * al, al * 255])
    im = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), 'RGBA'); W2, H2 = round(im.width * k), round(im.height * k)
    s = np.asarray(im.resize((W2, H2), Image.BOX)).astype(np.float32)
    al2 = s[..., 3] / 255; rgb = np.where(al2[..., None] > 0, s[..., :3] / np.maximum(al2[..., None], 1e-3), 0)
    small[p] = (np.clip(rgb, 0, 255).astype(np.uint8), al2 > 0.5)
    if FXR.get(p) is not None:   # effect layer: same scale, soft alpha kept (drawn additively, flickering)
        f_ = FXR[p].astype(np.float32); fa_ = f_[..., 3:4] / 255
        fs = np.asarray(Image.fromarray(np.clip(np.dstack([f_[..., :3] * fa_, fa_ * 255]), 0, 255).astype(np.uint8), 'RGBA').resize((W2, H2), Image.BOX)).astype(np.float32)
        fal = fs[..., 3] / 255; frgb = np.where(fal[..., None] > 0, fs[..., :3] / np.maximum(fal[..., None], 1e-3), 0)
        FXS = np.dstack([np.clip(frgb, 0, 255), np.where(fal > 0.25, np.clip(fal * 1.4, 0, 1) * 255, 0)]).astype(np.uint8)
        small[p] = small[p] + (FXS,)
# 4. shared palette across all poses (median cut on the union) + dark outline
allpx = np.concatenate([small[p][0][small[p][1]] for p in POSES])
pal_img = Image.fromarray(allpx.reshape(-1, 1, 3)).quantize(colors=NCOL, method=Image.MEDIANCUT)
pal = np.array(pal_img.getpalette()[:NCOL * 3]).reshape(-1, 3)
OUTLINE = np.array([18, 6, 34])
frames = {}
for p in POSES:
    rgb, m = small[p][:2]
    q = Image.fromarray(rgb).quantize(palette=pal_img, dither=Image.Dither.NONE)
    rgbq = pal[np.asarray(q)]
    edge = m & ~ndimage.binary_erosion(m)
    rgbq[edge] = (rgbq[edge] * 0.35 + OUTLINE * 0.65).astype(int)
    out = np.zeros(m.shape + (4,), np.uint8); out[..., :3] = rgbq; out[..., 3] = m * 255
    ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = out[y0:y1 + 1, x0:x1 + 1]
    Lp = L[p]; ax = round(Lp['beltx'] * k) - x0
    if p == 'ko_down' or p == 'ko_fall': ax = crop.shape[1] // 2
    frames[p] = dict(img=crop, ax=int(ax), ay=int(crop.shape[0] - 1), hip=int(round((Lp['low'] - Lp['belt']) * k)))
    if len(small[p]) > 2 and (small[p][2][..., 3] > 0).sum() > 8:
        fl = small[p][2]; fy_, fx_ = np.where(fl[..., 3] > 0)
        frames[p]['fx'] = dict(img=fl[fy_.min():fy_.max() + 1, fx_.min():fx_.max() + 1], ox=int(fx_.min() - x0), oy=int(fy_.min() - y0))
# 4b. idle breath from the MASTER: idle_a with the upper body raised 1 / 2 px (rows above the belt move up,
# the belt rows stretch so nothing tears). idle_b is kept in the atlas but not used if its stance differs.
fa = frames['idle_a']; belt_s = round((L['idle_a']['belt'] - L['idle_a']['top']) * k) + 3
for kk in (1, 2):
    im = fa['img'].copy(); im[:belt_s - kk] = fa['img'][kk:belt_s]; im[belt_s - kk:belt_s] = fa['img'][belt_s - kk:belt_s]
    im = np.vstack([np.zeros((kk, im.shape[1], 4), np.uint8), im[:-0 or None]]) if False else im
    frames[f'idle_br{kk}'] = dict(img=im, ax=fa['ax'], ay=fa['ay'], hip=fa['hip'])
    if 'fx' in fa: frames[f'idle_br{kk}']['fx'] = dict(fa['fx'], oy=fa['fx']['oy'] - kk)
wa, wb = frames['idle_a']['img'].shape[1], (frames['idle_b']['img'].shape[1] if 'idle_b' in frames else frames['idle_a']['img'].shape[1])
if 'idle_b' in frames and abs(wa - wb) > 0.1 * wa: report['flags'].append(f'idle_b: stance width {wb}px vs idle_a {wa}px - the feet jump between breath frames; breath built from idle_a (master) instead. Regenerate idle_b as idle_a with chest/shoulders up ~1%')
# 5. atlas
# every atlas cell carries a 3px transparent margin (BP) so no opaque pixel ever touches its rect edge;
# a pixel on the cell border means the art was cut (fighter_qa fails on it)
BP = 3; pad = 2
W = sum(f['img'].shape[1] + 2 * BP + pad + (f['fx']['img'].shape[1] + 2 * BP + pad if 'fx' in f else 0) for f in frames.values())
H = max([f['img'].shape[0] for f in frames.values()] + [f['fx']['img'].shape[0] for f in frames.values() if 'fx' in f]) + 2 * BP
atlas = np.zeros((H, W, 4), np.uint8); meta = {'char': CH, 'world': [960, 540], 'cell_pad': BP, 'frames': {}}; x = 0
for p, f in frames.items():
    h, w = f['img'].shape[:2]; atlas[BP:BP + h, x + BP:x + BP + w] = f['img']
    meta['frames'][p] = dict(rect=[x, 0, w + 2 * BP, h + 2 * BP], ax=f['ax'] + BP, ay=f['ay'] + BP, hip=f['hip'], air=p == 'ko_fall' or p in AIR, down=p == 'ko_down'); x += w + 2 * BP + pad
    if 'fx' in f:
        fi = f['fx']['img']; fh, fw = fi.shape[:2]; atlas[BP:BP + fh, x + BP:x + BP + fw] = fi
        meta['frames'][p]['fx'] = dict(rect=[x, 0, fw + 2 * BP, fh + 2 * BP], ox=f['fx']['ox'], oy=f['fx']['oy']); x += fw + 2 * BP + pad
# bob table for the walk: hip height relative to idle_a (positive = lower)
meta['bob'] = {p: frames['idle_a']['hip'] - frames[p]['hip'] for p in POSES if p.startswith(('walk', 'idle'))}
Image.fromarray(atlas).save(f'{PX}/{CH}.png'); json.dump(meta, open(f'{PX}/{CH}.json', 'w'), indent=1)
# 6. self-checks: off-model / motion flags
def mask(p): return frames[p]['img'][..., 3] > 0
for p in POSES:
    if p in ('ko_fall', 'ko_down'): continue
    h = frames[p]['img'].shape[0]
    if abs(scale_src[p] - 1) > 0.01: report['flags'].append(f'{p}: source scale off by {abs(scale_src[p]-1):.0%} (normalised on head width)')
    if L[p]['belt_px'] < 20: report['flags'].append(f'{p}: gold belt hard to find ({L[p]["belt_px"]} px) - check the outfit')
# master identity (core region pixels identical to idle_a's) on the master frames
for p in MASTER:
    a, b = comp[p], comp['idle_a']; mm = core_mask(M, ML); Lp = L[p]; dx, dy = Lp['beltx'] - ML['beltx'], Lp['belt'] - ML['belt']
    ys, xs = np.where(mm); ty, tx = ys + dy, xs + dx; ok = (ty >= 0) & (ty < a.shape[0]) & (tx >= 0) & (tx < a.shape[1])
    same = np.mean(np.all(a[ty[ok], tx[ok]] == b[ys[ok], xs[ok]], axis=1)); report['master'][p + '_identity'] = round(float(same), 4)
# walk: silhouette change between neighbours, feet alternate
seq = ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L']
for i, p in enumerate(seq):
    q = seq[(i + 1) % 4]; A, B = frames[p], frames[q]
    hh, ww = max(A['img'].shape[0], B['img'].shape[0]), 400
    def place(f):
        c = np.zeros((hh, ww), bool); h, w = f['img'].shape[:2]; x0 = 200 - f['ax']; c[hh - h:, x0:x0 + w] = f['img'][..., 3] > 0; return c
    pa, pb = place(A), place(B); ch = (pa ^ pb).sum() / max(1, (pa | pb).sum())
    report.setdefault('walk_change', {})[f'{p}->{q}'] = round(float(ch), 3)
    if ch < 0.06: report['flags'].append(f'walk {p}->{q}: silhouettes only {ch:.1%} different (motion reads frozen)')
for p in frames: report.setdefault('size', {})[p] = list(frames[p]['img'].shape[:2])
report['bob'] = meta['bob']; report['mirrored'] = sorted(MIRROR)
json.dump(report, open(f'{REP}/{CH}-report.json', 'w'), indent=1)
print(json.dumps(report, indent=1))

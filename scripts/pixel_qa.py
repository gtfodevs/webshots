#!/usr/bin/env python3
"""Pixel-game QA for webshots pixel shots.  python3 scripts/pixel_qa.py <shot> [--no-browser]
Fails (exit 1) on the mistakes Jason has called out: identical walk frames, low-detail blobs,
blur / stray non-pixel text, passive enemies, the NPC "1" pendant, chroma fringe, floating
sprites, NPCs that are hero recolours, and parallax layers that don't move at distinct speeds.
Writes out/<shot>/qa/qa-report.json."""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image

shot = sys.argv[1]; SD = f'shots/{shot}'; PX = f'{SD}/stage/assets/px'; OUT = f'out/{shot}/qa'
os.makedirs(OUT, exist_ok=True)
M = json.load(open(f'{PX}/sprites.json')); A = np.array(Image.open(f'{PX}/sprites.png').convert('RGBA'))
CFG = json.load(open(f'{SD}/stage/qa.json')) if os.path.exists(f'{SD}/stage/qa.json') else {}
fails, notes = [], []
def F(m): fails.append(m)
def frames(a): return [A[y:y+h, x:x+w] for x, y, w, h in M[a]['frames']]

# 1. loops: distinct frames
LOOPS = CFG.get('loops', {})
for a, need in LOOPS.items():
    fr = frames(a); dist = []
    for f in fr:
        if not any(f.shape == g.shape and np.mean(np.any(f != g, axis=2)) < 0.004 for g in dist): dist.append(f)
    for i in range(len(fr)):
        g = fr[(i+1) % len(fr)]
        if need >= 4 and fr[i].shape == g.shape and len(fr) > 1 and np.mean(np.any(fr[i] != g, axis=2)) < 0.004: F(f'{a}: frames {i} and {(i+1)%len(fr)} near-identical')
    notes.append(f'{a}: {len(dist)}/{len(fr)} distinct frames (need {need})')
    if len(dist) < need: F(f'{a}: only {len(dist)} distinct frames (need {need})')

# 1b. motion: neighbouring frames must differ in SILHOUETTE (mask XOR / union), not pixel noise; motion range
from scipy import ndimage
MIN_MASK = CFG.get('min_mask_change', 0.03)
for a, need in LOOPS.items():
    if need < 4: continue
    fr = frames(a); ms = [f[..., 3] > 0 for f in fr]
    for i in range(len(ms)):
        p, q = ms[i], ms[(i + 1) % len(ms)]
        if p.shape != q.shape: continue
        ch = (p ^ q).sum() / max(1, (p | q).sum())
        if ch < MIN_MASK: F(f'{a}: frames {i}->{(i+1)%len(ms)} silhouette change {ch:.1%} < {MIN_MASK:.0%} (duplicate pose)')
    bw = [np.ptp(np.where(m.any(0))[0]) for m in ms]; bh = [np.ptp(np.where(m.any(1))[0]) for m in ms]
    rng = max(max(bw) - min(bw), max(bh) - min(bh))
    notes.append(f'{a}: bbox motion range {rng}px, min neighbour silhouette change {min(((ms[i] ^ ms[(i+1)%len(ms)]).sum() / max(1,(ms[i] | ms[(i+1)%len(ms)]).sum())) for i in range(len(ms))):.1%}')
    if rng < CFG.get('min_bbox_range', 2) and a not in CFG.get('rig', {}): F(f'{a}: motion range only {rng}px across the loop')

# 1c. rig joints: angle ranges, alternation, wings
RL = json.load(open(f'{PX}/rig_log.json')) if os.path.exists(f'{PX}/rig_log.json') else {}
for a, req in CFG.get('rig', {}).items():
    L = RL.get(a)
    if not L: F(f'{a}: no rig log (not rigged?)'); continue
    for key, (lo_rng, what) in req.items():
        if key == 'alternate':
            x = np.array([r[what[0]] for r in L]); y = np.array([r[what[1]] for r in L])
            c = np.corrcoef(x - x.mean(), y - y.mean())[0, 1]; notes.append(f'{a}: {what[0]} vs {what[1]} correlation {c:.2f} (alternating pairs need < 0)')
            if not c < 0: F(f'{a}: {what[0]}/{what[1]} do not alternate (corr {c:.2f})')
            continue
        v = [r[key] for r in L]; rg = max(v) - min(v)
        notes.append(f'{a}: {key} range {min(v):.0f}..{max(v):.0f} ({rg:.0f})')
        if rg < lo_rng: F(f'{a}: {key} range {rg:.0f} < {lo_rng} ({what})')

# 1d. connectivity: one connected sprite per frame (no detached limbs / joint gaps), pelvis-torso continuity
for a in CFG.get('connected', []):
    for i, f in enumerate(frames(a)):
        m = f[..., 3] > 0; lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        if n == 0: continue
        sizes = ndimage.sum(m, lab, range(1, n + 1)); frac = sizes.max() / m.sum()
        if frac < CFG.get('min_connected', 0.97): F(f'{a}[{i}]: sprite splits into {n} pieces (largest {frac:.0%}) - joint gap / detached part'); break
        ys = np.where(m.any(1))[0]; y0, y1 = ys.min(), ys.max(); hgt = y1 - y0
        for yy in range(y0, y1):
            c0 = np.where(m[yy])[0]; c1 = np.where(m[yy + 1])[0]
            if not len(c0) or not len(c1) or (c0.max() < c1.min() or c1.max() < c0.min()):
                F(f'{a}[{i}]: rows {yy}/{yy+1} do not overlap (torso and legs disconnected)'); break
        # pelvis band (45-60% height) must overlap the torso band (25-45%) by >= 4 columns
        tb = m[y0 + int(hgt * 0.25): y0 + int(hgt * 0.45)].any(0); pb = m[y0 + int(hgt * 0.45): y0 + int(hgt * 0.6)].any(0)
        if (tb & pb).sum() < 4: F(f'{a}[{i}]: pelvis band overlaps torso by {(tb & pb).sum()} cols (<4)'); break

# 1e. THE sprite method: walk frames share ONE master upper body -> head/torso pixels identical apart from the bob
for a, v in M.items():
    if not v.get('master_core'): continue
    fr = frames(a); bob = v.get('bob', [0] * len(fr)); m0 = fr[0][..., 3] > 0
    ys = np.where(m0.any(1))[0]; top = ys.min(); hx = int(np.where(m0[top:top + 6].any(0))[0].mean())
    y0, y1, x0, x1 = top, top + 28, hx - 5, hx + 6
    worst = 1.0
    for i, f in enumerate(fr):
        d = bob[i] - bob[0]
        A0 = fr[0][y0:y1, x0:x1].astype(int); Ai = f[y0 + d:y1 + d, x0:x1].astype(int)
        same = np.mean(np.all(A0 == Ai, axis=2)); worst = min(worst, same)
        if same < CFG.get('min_core_same', 0.97): F(f'{a}[{i}]: upper-body core only {same:.0%} identical to frame 0 after the bob ({d:+d}px) - torso is boiling')
    notes.append(f'{a}: master upper body identical across frames (worst {worst:.1%} of core pixels)')

# 1f. idles must breathe (not frozen)
for a in CFG.get('idles', []):
    if a not in M: F(f'idle {a} missing'); continue
    fr = frames(a); diffs = [np.mean(np.any(fr[i] != fr[(i + 1) % len(fr)], axis=2)) for i in range(len(fr))]
    notes.append(f'{a}: {len(fr)} frames, per-frame change {", ".join(f"{d:.1%}" for d in diffs)}')
    if len(fr) < 3 or max(diffs) < 0.01: F(f'idle {a} is frozen ({len(fr)} frames, max change {max(diffs):.1%})')

# 2. detail: min height, colours, no blobs (opaque bbox fill + colour count)
for a in CFG.get('characters', []):
    f = frames(a)[0]; op = f[..., 3] > 0; ys = np.where(op.any(1))[0]; h = ys.max() - ys.min() + 1
    cols = len({tuple(p) for p in f[op][:, :3]})
    if h < CFG.get('min_h', 40): F(f'{a}: sprite height {h}px < {CFG.get("min_h", 40)}')
    if cols < CFG.get('min_colors', 10): F(f'{a}: only {cols} colours (blob)')

# 3. chroma fringe + NPC pendant
key = np.array(CFG.get('key', [232, 21, 122]))
op = A[..., 3] > 0; edge = op & ~(np.roll(op, 1, 0) & np.roll(op, -1, 0) & np.roll(op, 1, 1) & np.roll(op, -1, 1))
d = np.abs(A[..., :3].astype(int) - key).sum(2); fr_px = int((edge & (d < 60)).sum())
notes.append(f'chroma-key edge pixels: {fr_px}')
if fr_px > CFG.get('max_fringe', 25): F(f'{fr_px} sprite edge pixels within 60 of key colour #{"".join("%02X" % c for c in key)}')
for a in CFG.get('npcs', []):
    for i, f in enumerate(frames(a)):
        r, g_, b = [f[..., c].astype(int) for c in range(3)]
        gold = (f[..., 3] > 0) & (r > 170) & (g_ > 120) & (b < 90) & (r - b > 110)
        ys = np.where((f[..., 3] > 0).any(1))[0]; chest = gold[ys.min() + (ys.max()-ys.min())//4: ys.min() + (ys.max()-ys.min())*3//5]
        if chest.sum() > 6: F(f'{a}[{i}]: gold chest pixels ({int(chest.sum())}) - NPC "1" pendant?'); break

# 4. NPC vs hero silhouette similarity
def mask(a):
    f = frames(a)[0]; m = f[..., 3] > 0; ys, xs = np.where(m); m = m[ys.min():ys.max()+1, xs.min():xs.max()+1]
    return np.array(Image.fromarray(m.astype(np.uint8)*255).resize((32, 48), Image.NEAREST)) > 0
for n in CFG.get('npcs', []):
    for h in CFG.get('heroes', []):
        a, b = mask(n), mask(h); iou = (a & b).sum() / max(1, (a | b).sum())
        if iou > CFG.get('max_iou', 0.72): F(f'NPC {n} silhouette IoU {iou:.2f} vs hero {h} (recolour?)')
    notes.append(f'{n}: max IoU vs heroes {max(((mask(n) & mask(h)).sum()/max(1,(mask(n)|mask(h)).sum())) for h in CFG.get("heroes", [])):.2f}')

# 5. combat: every enemy has telegraph+attack anims, every fight has telegraph-then-attack by enemy
CH = json.load(open(f'{SD}/stage/choreo.json'))
for e in CFG.get('enemies', []):
    for s in ('telegraph', 'attack'):
        if f'{e}_{s}' not in M: F(f'enemy {e} has no {s} frames')
for name, fi in CH.get('fights', {}).items():
    ev = fi['events']; tel = [x[0] for x in ev if x[2] == 'telegraph' and x[1] not in ('U', 'A')]
    att = [x[0] for x in ev if x[2] in ('attack', 'orbs', 'slam', 'summon', 'lunge', 'breath') and x[1] not in ('U', 'A')]
    hits = sum(1 for x in ev if x[2] == 'hit')
    if not att: F(f'fight {name}: enemies never attack')
    elif not any(any(t < a for t in tel) for a in att): F(f'fight {name}: attack without telegraph')
    notes.append(f'fight {name}: {len(att)} enemy attacks, {len(tel)} telegraphs, {hits} hits')

# 6. pixel text / blur in the stage source
src = open(f'{SD}/stage/index.html').read()
if re.search(r'\bfillText\s*\(|\bstrokeText\s*\(', src): F('stage uses fillText/strokeText (non-pixel font)')
if not re.search(r'imageSmoothingEnabled\s*=\s*false', src): F('imageSmoothingEnabled=false not set')

# 7. browser stills: blur, DOM text, ground anchoring, parallax speeds
W = json.load(open(f'{PX}/world.json'))
if '--no-browser' not in sys.argv and CFG.get('stills'):
    pairs = [f'{k}={v}' for k, v in CFG['stills'].items()]
    subprocess.run(['node', 'scripts/pixel_stills.mjs', shot, OUT, '--dpr', '4', *pairs], check=True)
    Q = json.load(open(f'{OUT}/qa.json')); air = {k for k, v in M.items() if v.get('air')}
    grounds = set(W['ground'].values()) | {r for rs in W.get('depth_rows', {}).values() for r in rs}; skip = set(CFG.get('ground_exempt', []))
    for lab in CFG['stills']:
        im = np.array(Image.open(f'{OUT}/{lab}.png').convert('RGB')).astype(int)
        b = im.reshape(im.shape[0]//4, 4, im.shape[1]//4, 4, 3)
        nonu = np.mean(np.any(b != b[:, :1, :, :1], axis=(1, 3, 4)))
        if nonu > 0.01: F(f'still {lab}: {nonu:.1%} of 4x4 blocks not uniform (blur / non-nearest scaling)')
        if Q[lab]['text']: F(f'still {lab}: DOM text visible: {Q[lab]["text"][:60]!r}')
        for an, fi, dx, dy, y, *fl in Q[lab]['draws']:
            if (fl and fl[0]) or an in air or an in skip or an not in M: continue
            if not (M[an]['frames'][fi][3] + dy - 1 == y): F(f'{lab}: {an} bottom row != anchor')
            sc = Q[lab].get('scene'); bgk = CFG.get('scene_bg', {}).get(sc)
            allowed = ({W['ground'][bgk]} | (set(W.get('depth_rows', {}).get(bgk, [])) if an.startswith(('crowd', 'wizard', 'jester')) else set())) if bgk else grounds
            if min(abs(y - g) for g in allowed) > 1: F(f'{lab} ({sc}): grounded {an} feet at y={y}, stage ground is {sorted(allowed)}'); break
            # the sprite's lowest opaque pixel (composited position) must land on the anchor row
            fx, fy, fw, fh = M[an]['frames'][fi]; col = A[fy:fy + fh, fx:fx + fw, 3] > 0
            low = dy + int(np.where(col.any(1))[0].max())
            if abs(low - y) > 1: F(f'{lab}: {an} lowest foot pixel y={low} vs ground {y} (floating {y - low}px)'); break
        Image.fromarray(im[::4, ::4].astype(np.uint8)).save(f'{OUT}/{lab}-1x.png')
    # parallax: measure each layer's shift between two walk frames from the pixels themselves
    pa, pb = CFG.get('parallax_pair', [None, None])
    if pa:
        IA = np.array(Image.open(f'{OUT}/{pa}-1x.png')).astype(int); IB = np.array(Image.open(f'{OUT}/{pb}-1x.png')).astype(int)
        meas = []
        for i, L in enumerate(W['forest_layers']):
            Li = np.array(Image.open(f'{PX}/{L["img"]}').convert('RGBA')); tw = Li.shape[1]
            best = None
            # pixels in A that show this layer (match some shift of the layer image), then the shift that explains B
            def vis(I, off):
                sub = np.zeros(I.shape[:2], bool); y0 = L['y']; hh = min(Li.shape[0], I.shape[0] - y0)
                cols = (np.arange(I.shape[1]) + off) % tw; Lr = Li[:hh][:, cols]
                sub[y0:y0+hh] = (Lr[..., 3] > 0) & (np.abs(I[y0:y0+hh] - Lr[..., :3]).sum(2) == 0); return sub
            sa = [(vis(IA, o).sum(), o) for o in range(tw)]; na, oa = max(sa)
            sb = [(vis(IB, (oa + s) % tw).sum(), s) for s in range(0, 60)]; nb, s = max(sb)
            if nb < 200: notes.append(f'parallax layer {i} ({L["img"]}): not on screen in this pair ({nb} px) - skipped'); continue
            meas.append(s); notes.append(f'parallax layer {i} ({L["img"]}, speed {L["speed"]}): measured {s}px shift ({nb} matching px)')
        if len(set(meas)) < len(meas): F(f'parallax layers not distinct: measured shifts {meas}')
        if meas != sorted(meas): F(f'parallax shifts not increasing far->near: {meas}')
    for L in W['forest_layers']:
        Li = np.array(Image.open(f'{PX}/{L["img"]}').convert('RGBA'))[..., :3].astype(int); h2 = Li.shape[1] // 2
        if np.array_equal(Li[:, :h2], Li[:, h2:2*h2][:, ::-1]): F(f'{L["img"]} is mirror-tiled')

json.dump({'fails': fails, 'notes': notes}, open(f'{OUT}/qa-report.json', 'w'), indent=1)
for n in notes: print('  ' + n)
for f in fails: print('  FAIL ' + f)
print(f'pixel QA: {len(fails)} failure(s)'); sys.exit(1 if fails else 0)

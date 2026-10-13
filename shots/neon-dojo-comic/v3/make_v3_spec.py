#!/usr/bin/env python3
"""Neon Dojo v3: beat sheet (make_v3.py) -> renderable comic spec ../neon-dojo-comic-v3.comic.json.
Clip trims come from the 8 fps clip review below; reused panels map to their v1/v2 clips."""
import ast, bisect, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../..'))
import sys; sys.path.insert(0, HERE)
import make_v3 as V
TL = V.TL
B, END = TL['beats'], TL['duration']
def snap(t): return round(min(B, key=lambda b: abs(b - t)), 3)
def next_beat(t): return B[bisect.bisect_right(B, t + 0.05)]
src = open(os.path.join(HERE, '..', 'make_plan.py')).read()
LYR = ast.literal_eval(re.search(r'^LYR = (\[.*?\])\n\n', src, re.S | re.M).group(1))
ASSETS = '/workspace/neon-dojo-comic'

# reused panels -> existing clips (None = static panel: no clip exists for that art)
REUSE_CLIP = {'v01': 'clips/n01.mp4', 'v23': 'clips/n18.mp4', 'v28': 'clips/n09.mp4', 'v29': 'clips/n23.mp4',
              'v32': 'clips/n26.mp4', 's05': None, 'v15': None, 's24': None}
# 8 fps review 2026-10-13: (clean seconds from in=0, note). Reused v1 clips keep their v1 trims.
TRIMS = {
 'v01': (6.0, None), 'v23': (6.0, None), 'v28': (6.0, None), 'v29': (6.0, None), 'v32': (6.0, None),
 'v02': (6.0, None), 'v03': (2.4, 'camera jumps to a face close-up at ~2.5 s (regenerate)'),
 'v04': (3.5, 'after the flash both fighters shrink into the background'), 'v06': (6.0, None),
 'v07': (4.5, 'training dummy morphs into a pile after ~4.5 s'), 'v08': (5.0, 'jump at 5.25 s'),
 'v09': (3.9, 'hands dissolve into a glow after ~4 s'), 's10': (5.0, 'smoke swallows the frame after 5 s'),
 'v12': (4.0, 'rival lineup starts to duplicate after ~4 s'), 'v13': (6.0, None), 'v14': (6.0, None),
 'v16': (3.5, 'TEKKO vanishes after ~3.5 s'), 's17': (4.5, 'ring fades and LOTUS re-poses after 4.5 s'),
 'v18': (5.6, 'jump at 5.75 s'), 'v19': (4.0, 'Aura dissolves into smoke after ~4 s'), 'v20': (6.0, None),
 's21': (6.0, None), 'v22': (5.2, 'jump at 5.25 s'), 'v25': (6.0, None), 'v26': (6.0, None),
 's30': (2.0, "armour bursts, then SHOGUN re-forms whole after ~2 s (regenerate)"), 'v31': (6.0, None),
}
SFX_STYLE = {'a': ([0.72, 0.32], -8), 'b': ([0.3, 0.3], 7), 'c': ([0.7, 0.35], -6), 'splash': ([0.7, 0.28], -7)}
COLORS = [[255, 214, 0], [90, 230, 255], [255, 90, 200], [255, 255, 255]]


def norm(x):
    return re.sub(r'[^A-Z0-9 ]', '', re.sub(r'^\([^)]*\)\s*', '', x).replace('’', "'").upper()).split()


def sung_end(text, at):
    c = [l for l in TL['lyrics'] if norm(l['text']) == norm(text) and abs(l['t'] - at) < 4.0]
    if not c:
        return 0
    l = min(c, key=lambda l: abs(l['t'] - at))
    ts = [w['t'] for w in l['words']]; last = ts[0]
    for t in ts[1:]:
        if t - last > 2.0: break
        last = t
    return min(l['end'], last + 0.6)


def carry_lyrics(pages):
    for i, pg in enumerate(pages):
        tr = pg.get('transition')
        turn = tr['at'] - tr['dur'] if tr else pg['end']
        hops = []
        nxt = pages[i + 1] if i + 1 < len(pages) else None
        for u in pg['panels']:
            for c in u['captions']:
                if c.get('lyric') and sung_end(c['text'], c['at']) > turn + 0.05:
                    hops.append((c, pg['splash'] if tr else (nxt and nxt['panels'][0]), tr['at'] if tr else (nxt and nxt['start'])))
        if tr:
            for c in pg['splash']['captions']:
                if c.get('lyric') and sung_end(c['text'], c['at']) > pg['end'] + 0.05 and nxt:
                    hops.append((c, nxt['panels'][0], nxt['start']))
        for c, dst, at in hops:
            if dst is None or any(d['text'] == c['text'] for d in dst['captions']):
                continue
            used = {d['anchor'] for d in dst['captions']}
            dst['captions'].insert(0, {'text': c['text'], 'anchor': next(a for a in ('tl', 'bl', 'tr', 'br') if a not in used),
                                       'at': round(at, 3), 'lyric': True, 'carried': True})


def build():
    prompts = {p['id']: p for p in json.load(open(os.path.join(HERE, 'prompts.json')))}
    pages, k = [], 0
    starts = [0.0] + [snap(pg['panels'][0][2]) for pg in V.P[1:]]
    # a page never turns while a lyric line is still being sung (a short overrun pushes the turn a beat later)
    for i in range(1, len(starts)):
        for lt, s in LYR:
            e = sung_end(s, lt)
            if lt < starts[i] < e and e - starts[i] < 0.45:
                starts[i] = round(next_beat(e - 0.05), 3)
    for i, pg in enumerate(V.P):
        start, end = starts[i], (starts[i + 1] if i + 1 < len(V.P) else END)
        out = {'id': pg['id'], 'note': f"Act {pg['act']} - {pg['section']} - NEED: {pg['need']}", 'start': round(start, 3),
               'end': round(end, 3), 'layout': pg['layout'], 'panels': []}
        lands = [(start if i else round(B[0], 3)) if j == 0 else snap(p[2]) for j, p in enumerate(pg['panels'])]
        for j, (pid, slot, t, beat, shot, scene, chars, action, cam, sfx, reuse) in enumerate(pg['panels']):
            land = lands[j]
            nxt = lands[j + 1] if j + 1 < len(lands) else end
            pr = prompts[pid]
            lyr = [(lt, s) for lt, s in LYR if (land - 0.6 if (i or j) else -1) <= lt < nxt - 0.3][:2]
            caps = [{'text': s, 'anchor': ['tl', 'bl'][n], 'at': round(max(snap(lt), land), 3), 'lyric': True} for n, (lt, s) in enumerate(lyr)]
            if pid == 'v01':
                caps.insert(0, {'text': 'NEO-KYOTO. THE OLD DOJO IS FADING...', 'anchor': 'tl', 'at': round(B[0], 3)})
                for c_ in caps[1:]: c_['anchor'] = 'bl'
            u = {'id': pid, 'image': f'v3/panels/{pid}.jpg', 'at': round(land, 3), 'location': scene[:60], 'camera': shot,
                 'moment': beat, 'scene': scene, 'prompt': pr['prompt'] or f'REUSE {reuse}', 'refs': pr['refs'],
                 'motionPrompt': pr['motion'], 'captions': caps}
            clip = (f'v3/clips/{pid}.mp4' if not reuse else REUSE_CLIP.get(pid))
            if clip:
                u['clip'] = {'src': clip, 'in': 0.0, 'out': None}
            if sfx:
                pos, rot = SFX_STYLE[slot]
                u['sfx'] = [{'text': sfx, 'at': round(next_beat(next_beat(land)), 3), 'pos': pos, 'rot': rot,
                             'size': 0.2 if slot == 'splash' else 0.17, 'color': COLORS[k % len(COLORS)], 'impact': True}]
                k += 1
            if slot == 'splash':
                dur = round(land - max(b for b in B if b < land - 0.05), 3)
                out['transition'] = {'type': 'zoom', 'panel': out['panels'][-1]['id'], 'at': round(land, 3), 'dur': dur}
                out['splash'] = u
                out['splashStyle'] = pg['splash']
            else:
                u['slot'] = slot
                out['panels'].append(u)
        cut = out['transition']['at'] - out['transition']['dur'] if out.get('transition') else out['end']
        for u in out['panels'] + ([out['splash']] if out.get('splash') else []):
            if 'clip' not in u:
                continue
            page_cut = out['end'] if u is out.get('splash') else cut
            avail = round(page_cut - next_beat(u['at']) - 0.1, 2)
            clean, note = TRIMS[u['id']]
            o = round(min(clean, avail, 6.0), 2)
            u['clip']['out'] = o
            why = [note] if note else []
            if o < clean - 0.01:
                why.append(f'page turns at {page_cut:.2f}s, clip capped to {o}s')
            if why:
                u['clip']['trimNote'] = '; '.join(why)
        pages.append(out)
    carry_lyrics(pages)
    spec = {'title': 'Neon Dojo - comic mode v3 (dramatic story)', 'outName': 'neon-dojo-comic', 'assetsDir': ASSETS, 'fps': 30,
            'defaults': {'holdBeats': 1},
            'song': {'suno': 'ea6b85b9-efbb-40b4-83db-e9bb853f4122', 'audio': 'audio/song.m4a',
                     'audioNote': 'relative to assetsDir; not committed', 'timeline': 'shots/neon-dojo-fighter/stage/timeline.json',
                     'start': 0.0, 'end': END, 'loudness': -14},
            'short': {'start': 112.25, 'end': 155.81, 'note': 'pre-chorus 2 + chorus 2 + bridge + final chorus: belt, blade lock, tag combo, both supers, double finisher; cut points in word gaps (112.16-112.42, 155.66-155.84)'},
            'endCard': {'enabled': True, 'seconds': 3.0, 'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!']},
            'cast': V.CAST, 'pages': pages}
    path = os.path.join(HERE, '..', 'neon-dojo-comic-v3.comic.json')
    json.dump(spec, open(path, 'w'), indent=1, ensure_ascii=False)
    n = sum(len(p['panels']) + (1 if p.get('splash') else 0) for p in pages)
    print(os.path.relpath(path, REPO), n, 'panels', len(pages), 'pages')


if __name__ == '__main__':
    build()

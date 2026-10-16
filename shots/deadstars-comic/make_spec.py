#!/usr/bin/env python3
"""Deadstars: beat sheet (make_plan.py) -> renderable comic spec deadstars-comic.comic.json.
Takes come from the 8 fps clip review below (TAKE); every clip plays near-full length, problems are flagged, not trimmed."""
import ast, bisect, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../..'))
import sys; sys.path.insert(0, HERE)
import make_plan as V
for _pg in V.P:
    _pg.setdefault('act', '-'); _pg.setdefault('need', _pg['stakes'])
    _pg['panels'] = [tuple(p) + (None,) for p in _pg['panels']]
TL = V.TL
B, END = TL['beats'], TL['duration']
def snap(t): return round(min(B, key=lambda b: abs(b - t)), 3)
def next_beat(t): return B[bisect.bisect_right(B, t + 0.05)]
# full sung lines from the timeline (the v1 plan's shortened LYR list cut lines off mid-sentence:
# 'HIT HARD, THEN I STOP' while the singer goes on '...MAN, NO NEED TO DISAPPOINT')
LYR = [(l['t'], re.sub(r'^\([^)]*\)\s*', '', l['text']).replace('’', "'").upper()) for l in TL['lyrics'] if len(l['text'].split()) > 2]
ASSETS = '/workspace/deadstars-comic'

# v3 2026-10-13: d20/d25/d26/d28/s23 -> _e, d22/s29 -> _d (vehicle-only prompts, see motion.txt)
# 8 fps review 2026-10-13 (contact strips + 0/2/4/5.9 s detail sheets of every take; *_oldpanel ignored)
TAKE = {'d01': 'b', 'd02': 'b', 'd03': 'b', 'd04': 'b', 'd06': 'b', 'd07': 'a', 'd08': 'a', 'd09': 'a', 'd10': 'c',
        'd12': 'a', 'd13': 'a', 'd14': 'c', 'd15': 'a', 'd17': 'b', 'd18': 'a', 'd19': 'a', 'd20': 'e', 'd21': 'b',
        'd22': 'd', 'd24': 'b', 'd25': 'e', 'd26': 'e', 'd27': 'c', 'd28': 'e', 'd30': 'a', 'd31': 'a',
        's05': 'a', 's11': 'a', 's16': 'a', 's23': 'e', 's29': 'd'}
# flagged (played at full length, NOT trimmed to hide it; regenerate with the "only these characters" clause)
FLAG = {}   # v3: the 6 flagged ids (+ s29) were replaced by vehicle-only regenerations (_d/_e takes), clean for the full 6 s
TRIMS = {k: (6.0, ('FLAG: ' + FLAG[k]) if k in FLAG else None) for k in TAKE}
SHORT = {'start': 54.08, 'end': 104.48, 'note': 'sky-fight back half: NULLSTAR kills the lights, the jet dogfight, the core break and the crown descending (verse 3 -> hook -> verse 4 -> hook); cut points in word gaps'}
FULL = 6.6  # 6 s clip + 0.44 s anticipation + margin
SFX_STYLE = {'a': ([0.72, 0.32], -8), 'b': ([0.3, 0.3], 7), 'c': ([0.7, 0.35], -6), 'splash': ([0.7, 0.28], -7)}
COLORS = [[255, 214, 0], [90, 230, 255], [255, 90, 200], [255, 255, 255]]


# Character anchor, prepended to every motion prompt so the video model keeps each character's exact look
ANCHOR_HEAD = 'Handsome, sleek, well-designed chrome robots.'
ANCHOR_CAST = {
 'Uno': 'Uno: round smooth chrome dome head, red eyes, headphone ears, purple fur coat, gold 1 chain.',
 'Aura': 'Aura: beautiful grey chrome robot face, red eyes, headphone ears, flowing dark crimson hair, modest crimson bodysuit.',
 'Sensei': 'Sensei: elderly chrome robot, grey robe, white cable beard, cane.',
 'KAZE-9': 'KAZE-9: lean black ninja robot, red scarf, twin blades.',
 'RAIJIN': 'RAIJIN: bulky boxer robot, lightning gauntlets.',
 'TEKKO': 'TEKKO: squat sumo robot, piston arms.',
 'LOTUS': 'LOTUS: long-legged slim crane-kick robot.',
 'SHOGUN': 'SHOGUN: red samurai robot, horned helmet, glowing red katana.',
}
ANCHOR_TAIL = ('Each character keeps the exact same face, body, outfit and size for the entire shot; one continuous shot; '
               'the opening frame matches the image exactly; nothing melts, morphs, transforms, appears or vanishes.')


def anchor(chars):
    names = [n for n in ANCHOR_CAST if n in (chars if isinstance(chars, str) else ' '.join(chars))]
    return ' '.join([ANCHOR_HEAD] + [ANCHOR_CAST[n] for n in names] + [ANCHOR_TAIL])


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
    mot = dict(l.split(' | ', 1) for l in open(os.path.join(HERE, 'motion.txt')).read().splitlines() if ' | ' in l)
    prompts = {j['id']: {'prompt': j['prompt'], 'refs': j['reference_image_paths'], 'motion': mot[j['id']]}
               for j in json.load(open(os.path.join(HERE, 'generate_jobs.json')))}
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
        # pace the page so every clip plays out (~6 s): pull later lands (and the zoom) earlier, never before the
        # previous panel + 1 beat; whatever still does not fit is capped and noted below.
        def prev_beat(x):
            return max([b for b in B if b <= x + 1e-6] or [x])
        sl = [j for j, p in enumerate(pg['panels']) if p[1] == 'splash']
        if sl:
            js = sl[0]
            lands[js] = max(min(lands[js], prev_beat(end - FULL)), lands[js - 1] + 0.4 if js else lands[js])
        for j in range(1, len(lands)):
            if j in sl:
                continue
            js = sl[0] if sl else None
            page_cut = (lands[js] - (lands[js] - prev_beat(lands[js] - 0.05))) if sl else end
            lands[j] = round(max(min(lands[j], prev_beat(page_cut - FULL)), next_beat(lands[j - 1] + 0.05)), 3)
        for j, (pid, slot, t, beat, shot, scene, chars, action, cam, sfx, reuse) in enumerate(pg['panels']):
            land = lands[j]
            nxt = lands[j + 1] if j + 1 < len(lands) else end
            pr = prompts[pid]
            lyr = [(lt, s) for lt, s in LYR if (land - 0.6 if (i or j) else -1) <= lt < nxt - 0.3][:2]
            caps = [{'text': s, 'anchor': ['tl', 'bl'][n], 'at': round(max(snap(lt), land), 3), 'lyric': True} for n, (lt, s) in enumerate(lyr)]
            u = {'id': pid, 'image': f'panels/{pid}.jpg', 'at': round(land, 3), 'location': scene[:60], 'camera': shot,
                 'moment': beat, 'scene': scene, 'prompt': pr['prompt'] or f'REUSE {reuse}', 'refs': pr['refs'],
                 'motionPrompt': pr['motion'], 'captions': caps}
            clip = f'clips/{pid}_{TAKE[pid]}.mp4'
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
    # a lyric line is lettered once per page: the pacing pass lands panels early, so neighbouring panels' lyric
    # windows overlap and the same line was showing on two panels at once (d25 + d26 'NOBODY CAN DENY ...')
    for pg in pages:
        seen = set()
        for u in pg['panels']:
            keep = []
            for c in u['captions']:
                if c.get('lyric') and c['text'] in seen:
                    continue
                seen.add(c['text']); keep.append(c)
            u['captions'] = keep
    carry_lyrics(pages)
    # a finished line gives way to the next one (full-length lines are tall; stacking them overlapped)
    for pg in pages:
        for u in pg['panels'] + ([pg['splash']] if pg.get('splash') else []):
            ly = sorted([c for c in u['captions'] if c.get('lyric')], key=lambda c: c['at'])
            for a, b in zip(ly, ly[1:]):
                if sung_end(a['text'], a['at']) <= b['at'] + 0.05:
                    a['until'] = b['at']
    spec = {'title': 'Deadstars - comic mode (Progressive Slop)', 'outName': 'deadstars-comic', 'assetsDir': ASSETS, 'fps': 30,
            'defaults': {'holdBeats': 1},
            'song': {'suno': '2b485ca1-0de6-4575-8bb1-47cda2c9a273', 'audio': 'song.m4a',
                     'audioNote': 'relative to assetsDir (audio extracted from Suno public mp4); not committed', 'timeline': 'shots/deadstars-comic/timeline.json',
                     'start': 0.0, 'end': END, 'loudness': -14},
            'short': SHORT,
            'intro': {'enabled': True, 'title': 'DEADSTARS', 'subtitle': 'PROGRESSIVE SLOP PRESENTS', 'seconds': 2.6},
            'endCard': {'enabled': True, 'seconds': 3.0, 'lines': ['BROUGHT TO YOU BY PROGRESSIVE SLOP', 'LIKE AND SUBSCRIBE FOR MORE!']},
            'cast': V.CAST, 'pages': pages}
    path = os.path.join(HERE, 'deadstars-comic.comic.json')
    json.dump(spec, open(path, 'w'), indent=1, ensure_ascii=False)
    n = sum(len(p['panels']) + (1 if p.get('splash') else 0) for p in pages)
    print(os.path.relpath(path, REPO), n, 'panels', len(pages), 'pages')


if __name__ == '__main__':
    build()

#!/usr/bin/env python3
"""Music analysis for webshots music mode.

  python3 scripts/analyze_music.py <audio> -o timeline.json [--lyrics lyrics.txt] [--no-words]

Writes a timeline JSON:
  { duration, tempo, beats:[s], downbeats:[s], bars:[{i,t,end}], sections:[{i,t,end,label,energy}],
    energy:[{t,v}] (per beat, 0..1), words:[{w,s,e}], lyrics:[{t,end,text,words:[{w,t}],tag}] }

Beats/tempo: librosa beat tracker. Downbeats: the beat phase (0..3) whose beats carry the most
onset strength + low-frequency energy. Sections: agglomerative segmentation of beat-synced
chroma+MFCC, snapped to bar lines, labelled by energy (intro/verse/chorus/break/outro heuristics).
Words: faster-whisper word timestamps. Lyrics: each lyric line is aligned to the word stream.
"""
import argparse, json, re, subprocess, sys
import numpy as np


def load_audio(path, sr):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def analyze(y, sr, n_sections=None):
    import librosa
    hop = 512
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    # low-end energy per frame for downbeat phase
    S = np.abs(librosa.stft(y, hop_length=hop, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = S[freqs < 150].sum(axis=0)
    low = low / (low.max() + 1e-9)
    on = onset / (onset.max() + 1e-9)
    score = [0.0] * 4
    for k, f in enumerate(beat_frames):
        f = min(f, len(on) - 1)
        score[k % 4] += on[f] + low[f]
    phase = int(np.argmax(score))
    downbeats = beats[phase::4]
    # bars
    bars = [{'i': i, 't': round(float(t), 3), 'end': round(float(downbeats[i + 1]) if i + 1 < len(downbeats) else float(len(y) / sr), 3)}
            for i, t in enumerate(downbeats)]
    # energy per beat (RMS), normalized
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    e = np.array([rms[min(f, len(rms) - 1)] for f in beat_frames])
    if len(e):
        e = np.convolve(e, np.ones(4) / 4, mode='same')
        e = (e - e.min()) / (e.max() - e.min() + 1e-9)
    energy = [{'t': round(float(t), 3), 'v': round(float(v), 3)} for t, v in zip(beats, e)]
    # sections
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=13)
    feat = np.vstack([librosa.util.normalize(chroma), librosa.util.normalize(mfcc)])
    sync = librosa.util.sync(feat, beat_frames, aggregate=np.median)
    dur = len(y) / sr
    k = n_sections or max(4, min(14, int(dur / 14)))
    bounds = librosa.segment.agglomerative(sync, k)
    bt = [0.0] + [float(beats[min(b, len(beats) - 1)]) for b in bounds[1:]]
    # snap to nearest downbeat
    snapped = sorted({min(downbeats, key=lambda d: abs(d - t)) if len(downbeats) else t for t in bt} | {0.0})
    snapped = [float(t) for t in snapped if t < dur - 2]
    secs = []
    for i, t in enumerate(snapped):
        end = snapped[i + 1] if i + 1 < len(snapped) else dur
        if end - t < 2:
            continue
        m = [x['v'] for x in energy if t <= x['t'] < end]
        secs.append({'i': len(secs), 't': round(t, 3), 'end': round(end, 3), 'energy': round(float(np.mean(m)) if m else 0, 3)})
    if secs:
        secs[0]['t'] = 0.0
        med = float(np.median([s['energy'] for s in secs]))
        for s in secs:
            s['label'] = 'high' if s['energy'] > med + 0.08 else 'low' if s['energy'] < med - 0.12 else 'mid'
        secs[0]['label'] = secs[0]['label'] if secs[0]['energy'] > med else 'intro'
        if secs[-1]['energy'] < med:
            secs[-1]['label'] = 'outro'
    return {'duration': round(dur, 3), 'tempo': round(tempo, 2), 'beats': [round(float(b), 3) for b in beats],
            'downbeats': [round(float(d), 3) for d in downbeats], 'bars': bars, 'sections': secs, 'energy': energy}


def whisper_words(path, prompt=None, model='small.en'):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device='cpu', compute_type='int8')
    a = load_audio(path, 16000)
    segs, _ = m.transcribe(a, language='en', word_timestamps=True, vad_filter=False, initial_prompt=prompt, condition_on_previous_text=False)
    out = []
    for s in segs:
        for w in s.words:
            out.append({'w': w.word.strip(), 's': round(w.start, 2), 'e': round(w.end, 2)})
    return out


norm = lambda s: re.sub(r"[^a-z0-9']", '', s.lower())


def align_lyrics(lines, words, duration):
    """Segment the *performed* word stream into lyric lines. Songs repeat hooks and skip or
    change lines, so a lyric sheet is not a script: at each point in the word stream we pick the
    lyric line (any line, reuse allowed, preferring the next one in sheet order) whose tokens best
    match the upcoming words, and display it with the sheet's spelling and Whisper's timing.
    Words that match no line are skipped (ad-libs, mis-hearings)."""
    import difflib
    L = [(tag, text, [norm(w) for w in text.split()]) for tag, text in lines]
    wt = [norm(w['w']) for w in words]
    out, p, last = [], 0, -1
    while p < len(words):
        best = (0.0, None, 0)
        for li, (tag, text, toks) in enumerate(L):
            n = len(toks)
            for span in (n - 1, n, n + 1):
                if span < 1 or p + span > len(words):
                    continue
                r = difflib.SequenceMatcher(None, toks, wt[p:p + span], autojunk=False).ratio()
                if r <= 0.5: continue
                order = 0.08 if li == last + 1 else 0.04 if li > last else 0.0
                r += order
                if r > best[0]:
                    best = (r, li, span)
        if best[1] is None or best[0] < 0.62:
            p += 1
            continue
        _, li, span = best
        tag, text, toks = L[li]
        seg = words[p:p + span]
        ws = text.split()
        sm = difflib.SequenceMatcher(None, toks, [norm(w['w']) for w in seg], autojunk=False)
        h = {}
        for blk in sm.get_matching_blocks():
            for k in range(blk.size): h[blk.a + k] = seg[blk.b + k]['s']
        times = []
        for k in range(len(ws)):
            if k in h: times.append(h[k]); continue
            prev = max([x for x in h if x < k], default=None); nxt = min([x for x in h if x > k], default=None)
            if prev is not None and nxt is not None: times.append(h[prev] + (h[nxt] - h[prev]) * (k - prev) / (nxt - prev))
            elif prev is not None: times.append(h[prev] + 0.25 * (k - prev))
            else: times.append(seg[0]['s'] + 0.25 * k)
        times = [max(times[0], t) for t in times]
        out.append({'t': round(times[0], 2), 'end': round(seg[-1]['e'] + 0.6, 2), 'text': text, 'tag': tag, 'line': li,
                    'words': [{'w': w, 't': round(t, 2)} for w, t in zip(ws, times)], 'matched': round(best[0], 2)})
        last, p = li, p + span
    for i in range(len(out) - 1):
        out[i]['end'] = round(min(out[i]['end'], out[i + 1]['t'] - 0.05), 2)
    return out


def lyric_sections(lyrics, bars, duration):
    """Sections from lyric blocks: consecutive lines with the same tag form a section, snapped to the
    bar line at or before the first word. Gaps of 4+ bars with no vocals become 'instrumental'."""
    if not lyrics:
        return []
    starts = [b['t'] for b in bars] or [0.0]
    snap = lambda t: max([s for s in starts if s <= t + 0.15], default=0.0)
    blocks = []
    for l in lyrics:
        if blocks and blocks[-1]['tag'] == l['tag'] and l['t'] - blocks[-1]['last'] < 6:
            blocks[-1]['last'] = l['end']
        else:
            blocks.append({'tag': l['tag'], 't': snap(l['t']), 'last': l['end']})
    bar_len = (bars[1]['t'] - bars[0]['t']) if len(bars) > 1 else 2.0
    secs = []
    if blocks[0]['t'] > 4 * bar_len:
        secs.append({'t': 0.0, 'label': 'intro'})
    for i, b in enumerate(blocks):
        secs.append({'t': b['t'], 'label': b['tag'] or 'vocal'})
        nxt = blocks[i + 1]['t'] if i + 1 < len(blocks) else duration
        if nxt - b['last'] > 4 * bar_len:
            secs.append({'t': snap(b['last'] + bar_len * 0.5) if snap(b['last'] + bar_len * 0.5) > b['t'] else b['last'], 'label': 'instrumental'})
    secs[0]['t'] = 0.0
    out = []
    for i, s in enumerate(secs):
        end = secs[i + 1]['t'] if i + 1 < len(secs) else duration
        if end - s['t'] > 1:
            out.append({'i': len(out), 't': round(s['t'], 3), 'end': round(end, 3), 'label': s['label']})
    return out


def parse_lyrics(text):
    lines, tag = [], ''
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        tags = re.findall(r'\[([^\]]+)\]', s)
        rest = re.sub(r'\[[^\]]+\]', '', s).strip()
        if tags:
            tag = ' '.join(t.lower() for t in tags)
        if rest:
            lines.append((tag, rest))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio'); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--lyrics'); ap.add_argument('--no-words', action='store_true')
    ap.add_argument('--sections', type=int); ap.add_argument('--whisper-model', default='small.en')
    a = ap.parse_args()
    sr = 22050
    y = load_audio(a.audio, sr)
    tl = analyze(y, sr, a.sections)
    lines = parse_lyrics(open(a.lyrics).read()) if a.lyrics else []
    if not a.no_words:
        prompt = '. '.join(t.rstrip('.,') for _, t in lines[:3]) + '.' if lines else None
        tl['words'] = whisper_words(a.audio, prompt, a.whisper_model)
        if lines:
            tl['lyrics'] = align_lyrics(lines, tl['words'], tl['duration'])
            ls = lyric_sections(tl['lyrics'], tl['bars'], tl['duration'])
            if ls:
                for x in ls:
                    m = [e['v'] for e in tl['energy'] if x['t'] <= e['t'] < x['end']]
                    x['energy'] = round(float(np.mean(m)) if m else 0, 3)
                tl['audio_sections'] = tl['sections']
                tl['sections'] = ls
    json.dump(tl, open(a.out, 'w'), indent=1)
    print(f"timeline: {tl['duration']}s, {tl['tempo']} BPM, {len(tl['beats'])} beats, {len(tl['bars'])} bars, "
          f"{len(tl['sections'])} sections, {len(tl.get('words', []))} words, {len(tl.get('lyrics', []))} lyric lines -> {a.out}")


if __name__ == '__main__':
    main()

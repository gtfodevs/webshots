import bisect
def write(spec, rows, B):
    def nb(t): return B[bisect.bisect_right(B, t + 0.05)]
    L = [f"# Kingdom Come - comic mode panel plan (draft)\n",
         f"Song: Kingdom Come - Hip Hop Fantasy (Suno 7bf4887f-eec0-4614-a285-5557aa4382d5), {spec['song']['end']:.1f} s, 136 BPM (beat ~0.44 s, bar ~1.76 s).",
         f"Timeline/lyrics: `shots/kingdom-come-16bit/stage/timeline.json`. Spec: `shots/kingdom-come-comic/kingdom-come-comic.comic.json`. Prompts: `prompts.json`.\n",
         f"{len(rows)} panels on {len(spec['pages'])} pages; every panel is a different scene (location + camera + moment; QA checks prompt similarity and image pHash).",
         "Rule: each clip starts one beat after its panel lands (static hold ~0.44 s, QA max 0.6 s). Trim every clip to <= 2.5 s.",
         "Files to generate: `panels/<id>.jpg` (16:9, no text) and `clips/<id>.mp4` (Grok Imagine i2v, 480p, 6 s) under `/workspace/kingdom-come-comic/`.\n",
         "Lyric times marked * were estimated (the aligner missed the line).\n"]
    cur = None
    for pid, slot, u, f, dur in rows:
        if pid != cur:
            pg = next(p for p in spec['pages'] if p['id'] == pid)
            L.append(f"\n## {pid} - {pg['note']} ({pg['start']:.2f}-{pg['end']:.2f} s)\n")
            cur = pid
        caps = '; '.join(f"{c['at']:.2f} s \"{c['text']}\"{'*' if c.get('estimated') else ''}" for c in u['captions']) or '-'
        sfx = ', '.join(f"{s['text']} @ {s['at']:.2f} s" for s in u.get('sfx', [])) or '-'
        L.append(f"### {u['id']} - {slot}{' (zoom ' + str(dur) + ' s into it)' if dur else ''} - lands {u['at']:.2f} s, clip {nb(u['at']):.2f} s")
        L.append(f"- Scene: {u['location']} / {u['camera']} / {u['moment']}")
        L.append(f"- Captions: {caps}")
        L.append(f"- SFX: {sfx}")
        L.append(f"- Refs: {', '.join(u['refs'])}")
        L.append(f"- Image prompt: {u['prompt']}")
        L.append(f"- Motion prompt: {u['motionPrompt']}")
        L.append(f"- Expected trim: {u['clip']['expected']} s\n")
    open('/workspace/kingdom-come-comic/plan.md', 'w').write('\n'.join(L))

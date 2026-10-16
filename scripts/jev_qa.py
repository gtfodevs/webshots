#!/usr/bin/env python3
"""Jev-backed judgment checks for the music-video pipeline (text in, decision out; no media is sent).

Rule-based checks run first and stay authoritative: duration (catches truncated 0.54 s downloads),
clip_drift_check.py (NCC / skin / eye rules), motion_qa / static_check frame-diff stats. Jev only answers the
questions those numbers can't: does a vision caption match the shot's text spec, which candidate caption best
fits the brief, does a shot-list entry contradict the song's rules. Anything gated 'escalate' (low confidence or
Jev unavailable) goes to the existing human / vision-LLM review, exactly as before.

  python3 scripts/jev_qa.py caption  SHOTLIST SHOT_ID "vision caption text"
  python3 scripts/jev_qa.py pick     SHOTLIST SHOT_ID captions.json      # {"s07_a.mp4": "caption", ...}
  python3 scripts/jev_qa.py shotlist SHOTLIST [--rules "extra rule text"]  # sanity-check every shot vs the rules
Exit code: 0 all decided OK, 1 something failed/flagged, 2 needs review/escalation.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jev import jev_noul, jev_choice

SHOT_RULES = ("At most 2 characters; locked static camera; one simple action; waist-up framing for characters; robots fully "
              "clothed; lettering never covers a face; SFX lettering only on a motivated cue; lyric lettering matches the sung line.")


# Short visual tags so a caption that never names a character can still be matched to it.
LOOKS = {'Uno': 'chrome robot man, purple fur coat, tan fedora, gold grill, red eyes',
         'Aura': 'chrome robot woman, khaki safari jacket, burgundy scarf, black hair with red streaks, red eyes',
         'Pharaoh': 'skeletal bandaged mummy king, green eyes, gold nemes headdress'}


def spec_text(s):
    t = s.get('text', {})
    return (f"Shot {s['id']} ({s['type']}, {s.get('section')}): location {s.get('location')}; characters "
            f"{', '.join(f'{c} ({LOOKS[c]})' if c in LOOKS else c for c in s.get('characters', [])) or 'none'}; framing {s.get('framing')}; action: {s.get('action')}."
            + (f" Lettering ({t.get('preset')}): \"{t.get('text')}\"." if t else '')
            + (f" Sung: {' / '.join(s['lyrics_sung'])}." if s.get('lyrics_sung') else ''))


def check_caption(shot, caption):
    """Clip/frame pass-fail from a vision caption, run AFTER the numeric checks pass."""
    r = jev_noul(f"SHOT SPEC: {spec_text(shot)}\nVISION CAPTION OF THE GENERATED CLIP: {caption}",
                 'Does the caption describe what the spec asked for?',
                 true='The caption shows the spec\'s characters doing its action in its setting (wording may differ)',
                 false='The caption shows a different or extra character, a different setting, or a different action')
    r['verdict'] = 'escalate' if r['action'] == 'escalate' else ('pass' if r['yes'] and r['action'] == 'act' else
                                                                 ('fail' if not r['yes'] and r['action'] == 'act' else 'review'))
    return r


def pick_candidate(shot, captions):
    """Choose between candidate frames/clips (already past the numeric gates) from their captions."""
    r = jev_choice({'shot_spec': spec_text(shot)}, 'Which candidate best matches the shot spec?', captions)
    r['pick'] = r['choice'] if r['action'] == 'act' and r['choice'] != 'other' else None
    return r


def check_shotlist(sl, rules=SHOT_RULES):
    out = []
    for s in sl['shots']:
        r = jev_noul({'rules': rules, 'shot': spec_text(s)}, 'Does this shot break any of the rules or contradict itself?',
                     true='A rule is clearly broken or the shot is self-contradictory', false='The shot follows the rules')
        out.append({'id': s['id'], 'flag': r['yes'] and r['action'] != 'escalate', 'confidence': r['confidence'], 'action': r['action']})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['caption', 'pick', 'shotlist']); ap.add_argument('shotlist')
    ap.add_argument('shot', nargs='?'); ap.add_argument('arg', nargs='?'); ap.add_argument('--rules', default='')
    a = ap.parse_args(); sl = json.load(open(a.shotlist))
    if a.cmd == 'shotlist':
        res = check_shotlist(sl, SHOT_RULES + (' ' + a.rules if a.rules else ''))
        print(json.dumps(res, indent=1)); flagged = [r['id'] for r in res if r['flag']]
        print('flagged:', flagged or 'none'); sys.exit(1 if flagged else (2 if any(r['action'] == 'escalate' for r in res) else 0))
    shot = next(s for s in sl['shots'] if s['id'] == a.shot)
    if a.cmd == 'caption':
        r = check_caption(shot, a.arg); print(json.dumps(r)); sys.exit({'pass': 0, 'fail': 1}.get(r['verdict'], 2))
    r = pick_candidate(shot, json.load(open(a.arg))); print(json.dumps(r)); sys.exit(0 if r['pick'] else 2)


if __name__ == '__main__':
    main()

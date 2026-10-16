#!/usr/bin/env python3
"""Tiny client for Jev (TypeSafe "System One"): cheap text-only yes/no, choice and score decisions.

Use it ONLY for judgment calls that would otherwise go to a bigger LLM (e.g. "does this vision caption match
the shot spec?", "which candidate caption best fits the brief?"). Anything a number decides (duration,
frame-diff, NCC, skin share) stays rule-based in code. Jev cannot see images: feed it text (captions, metrics).

  from jev import jev_noul, jev_choice, jev_score
  r = jev_noul(state, "Does the caption match the shot spec?")
  r['action']  -> 'act' (conf > 0.9) | 'review' (0.5-0.9, see r['top']) | 'escalate' (< 0.5 or Jev unavailable)

Key: env JEV_API_KEY (never logged). Endpoint: direct TypeSafe API (POST /v1/systemone, model jev-latest);
set JEV_ENDPOINT=openrouter to use OpenRouter (~typesafe/jev-latest, needs an OpenRouter key in JEV_API_KEY).
Every call is appended (question, answer, confidence; never the key) to $JEV_LOG (default /tmp/jev-decisions.jsonl).
"""
import json, os, sys, time, urllib.request, urllib.error

ENDPOINTS = {'typesafe': ('https://api.typesafe.ai/v1/systemone', 'jev-latest'),
             'openrouter': ('https://openrouter.ai/api/alpha/decisions', '~typesafe/jev-latest')}
ESCALATE_BELOW, ACT_ABOVE = 0.5, 0.9   # confidence gate (single reviewable place)
LOG = os.environ.get('JEV_LOG', '/tmp/jev-decisions.jsonl')


class JevUnavailable(Exception):
    pass


def available():
    return bool(os.environ.get('JEV_API_KEY'))


def _post(questions, state, timeout=20):
    key = os.environ.get('JEV_API_KEY')
    if not key: raise JevUnavailable('JEV_API_KEY not set')
    url, model = ENDPOINTS[os.environ.get('JEV_ENDPOINT', 'typesafe')]
    body = json.dumps({'model': model, 'state': state, 'questions': questions}).encode()
    last = None
    for attempt in range(4):   # first try + 3 retries on 429/5xx/network
        req = urllib.request.Request(url, body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}: {e.read()[:300].decode(errors="replace")}'
            if e.code != 429 and e.code < 500: break
        except (urllib.error.URLError, TimeoutError) as e:
            last = f'network: {e}'
        if attempt < 3: time.sleep(0.5 * 2 ** attempt)
    raise JevUnavailable(last)


def _gate(conf):
    return 'escalate' if conf < ESCALATE_BELOW else ('act' if conf > ACT_ABOVE else 'review')


def _log(rec):
    try:
        with open(LOG, 'a') as f: f.write(json.dumps(rec) + '\n')
    except OSError: pass


def _ask(kind, state, q, shape):
    try:
        a = _post({'q': q}, state)['answers']['q']
    except (JevUnavailable, KeyError, ValueError) as e:
        r = {'type': kind, 'action': 'escalate', 'error': str(e), 'confidence': 0.0, 'probabilities': {}, 'top': []}
    else:
        r = shape(a); r['type'] = kind; r['action'] = _gate(r['confidence'])
    _log({'t': time.time(), 'type': kind, 'question': q.get('instructions'), 'answer': {k: r.get(k) for k in ('choice', 'score', 'yes', 'probabilities')},
          'confidence': r['confidence'], 'action': r['action'], 'error': r.get('error')})
    return r


def jev_noul(state, question, true=None, false=None):
    """Yes/no. Returns {yes: bool, probabilities: {yes, no}, confidence, action, top}."""
    q = {'type': 'noul', 'instructions': question}
    if true or false: q['criteria'] = {k: v for k, v in (('true', true), ('false', false)) if v}
    def shape(a):
        p = float(a['noul']); probs = {'yes': round(p, 4), 'no': round(1 - p, 4)}
        return {'yes': p >= 0.5, 'probabilities': probs, 'confidence': max(p, 1 - p), 'top': sorted(probs, key=probs.get, reverse=True)}
    return _ask('noul', state, q, shape)


def jev_choice(state, question, options, top_n=2):
    """Pick one. options: {name: description}; an 'other' option is always added. Returns {choice, probabilities, confidence, action, top}."""
    opts = dict(list(options.items())[:254])
    opts.setdefault('other', 'None of the listed options fits')
    def shape(a):
        probs = a.get('probabilities') or {a['choice']: a['confidence']}
        return {'choice': a['choice'], 'probabilities': probs, 'confidence': float(a['confidence']),
                'top': sorted(probs, key=probs.get, reverse=True)[:top_n]}
    return _ask('choice', state, {'type': 'choice', 'instructions': question, 'criteria': opts}, shape)


def jev_score(state, question, levels):
    """Rate on 2-10 described levels (list, lowest first). Returns {score (0-based expected level index), probabilities, confidence, action}."""
    def shape(a):
        return {'score': float(a['score']), 'probabilities': a.get('probabilities', {}), 'confidence': float(a['confidence']), 'top': [round(float(a['score']))]}
    return _ask('score', state, {'type': 'score', 'instructions': question, 'criteria': list(levels)}, shape)


if __name__ == '__main__':   # smoke test: python3 scripts/jev.py
    print('noul  ', json.dumps(jev_noul('Clip s07: caption "a chrome robot in a purple fur coat smirks, gold grill visible, static camera".',
                                       'Does the caption show Uno (chrome robot, purple fur coat, gold grill)?')))
    print('choice', json.dumps(jev_choice('Spec: Aura raises a torch in the crypt, waist-up, locked camera.',
                                         'Which candidate caption best matches the spec?',
                                         {'a': 'chrome woman robot lifts a burning torch in a stone tomb, waist-up',
                                          'b': 'chrome man robot dances in a desert, full body, camera pans',
                                          'c': 'mummy king rises from a sarcophagus'})))
    print('score ', json.dumps(jev_score('Caption: blurry frame, faces smeared, extra arm on the robot.',
                                        'How usable is this frame for the music video?',
                                        ['Unusable: broken anatomy or wrong character', 'Usable with fixes', 'Clean and on-model'])))

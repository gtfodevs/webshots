#!/usr/bin/env node
// Fighter QA for pixel fighting-game shots (any shot with stage/fight.js).  node scripts/fighter_qa.mjs <shot>
// Fails (exit 1) on: HUD / banner text not in the bitmap pixel font, fighters not on the stage ground,
// an exchange where the opponent never swings back, identical consecutive frames in an animation,
// a master core that changes between frames, too many hits per bar, montage-only fighters using moves they don't have.
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const shot = process.argv[2], SD = `shots/${shot}/stage`, OUT = `out/${shot}/qa`; mkdirSync(OUT, { recursive: true });
const ctx = {}; vm.createContext(ctx); vm.runInContext(readFileSync(`${SD}/fight.js`, 'utf8'), ctx); const F = ctx.FIGHT;
const TL = JSON.parse(readFileSync(`${SD}/timeline.json`, 'utf8')); const E = F.build(TL);
const fails = [], notes = [], fail = (m) => fails.length < 200 && fails.push(m);

// 1. pixel font only
const src = readFileSync(`${SD}/index.html`, 'utf8');
if (/\b(fillText|strokeText)\s*\(|\.font\s*=/.test(src)) fail('HUD: canvas fillText/strokeText/ctx.font used (non-pixel font)');
if (!/imageSmoothingEnabled\s*=\s*false/.test(src)) fail('imageSmoothingEnabled = false not set');
if (!existsSync(`${SD}/assets/px/font8.png`)) fail('assets/px/font8.png missing (run build_assets.py)');
const body = src.replace(/<head[\s\S]*?<\/head>|<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<!--[\s\S]*?-->|<[^>]+>/g, '').trim();
if (body) fail(`DOM text in the page body: ${body.slice(0, 60)}`);
if (/fonts\.googleapis|font-family/.test(src)) fail('web fonts referenced in the stage');
notes.push('pixel font: all text goes through text()/logo() on the 8px bitmap font');

// 2. animations: no identical consecutive frames; master core identical (translation only)
const core = (rs) => rs.filter((r) => r[5] === 'core'), norm = (rs) => { const x0 = Math.min(...rs.map((r) => r[0])), y0 = Math.min(...rs.map((r) => r[1])); return JSON.stringify(rs.map((r) => [r[0] - x0, r[1] - y0, r[2], r[3], r[4]])); };
const SPR = {}; for (const c of Object.keys(F.SPRITE_ANIMS || {})) {
  const mp = `${SD}/assets/px/${c}.json`; if (!existsSync(mp)) { fail(`${c}: sprite atlas ${mp} missing (run the sprite build)`); continue; }
  SPR[c] = JSON.parse(readFileSync(mp, 'utf8'));
  for (const [a, A] of Object.entries(F.SPRITE_ANIMS[c])) {
    if (A.frames.length !== A.durations.length) fail(`${c}.${a}: durations/frames mismatch`);
    A.frames.forEach((p, i) => { const fr = SPR[c].frames[p]; if (!fr) return fail(`${c}.${a}: pose ${p} not in the atlas`);
      const cp = SPR[c].cell_pad || 0; if (fr.ay !== fr.rect[3] - 1 - cp) fail(`${c}.${p}: anchor row ${fr.ay} is not the lowest content row ${fr.rect[3] - 1 - cp}`);
      const j = i + 1 < A.frames.length ? i + 1 : (A.loop ? 0 : -1); if (j >= 0 && j !== i && A.frames[j] === p) fail(`${c}.${a}: frames ${i} and ${j} identical (${p})`); });
  }
  // cut-off art: no opaque pixel may touch its atlas cell edge, the lowest opaque row must be the anchor row
  const py = spawnSync('python3', ['-c', `
import json, sys, numpy as np
from PIL import Image
m = json.load(open(sys.argv[1])); A = np.asarray(Image.open(sys.argv[2]).convert('RGBA'))[..., 3] > 0; bad = []
for p, f in m['frames'].items():
    for kind, r in [('body', f['rect'])] + ([('fx', f['fx']['rect'])] if 'fx' in f else []):
        x, y, w, h = r; c = A[y:y + h, x:x + w]
        e = [k for k, v in (('top', c[0]), ('bottom', c[-1]), ('left', c[:, 0]), ('right', c[:, -1])) if v.any()]
        if e: bad.append(f'{p} {kind}: opaque pixels touch the cell {"/".join(e)} edge (clipped)')
        if kind == 'body' and c.any() and int(np.where(c.any(1))[0].max()) != f['ay']: bad.append(f'{p}: lowest opaque row {int(np.where(c.any(1))[0].max())} != anchor {f["ay"]}')
print(json.dumps(bad))`, mp, mp.replace('.json', '.png')], { encoding: 'utf8' });
  if (py.status !== 0) fail(`${c}: atlas edge check crashed: ${py.stderr.slice(-200)}`); else JSON.parse(py.stdout).forEach((m) => fail(`${c}.${m}`));
  const rp = `out/${shot}/${c}-report.json`; if (existsSync(rp)) { const r = JSON.parse(readFileSync(rp, 'utf8'));
    for (const [k, v] of Object.entries(r.master || {})) if (k.endsWith('_identity') && v < 0.97) fail(`${c}: master upper body identity ${k} ${v} < 0.97`);
    for (const [k, v] of Object.entries(r.walk_change || {})) if (v < 0.03) fail(`${c}: walk ${k} silhouette change ${v} < 3%`);
    (r.flags || []).forEach((f) => notes.push(`${c} ART FLAG: ${f}`)); (r.source_cut || []).forEach((f) => fail(`${c} SOURCE CUT: ${f}`)); }
  notes.push(`${c}: sprite atlas, ${Object.keys(SPR[c].frames).length} poses`);
}
for (const c of Object.keys(F.CHARS)) {
  if (SPR[c]) continue;
  let ref = null;
  for (const a of F.movesOf(c)) {
    const A = F.ANIMS[a], n = A.frames.length;
    for (let i = 0; i < n; i++) {
      const j = i + 1 < n ? i + 1 : (A.loop ? 0 : -1); if (j < 0 || j === i) continue;
      if (F.frameKey(c, a, i) === F.frameKey(c, a, j)) fail(`${c}.${a}: frames ${i} and ${j} identical`);
    }
    if (A.durations.length !== n) fail(`${c}.${a}: durations/frames mismatch`);
    for (let i = 0; i < n; i++) { const cr = core(F.poseRects(c, a, i)); if (!cr.length) continue; const k = norm(cr); if (ref === null) ref = k; else if (k !== ref) fail(`${c}.${a}[${i}]: master core differs from idle[0]`); }
  }
  notes.push(`${c}: moves ${F.movesOf(c).join('/')}`);
}

// 3. sampled fights: grounded feet, legal moves, idle never frozen
// ---- stage figure rule (every stage, automatic): animated background figures are individual cutouts over an inpainted clean plate
{ const PX = `${SD}/assets/px`, keys = new Set(readdirSync(PX).filter((n) => /^stage-[^-]+\.json$/.test(n)).map((n) => n.slice(6, -5)));
  for (const S of Object.values(F.STAGES || {})) if (S.art) { if (!keys.has(S.art)) fail(`stage ${S.art}: stage-${S.art}.json missing`); keys.add(S.art); }
  if (/fx\s*===\s*'bob'/.test(src)) fail('stage code bobs whole layers (band bob); figures must be individual cutouts');
  for (const k of keys) { const jp = `${PX}/stage-${k}.json`; if (!existsSync(jp)) continue; const M = JSON.parse(readFileSync(jp, 'utf8'));
    (M.layers || []).forEach((l) => l[2] === 'bob' && fail(`stage ${k}: layer ${l[0]} bobs as a band; cut its figures out individually`));
    if (!M.plate) fail(`stage ${k}: not built on an inpainted clean plate (plate:true missing)`);
    if (!Array.isArray(M.figures)) { fail(`stage ${k}: no figures list (declare figures:[] only if the stage has no animated figures)`); continue; }
    if (M.figures.length && !(M.layers || []).some((l) => l[0] === M.figure_layer)) fail(`stage ${k}: figure_layer ${M.figure_layer} is not a layer`);
    const py = spawnSync('python3', ['-c', `
import json,sys,numpy as np
from PIL import Image
k,px=sys.argv[1],sys.argv[2]; M=json.load(open(f'{px}/stage-{k}.json')); out=[]
plate=np.asarray(Image.open(f"{px}/stage-{k}-{M['layers'][0][0]}.png").convert('RGB')).astype(int)
masks=[]
for i,(x,y,w,h,p) in enumerate(M['figures']):
    try: f=np.asarray(Image.open(f'{px}/stage-{k}-fig{i}.png').convert('RGBA')).astype(int)
    except Exception: out.append(f'fig{i}: png missing'); continue
    a=f[...,3]>0
    if f.shape[:2]!=(h,w): out.append(f'fig{i}: size {f.shape[1]}x{f.shape[0]} != rect {w}x{h}')
    if a.mean()>0.92: out.append(f'fig{i}: cutout is a filled rectangle, not a figure mask')
    d=np.abs(plate[y:y+h,x:x+w][a]-f[...,:3][a]).mean()
    if d<10: out.append(f'fig{i}: plate under the figure still shows it (diff {d:.1f}); inpaint the clean plate')
    m=np.zeros(plate.shape[:2],bool); m[y:y+h,x:x+w]=a; masks.append((i,m))
for (i,a) in masks:
    for (j,b) in masks:
        if j>i and (a&b).sum()>0.2*min(a.sum(),b.sum()): out.append(f'fig{i}/fig{j}: masks overlap >20% (not individual figures)')
print(json.dumps(out))`, k, PX], { encoding: 'utf8' });
    if (py.status !== 0) fail(`stage ${k}: figure check crashed: ${py.stderr.slice(-200)}`); else JSON.parse(py.stdout).forEach((m) => fail(`stage ${k}: ${m}`));
    notes.push(`stage ${k}: ${M.figures.length} figure cutouts over a clean plate`); } }
// ---- VS portraits + super cut-ins
if (/VS PORTRAIT|CUT-IN .* EYES/.test(src)) fail('VS / cut-in placeholders still drawn (ph slots)');
{ const vs = E.scenes.filter((s) => s.name === 'vs'), need = new Set(vs.flatMap((s) => [...s.p1, s.p2]));
  const py = spawnSync('python3', ['-c', `
import json,sys,os,numpy as np
from PIL import Image
px=sys.argv[1]; out=[]
for c in sys.argv[2].split(','):
    f=f'{px}/portrait-{c}.png'
    if not os.path.exists(f): out.append(f'portrait {c}: missing'); continue
    a=np.asarray(Image.open(f).convert('RGBA')).astype(int); o=a[...,3]>0
    if o.mean()<0.15: out.append(f'portrait {c}: slot nearly empty ({o.mean():.0%} opaque)')
    gr=o&(a[...,1]>np.maximum(a[...,0],a[...,2])+30)
    if gr.sum()>0.001*o.sum(): out.append(f'portrait {c}: green fringe {gr.sum()} px')
print(json.dumps(out))`, `${SD}/assets/px`, [...need].join(',')], { encoding: 'utf8' });
  if (py.status !== 0) fail(`portrait check crashed: ${py.stderr.slice(-200)}`); else JSON.parse(py.stdout).forEach(fail);
  if (!(F.CUTIN >= 0.6 && F.CUTIN <= 0.8)) fail(`cut-in length ${F.CUTIN}s outside 0.6-0.8s`);
  const want = { f1: 'uno', f2: 'aura', boss: 'shogun' };
  for (const [id, who] of Object.entries(want)) { const f = E.fights[id];
    if (!f || !f.super) { fail(`${id}: no super cut-in cue`); continue; }
    if (f.super[1] !== who) fail(`${id}: cut-in is ${f.super[1]}, want ${who}`);
    if (!existsSync(`${SD}/assets/px/cutin-${who}.png`)) fail(`${id}: cutin-${who}.png missing`);
    const c = E.fx(f, f.super[0] + 0.02).cutin; if (!c || c.who !== who) fail(`${id}: cut-in not showing at its cue ${f.super[0].toFixed(2)}s`);
    if (E.fx(f, f.super[0] + F.CUTIN + 0.02).cutin) fail(`${id}: cut-in overstays`);
    const side = F.CHARS[who] && (f.p2 === who ? 2 : 1), sp = f.events.find((e) => e.side === side && e.move === 'special' && e.t > f.super[0]);
    if (!sp) fail(`${id}: no ${who} special after the cut-in`);
    else { const start = sp.t - 0.16; // fighterAt starts an attack anim 0.16 s before its impact
      if (start < f.super[0] + F.CUTIN - 0.05) fail(`${id}: ${who}'s special starts during the cut-in`); if (sp.t - f.super[0] > 1.6) fail(`${id}: cut-in ${(sp.t - f.super[0]).toFixed(2)}s before the special (too early)`);
      notes.push(`${id}: ${who} cut-in ${f.super[0].toFixed(2)}-${(f.super[0] + F.CUTIN).toFixed(2)}s, world held from ${(f.super[0] - F.HOLD).toFixed(2)}s, special lands ${sp.t}s`); } } }
// ---- no grey placeholders anywhere in the timeline
{ const calls = (src.match(/\bph\(\s*g\b/g) || []).length; if (calls) fail(`${calls} grey placeholder box call(s) ph(g, ...) still in the stage`);
  for (const [k, S] of Object.entries(F.STAGES)) if (!S.art) fail(`stage ${k}: no art (would draw the PLACEHOLDER STAGE fallback)`);
  const px = (n) => existsSync(`${SD}/assets/px/${n}`);
  for (const s of E.scenes) {
    if (s.name === 'cut' && !px(`panel-${s.panel}.png`)) fail(`cut @${s.t0.toFixed(1)}s: panel-${s.panel}.png missing`);
    if (s.name === 'map' && !px('world-map.png')) fail('map: world-map.png missing');
    if (s.name === 'title' && !px('logo.png')) fail('title: logo.png missing');
    if (s.name === 'ending') for (const n of ['belt', 'sensei', 'bow']) if (!px(`panel-${n}.png`)) fail(`ending: panel-${n}.png missing`);
    if (s.name === 'fight' && !F.STAGES[E.fights[s.fight].stage].art) fail(`fight ${s.fight}: placeholder stage`); }
  for (const c of F.ROSTER) if (!F.SPRITE_ANIMS[c]) fail(`${c}: still a rect placeholder fighter`);
  if (existsSync(`${SD}/assets/px/story.json`)) { const st = JSON.parse(readFileSync(`${SD}/assets/px/story.json`, 'utf8')); if (st.logo_green_px) fail(`logo: ${st.logo_green_px} green fringe px`); if ((st.pins || []).length !== 5) fail(`world map: ${st.pins.length} pins measured, want 5`); } }
const dt = 1 / 30;
for (const f of Object.values(E.fights)) {
  const used = new Set(), gfail = new Set(); let lastKey = {}, still = {};
  for (let t = f.t0; t < f.end - 1e-6; t += dt) {
    for (const side of [1, 2]) {
      const st = E.fighterAt(f, side, t); used.add(`${st.char}.${st.anim}`);
      if (!F.movesOf(st.char).includes(st.anim)) fail(`${f.id} t=${t.toFixed(2)}: ${st.char} uses ${st.anim} (not in its move set)`);
      let low;
      if (SPR[st.char]) { const pose = F.animOf(st.char, st.anim).frames[st.frame], fr = SPR[st.char].frames[pose]; low = st.y + (fr.rect[3] - 1 - (SPR[st.char].cell_pad || 0) - fr.ay); if (fr.air && !st.air) fail(`${f.id}: ${st.char} air pose ${pose} drawn grounded`); }
      else { const rs = F.poseRects(st.char, st.anim, st.frame); low = st.y + Math.max(...rs.map((r) => r[1] + r[3] - 1)); }
      if (!st.air && Math.abs(low - f.ground) > 1 && !gfail.has(st.char + st.anim)) { gfail.add(st.char + st.anim); fail(`${f.id} t=${t.toFixed(2)}: ${st.char} ${st.anim}[${st.frame}] lowest pixel y=${low}, ground ${f.ground} (floating ${f.ground - low}px)`); }
      if (SPR[st.char]) { const pose = F.animOf(st.char, st.anim).frames[st.frame], fr = SPR[st.char].frames[pose], Z = 2;
        const boxes = [[0, fr.rect[2], 0, fr.rect[3]]].concat(fr.fx ? [[fr.fx.ox, fr.fx.ox + fr.fx.rect[2], fr.fx.oy, fr.fx.oy + fr.fx.rect[3]]] : []);
        for (const [x0, x1, y0, y1] of boxes) { const ax = st.flip ? fr.rect[2] - 1 - fr.ax : fr.ax, dx = Math.round(st.x * Z) - ax, dy = Math.round(st.y * Z) - fr.ay;
          const L = st.flip ? dx + fr.rect[2] - x1 : dx + x0, Rr = st.flip ? dx + fr.rect[2] - x0 : dx + x1;
          if ((L < 0 || Rr > 960 || dy + y0 < 0) && !gfail.has('clip' + st.char + pose)) { gfail.add('clip' + st.char + pose); fail(`${f.id} t=${t.toFixed(2)}: ${st.char} ${pose} drawn outside the screen (x ${L}..${Rr}, top ${dy + y0}) - limb clipped`); } } }
      const SA = F.SPRITE_ANIMS && F.SPRITE_ANIMS[st.char] && F.SPRITE_ANIMS[st.char][st.anim];
      if (st.air && st.anim !== 'ko_fall' && !(SA && SA.lift && SA.lift[st.frame])) fail(`${f.id}: ${st.char} airborne outside ko_fall`);
      const key = st.anim + st.frame + ':' + st.x; const id = side; if (st.anim === 'idle') { still[id] = key === lastKey[id] ? (still[id] || 0) + dt : 0; if (still[id] > 0.6) { fail(`${f.id} t=${t.toFixed(2)}: ${st.char} idle frozen >0.6s`); still[id] = -99; } } lastKey[id] = key;
    }
  }
  // 4. opponent fights back in every exchange, lands at least one hit per fight
  f.ex.forEach((ex, i) => { if (!ex.some((e) => e.side === 2)) fail(`${f.id} exchange ${i + 1}: opponent never attacks`); if (!ex.some((e) => e.side === 1)) fail(`${f.id} exchange ${i + 1}: hero never attacks`); });
  if (!f.montage && !f.events.some((e) => e.side === 2 && e.res !== 'block')) fail(`${f.id}: opponent never lands a hit`);
  // 5. restraint: <= 3 connecting hits per bar
  const DB = TL.downbeats; for (let b = 0; b < DB.length; b++) { const n = f.events.filter((e) => e.res !== 'block' && e.t >= DB[b] && e.t < (DB[b + 1] ?? 1e9)).length; if (n > 3) fail(`${f.id}: ${n} hits in bar ${b} (max 3)`); }
  notes.push(`${f.id} ${f.p1} vs ${f.p2} @${f.t0.toFixed(1)}s: ${f.ex.length} exchanges, ${f.events.filter((e) => e.side === 2).length} CPU attacks, anims ${[...used].length}`);
}
// 6. scenes contiguous, start on downbeats
E.scenes.forEach((s, i) => { if (i && Math.abs(s.t0 - E.scenes[i - 1].t1) > 1e-6) fail(`scene ${i} gap`); if (s.t0 && !TL.downbeats.some((d) => Math.abs(d - s.t0) < 1e-3)) fail(`scene ${s.name}@${s.t0} not on a downbeat`); });
writeFileSync(`${OUT}/fighter-qa.json`, JSON.stringify({ fails, notes }, null, 1));
notes.forEach((n) => console.log('  ' + n)); fails.forEach((f) => console.log('  FAIL ' + f));
console.log(`fighter QA: ${fails.length} failure(s)`); process.exit(fails.length ? 1 : 0);

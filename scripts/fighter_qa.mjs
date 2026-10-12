#!/usr/bin/env node
// Fighter QA for pixel fighting-game shots (any shot with stage/fight.js).  node scripts/fighter_qa.mjs <shot>
// Fails (exit 1) on: HUD / banner text not in the bitmap pixel font, fighters not on the stage ground,
// an exchange where the opponent never swings back, identical consecutive frames in an animation,
// a master core that changes between frames, too many hits per bar, montage-only fighters using moves they don't have.
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
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
      if (fr.ay !== fr.rect[3] - 1) fail(`${c}.${p}: anchor row ${fr.ay} is not the lowest pixel row ${fr.rect[3] - 1}`);
      const j = i + 1 < A.frames.length ? i + 1 : (A.loop ? 0 : -1); if (j >= 0 && j !== i && A.frames[j] === p) fail(`${c}.${a}: frames ${i} and ${j} identical (${p})`); });
  }
  const rp = `out/${shot}/${c}-report.json`; if (existsSync(rp)) { const r = JSON.parse(readFileSync(rp, 'utf8'));
    for (const [k, v] of Object.entries(r.master || {})) if (k.endsWith('_identity') && v < 0.97) fail(`${c}: master upper body identity ${k} ${v} < 0.97`);
    for (const [k, v] of Object.entries(r.walk_change || {})) if (v < 0.03) fail(`${c}: walk ${k} silhouette change ${v} < 3%`);
    (r.flags || []).forEach((f) => notes.push(`${c} ART FLAG: ${f}`)); }
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
const dt = 1 / 30;
for (const f of Object.values(E.fights)) {
  const used = new Set(), gfail = new Set(); let lastKey = {}, still = {};
  for (let t = f.t0; t < f.end - 1e-6; t += dt) {
    for (const side of [1, 2]) {
      const st = E.fighterAt(f, side, t); used.add(`${st.char}.${st.anim}`);
      if (!F.movesOf(st.char).includes(st.anim)) fail(`${f.id} t=${t.toFixed(2)}: ${st.char} uses ${st.anim} (not in its move set)`);
      let low;
      if (SPR[st.char]) { const pose = F.animOf(st.char, st.anim).frames[st.frame], fr = SPR[st.char].frames[pose]; low = st.y + (fr.rect[3] - 1 - fr.ay); if (fr.air && !st.air) fail(`${f.id}: ${st.char} air pose ${pose} drawn grounded`); }
      else { const rs = F.poseRects(st.char, st.anim, st.frame); low = st.y + Math.max(...rs.map((r) => r[1] + r[3] - 1)); }
      if (!st.air && Math.abs(low - f.ground) > 1 && !gfail.has(st.char + st.anim)) { gfail.add(st.char + st.anim); fail(`${f.id} t=${t.toFixed(2)}: ${st.char} ${st.anim}[${st.frame}] lowest pixel y=${low}, ground ${f.ground} (floating ${f.ground - low}px)`); }
      if (st.air && st.anim !== 'ko_fall') fail(`${f.id}: ${st.char} airborne outside ko_fall`);
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

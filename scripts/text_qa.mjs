// node scripts/text_qa.mjs <shot> [--step 0.25]  -> JSON list of text problems (clipped at the frame edge, overlapping text)
// Samples the whole timeline in the landscape and vertical layouts. The page records every bitmap-font text box in
// window.__qa.texts as [canvas, x, y, w, h, string, group] in logic px (world = 480x270, 'out' = the output canvas).
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { resolveAsset } from '../lib/serve.mjs';
const args = process.argv.slice(2), name = args[0]; const si = args.indexOf('--step'), step = si >= 0 ? +args[si + 1] : 0.25;
const mj = JSON.parse(readFileSync(`shots/${name}/${name}.music.json`, 'utf8')), px = mj.pixel || { w: 480, h: 270 }, dur = mj.duration;
const probs = []; const seen = new Set(); const add = (k, m) => { if (!seen.has(k)) { seen.add(k); probs.push(m); } };
const b = await chromium.launch();
for (const fmt of ['landscape', 'vertical']) {
  const V = fmt === 'vertical', p = await b.newPage({ viewport: V ? { width: px.h, height: px.w } : { width: px.w, height: px.h } });
  await p.addInitScript(() => { window.__qa = { log: true, draws: [], texts: [] }; });
  await p.route('http://webshot.local/**', (r) => { const a = resolveAsset(name, new URL(r.request().url()).pathname); return a ? r.fulfill({ body: readFileSync(a.file), contentType: a.type }) : r.fulfill({ status: 404 }); });
  await p.goto(`http://webshot.local/${V ? '?format=vertical' : ''}`); await p.waitForFunction(() => document.body.dataset.ready === '1');
  const t0 = V ? mj.shorts.start : 0, t1 = V ? mj.shorts.end : dur;
  for (let t = t0; t < t1; t += step) {
    const r = await p.evaluate(async (t) => { Music.freeze(t); await new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))); return { texts: window.__qa.texts, fit: window.__qa.vsFit, scene: window.__qa.scene }; }, t);
    // map every box into output-frame logic px; the visible frame is 480x270 (landscape) or 270x480 (vertical)
    const FW = V ? 270 : 480, FH = V ? 480 : 270, boxes = [];
    for (const [cv, x, y, w, h, s, gr] of r.texts) {
      let X = x, Y = y, k = 1;
      if (V && cv === 'world') { if (r.fit) { k = 0.5625; X = x * k; Y = y * k + 159; } else { X = x - 105; Y = y + 100; } }
      const bx = [X, Y, w * k, h * k, s, gr, cv]; boxes.push(bx);
      const inX = X >= 0 && X + w * k <= FW, inY = Y >= 0 && Y + h * k <= FH, any = X + w * k > 0 && X < FW && Y + h * k > 0 && Y < FH;
      const vis = V && cv === 'world' && !r.fit ? Y >= 100 && Y + h * k <= 370 : true; // world crop band in the Short
      if (any && (!inX || !inY || !vis)) add(`${fmt}clip${s}`, `${fmt} t=${t.toFixed(2)} (${r.scene}): text "${s}" clipped at the frame edge (x ${X.toFixed(0)}..${(X + w * k).toFixed(0)} of ${FW}, y ${Y.toFixed(0)})`);
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const A = boxes[i], B = boxes[j]; if (A[5] && A[5] === B[5] && A[5] !== 'logo') continue; if (A[4] === B[4] && A[0] === B[0]) continue;
      const ox = Math.min(A[0] + A[2], B[0] + B[2]) - Math.max(A[0], B[0]), oy = Math.min(A[1] + A[3], B[1] + B[3]) - Math.max(A[1], B[1]);
      if (ox > 1 && oy > 1) add(`${fmt}ov${A[4]}|${B[4]}`, `${fmt} t=${t.toFixed(2)} (${r.scene}): text "${A[4]}" overlaps "${B[4]}" (${ox.toFixed(0)}x${oy.toFixed(0)} px)`);
    }
  }
  await p.close();
}
await b.close();
console.log(JSON.stringify(probs));

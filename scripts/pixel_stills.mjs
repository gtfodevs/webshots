// node scripts/pixel_stills.mjs <shot> <outdir> [--dpr N] label=seconds ...  -> exact canvas-sized PNG stills of a pixel shot
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { resolveAsset } from '../lib/serve.mjs';
const args = process.argv.slice(2); const name = args.shift(), outdir = args.shift();
let dpr = 4; const di = args.indexOf('--dpr'); if (di >= 0) { dpr = +args[di + 1]; args.splice(di, 2); }
const mj = JSON.parse(readFileSync(`shots/${name}/${name}.music.json`, 'utf8')); const px = mj.pixel || { w: 480, h: 270 };
mkdirSync(outdir, { recursive: true });
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: px.w, height: px.h }, deviceScaleFactor: dpr });
await p.addInitScript(() => { window.__qa = { log: true, draws: [] }; });
await p.route('http://webshot.local/**', (r) => { const a = resolveAsset(name, new URL(r.request().url()).pathname); return a ? r.fulfill({ body: readFileSync(a.file), contentType: a.type }) : r.fulfill({ status: 404 }); });
await p.goto('http://webshot.local/'); await p.waitForFunction(() => document.body.dataset.ready === '1');
const qa = {};
for (const pr of args) { const [label, t] = pr.split('='); await p.evaluate((t) => { window.__qa.draws = []; Music.freeze(+t); }, t); await p.waitForTimeout(150);
  await p.screenshot({ path: `${outdir}/${label}.png` });
  qa[label] = await p.evaluate(() => ({ t: Music.time(), scene: window.__qa.scene, draws: window.__qa.draws.slice(-400), text: document.body.innerText.trim().slice(0, 200) })); }
writeFileSync(`${outdir}/qa.json`, JSON.stringify(qa));
await b.close();

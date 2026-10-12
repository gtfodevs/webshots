import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { resolveAsset } from '../../../lib/serve.mjs';
const name = 'kingdom-come-16bit', [,, outdir, ...pairs] = process.argv;
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 480, height: 270 }, deviceScaleFactor: 4 });
await p.route('http://webshot.local/**', (r) => { const a = resolveAsset(name, new URL(r.request().url()).pathname); return a ? r.fulfill({ body: readFileSync(a.file), contentType: a.type }) : r.fulfill({ status: 404 }); });
await p.goto('http://webshot.local/'); await p.waitForFunction(() => document.body.dataset.ready === '1');
for (const pr of pairs) { const [label, t] = pr.split('='); await p.evaluate((t) => Music.freeze(+t), t); await p.waitForTimeout(120); await p.screenshot({ path: `${outdir}/${label}.png` }); }
await b.close();

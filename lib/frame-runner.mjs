// Frame-exact recorder for music shots (default for `npm run render` in music mode).
//
// Wall-clock capture drops frames whenever the page is heavy (rigged WebGL actors, many layers):
// the video then shows the same frame several times ("jerky"). This recorder virtualizes time
// instead: performance.now, Date.now, requestAnimationFrame, setTimeout/setInterval and CSS/Web
// animations all run on a virtual clock that advances exactly 1/fps per captured frame. GSAP, the
// music clock, actor loops and particles therefore render every frame, however long a frame takes.
//
//   node lib/frame-runner.mjs <shot> <out.mp4> --start s --end s --format landscape|vertical [--fps 30]

import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { resolveAsset, shotDir } from './serve.mjs';

const VCLOCK = () => {
  const realPerf = performance.now.bind(performance), realDate = Date.now, realRaf = window.requestAnimationFrame.bind(window), realCaf = window.cancelAnimationFrame.bind(window);
  const realST = window.setTimeout.bind(window), realCT = window.clearTimeout.bind(window), realSI = window.setInterval.bind(window), realCI = window.clearInterval.bind(window);
  const V = (window.__vclock = { on: false, t: 0, epoch: 0, raf: new Map(), timers: new Map(), id: 1e6 });
  performance.now = () => (V.on ? V.t : realPerf());
  Date.now = () => (V.on ? V.epoch + V.t : realDate());
  window.requestAnimationFrame = (cb) => { if (!V.on) return realRaf(cb); const id = ++V.id; V.raf.set(id, cb); return id; };
  window.cancelAnimationFrame = (id) => { V.raf.delete(id); realCaf(id); };
  const addT = (fn, ms, rep, args) => { const id = ++V.id; V.timers.set(id, { fn, due: V.t + Math.max(0, +ms || 0), ms: Math.max(1, +ms || 0), rep, args }); return id; };
  window.setTimeout = (fn, ms, ...a) => (V.on ? addT(fn, ms, false, a) : realST(fn, ms, ...a));
  window.setInterval = (fn, ms, ...a) => (V.on ? addT(fn, ms, true, a) : realSI(fn, ms, ...a));
  window.clearTimeout = (id) => { V.timers.delete(id); realCT(id); };
  window.clearInterval = (id) => { V.timers.delete(id); realCI(id); };
  V.enable = () => { V.t = realPerf(); V.epoch = realDate() - V.t; V.on = true; };
  V.advance = (ms) => {
    const target = V.t + ms;
    for (;;) { // fire due timers in order
      let next = null; for (const [id, x] of V.timers) if (x.due <= target && (!next || x.due < next[1].due)) next = [id, x];
      if (!next) break; const [id, x] = next; V.t = Math.max(V.t, x.due);
      if (x.rep) x.due += x.ms; else V.timers.delete(id);
      try { typeof x.fn === 'function' ? x.fn(...x.args) : 0; } catch (e) { console.error(e); }
    }
    V.t = target;
    const cbs = [...V.raf.values()]; V.raf.clear(); cbs.forEach((cb) => { try { cb(V.t); } catch (e) { console.error(e); } });
    // CSS transitions/animations and WAAPI: pin them to the virtual clock
    document.getAnimations().forEach((a) => { if (a.__v0 == null) { a.__v0 = V.t; a.pause(); } a.currentTime = V.t - a.__v0; });
  };
};

export async function renderFrames({ name, out, start, end, format = 'landscape', fps = 30, pixel = null }) {
  const dir = shotDir(name);
  const scenes = JSON.parse(readFileSync(join(dir, `${name}.scenes.json`), 'utf8'));
  let bars = []; try { bars = JSON.parse(readFileSync(join(dir, 'stage', 'timeline.json'), 'utf8')).downbeats || []; } catch {}
  const plan = scenes.map((s) => ({ scene: s.scene, at: s.at ?? (s.bar != null ? bars[s.bar] ?? 0 : 0) }));
  const vertical = format === 'vertical';
  // Pixel-game stages (music.json "pixel": {"w":480,"h":270}): the viewport IS the low-res game screen and
  // the device scale is the integer upscale to 1920x1080 / 1080x1920, so every art pixel is an exact NxN block.
  let [w, h, dpr] = vertical ? [720, 1280, 1.5] : [1280, 720, 2];
  if (pixel) { [w, h] = vertical ? [pixel.h, pixel.w] : [pixel.w, pixel.h]; dpr = (vertical ? 1080 : 1920) / w; }
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dpr });
  page.on('pageerror', (e) => console.error('page error:', e.message));
  await page.addInitScript(VCLOCK);
  await page.route('http://webshot.local/**', (route) => {
    const asset = resolveAsset(name, new URL(route.request().url()).pathname);
    return asset ? route.fulfill({ body: readFileSync(asset.file), contentType: asset.type }) : route.fulfill({ status: 404, body: 'not found' });
  });
  await page.goto(`http://webshot.local/?format=${format}`);
  await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60_000 });
  await page.waitForTimeout(500);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', pixel ? 'png' : 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  await page.evaluate((s) => { window.__vclock.enable(); window.Music && window.Music.start(s); }, start);
  const first = [...plan].reverse().find((p) => p.at <= start) || plan[0];
  await page.evaluate((n) => { window.scene(n); }, first.scene);
  const N = Math.round((end - start) * fps); let k = plan.indexOf(first) + 1; const t0 = Date.now();
  for (let i = 0; i < N; i++) {
    const t = start + i / fps;
    while (k < plan.length && plan[k].at <= t) { if (plan[k].at < end) await page.evaluate((n) => { window.scene(n); }, plan[k].scene); k++; }
    await page.evaluate((ms) => window.__vclock.advance(ms), i === 0 ? 0 : 1000 / fps);
    const buf = await page.screenshot(pixel ? { type: 'png' } : { type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % (fps * 5) === 0) process.stdout.write(`\r  frame ${i}/${N}  t=${t.toFixed(1)}s  ${((Date.now() - t0) / 1000 / Math.max(1, i)).toFixed(2)} s/frame   `);
  }
  ff.stdin.end(); await new Promise((r) => ff.on('close', r));
  await browser.close();
  console.log(`\n  ${N} frames -> ${out}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const a = process.argv.slice(2); const f = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
  await renderFrames({ name: a[0], out: a[1], start: +f('--start', 0), end: +f('--end', 10), format: f('--format', 'landscape'), fps: +f('--fps', 30) });
}

#!/usr/bin/env node
// webshots CLI. Usually run through npm:
//   npm run new -- <name> [--title "Video title"]   scaffold shots/<name> from the template
//   npm run preview -- <name>                       serve the stage at http://127.0.0.1:8231
//   npm run check -- <name>                         play every scene, screenshot it, find errors
//   npm run render -- <name>                        narrate + record + export -> out/<name>.mp4
//   npm run list                                    list shots
//   npm run doctor                                  check that everything needed is installed

import { spawn } from 'node:child_process';
import { copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { ROOT, resolveAsset, shotDir } from '../lib/serve.mjs';

const [cmd, name, ...rest] = process.argv.slice(2);
const flag = (f, dflt) => { const i = rest.indexOf(f); return i >= 0 ? rest[i + 1] : dflt; };
const OUT = join(ROOT, 'out');

function die(msg) { console.error(`webshots: ${msg}`); process.exit(1); }
function needShot() {
  if (!name) die(`usage: npm run ${cmd} -- <name>`);
  if (!existsSync(shotDir(name))) die(`no shot "${name}" (try: npm run list)`);
}
function manifest() {
  return JSON.parse(readFileSync(join(shotDir(name), `${name}.scenes.json`), 'utf8'));
}
function run(bin, args, env = {}) {
  return new Promise((resolve) => {
    const p = spawn(bin, args, { cwd: ROOT, stdio: 'inherit', env: { ...process.env, ...env } });
    p.on('exit', (code) => resolve(code ?? 1));
  });
}
function serve(port) {
  const server = createServer((req, res) => {
    const asset = resolveAsset(name, new URL(req.url, 'http://x').pathname);
    if (!asset) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'content-type': asset.type, 'cache-control': 'no-store' });
    res.end(readFileSync(asset.file));
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}

async function cmdNew() {
  if (!name || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) die('usage: npm run new -- <kebab-case-name> [--title "Title"]');
  const dir = shotDir(name);
  if (existsSync(dir)) die(`shots/${name} already exists`);
  cpSync(join(ROOT, 'template'), dir, { recursive: true });
  renameSync(join(dir, 'NAME.scenes.json'), join(dir, `${name}.scenes.json`));
  renameSync(join(dir, 'NAME.demo.ts'), join(dir, `${name}.demo.ts`));
  const title = flag('--title', name.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()));
  const html = join(dir, 'stage', 'index.html');
  writeFileSync(html, readFileSync(html, 'utf8').replaceAll('{{TITLE}}', title));
  console.log(`Created shots/${name}/ (stage/index.html, ${name}.scenes.json, ${name}.demo.ts)`);
}

async function cmdPreview() {
  needShot();
  const port = Number(flag('--port', 8231));
  await serve(port);
  console.log(`Previewing ${name} at http://127.0.0.1:${port}/  (Ctrl+C to stop)`);
  console.log(`In the browser console: scene('${manifest()[0].scene}')`);
}

async function cmdCheck() {
  needShot();
  const { chromium } = await import('playwright');
  const server = await serve(0);
  const port = server.address().port;
  const dir = join(OUT, name, 'check');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const problems = [];
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
  page.on('console', (m) => m.type() === 'error' && problems.push(`console error: ${m.text()}`));
  page.on('requestfailed', (r) => problems.push(`failed to load: ${r.url()}`));
  page.on('response', (r) => r.status() >= 400 && problems.push(`HTTP ${r.status()}: ${r.url()}`));
  try {
    await page.goto(`http://127.0.0.1:${port}/`);
    await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30_000 });
  } catch {
    problems.push('stage never became ready (call Webshot.start() at the end of the page script)');
  }
  const wanted = manifest().map((s) => s.scene);
  const defined = await page.evaluate(() => window.sceneNames || []).catch(() => []);
  for (const s of wanted) if (!defined.includes(s)) problems.push(`scene "${s}" is in ${name}.scenes.json but not defined on the stage`);
  for (const s of defined) if (!wanted.includes(s)) problems.push(`scene "${s}" is defined on the stage but has no narration in ${name}.scenes.json`);
  let i = 0;
  for (const s of wanted.filter((x) => defined.includes(x))) {
    const t0 = Date.now();
    try {
      await page.evaluate((n) => window.scene(n), s);
    } catch (e) {
      problems.push(`scene "${s}" failed: ${e.message}`);
    }
    const secs = (Date.now() - t0) / 1000;
    await page.waitForTimeout(250);
    await page.screenshot({ path: join(dir, `${String(++i).padStart(2, '0')}-${s}.png`) });
    console.log(`  ${s.padEnd(18)} entrance ${secs.toFixed(1)}s`);
  }
  await browser.close();
  server.close();
  const cols = 2, rows = Math.ceil(i / cols);
  if (i) {
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i', join(dir, '*.png'),
      '-vf', `scale=640:-1,tile=${cols}x${rows}`, '-frames:v', '1', join(dir, 'sheet.png')]);
  }
  console.log(`\nScreenshots: out/${name}/check/  (contact sheet: out/${name}/check/sheet.png)`);
  if (problems.length) {
    console.log(`\n${problems.length} problem(s):`);
    [...new Set(problems)].forEach((p) => console.log(`  - ${p}`));
    process.exit(1);
  }
  console.log('No problems found.');
}

async function cmdRender() {
  needShot();
  const argo = join(ROOT, 'node_modules', '@argo-video', 'cli', 'bin', 'argo.js');
  if (!existsSync(argo)) die('dependencies missing: run npm run setup');
  const code = await run(process.execPath, [argo, 'pipeline', name, '-c', 'webshots.config.mjs'], { WEBSHOT: name });
  if (code !== 0) die(`render failed (exit ${code}); see the log above`);
  const raw = join(OUT, '.argo', `${name}.mp4`);
  const final = join(OUT, `${name}.mp4`);
  // Standard stereo 48 kHz audio and no data track, so every player and chat app plays it.
  const c2 = await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-map', '0:v:0', '-map', '0:a:0', '-dn',
    '-map_chapters', '-1', '-c:v', 'copy', '-af', 'aresample=48000', '-ac', '2', '-c:a', 'aac', '-b:a', '192k',
    '-movflags', '+faststart', final]);
  if (c2 !== 0) die('ffmpeg could not finalize the video');
  for (const ext of ['srt', 'vtt']) {
    const f = join(OUT, '.argo', `${name}.${ext}`);
    if (existsSync(f)) copyFileSync(f, join(OUT, `${name}.${ext}`));
  }
  console.log(`\nDone: out/${name}.mp4  (subtitles: out/${name}.srt)`);
}

function cmdList() {
  const dir = join(ROOT, 'shots');
  const shots = existsSync(dir) ? readdirSync(dir).filter((d) => existsSync(join(dir, d, `${d}.scenes.json`))) : [];
  shots.forEach((s) => console.log(`${s}${existsSync(join(OUT, `${s}.mp4`)) ? '  -> out/' + s + '.mp4' : ''}`));
  if (!shots.length) console.log('No shots yet. Try: npm run new -- my-first-video');
}

async function cmdDoctor() {
  const results = [];
  const ok = (label, pass, fix) => results.push({ label, pass, fix });
  const major = Number(process.versions.node.split('.')[0]);
  ok(`Node ${process.versions.node}`, major >= 20, 'install Node 20 or newer');
  const has = (bin) => new Promise((r) => { const p = spawn(bin, ['-version'], { stdio: 'ignore' }); p.on('error', () => r(false)); p.on('exit', (c) => r(c === 0)); });
  ok('ffmpeg', await has('ffmpeg'), 'install ffmpeg (macOS: brew install ffmpeg)');
  ok('ffprobe', await has('ffprobe'), 'comes with ffmpeg');
  for (const [pkg, fix] of [['@argo-video/cli', 'npm install'], ['kokoro-js', 'npm install'], ['gsap', 'npm install']]) {
    let found = true;
    try { await import(pkg === 'gsap' ? 'gsap' : pkg); } catch { found = false; }
    ok(pkg, found, fix);
  }
  try {
    const { chromium } = await import('playwright');
    const b = await chromium.launch(); await b.close();
    ok('Chromium (Playwright)', true);
  } catch {
    ok('Chromium (Playwright)', false, 'npx playwright install chromium');
  }
  const tts = process.env.WEBSHOTS_TTS;
  if (tts) {
    const pkg = { openai: 'openai', elevenlabs: '@elevenlabs/elevenlabs-js' }[tts];
    let found = !!pkg;
    try { if (pkg) await import(pkg); } catch { found = false; }
    ok(`cloud voice "${tts}"`, found, pkg ? `npm i ${pkg}` : 'WEBSHOTS_TTS must be openai or elevenlabs');
  }
  for (const r of results) console.log(`  ${r.pass ? '✓' : '✗'} ${r.label}${r.pass ? '' : `  -> ${r.fix}`}`);
  const bad = results.filter((r) => !r.pass).length;
  console.log(bad ? `\n${bad} thing(s) to fix.` : '\nReady to make videos.');
  if (bad) process.exit(1);
}

const commands = { doctor: cmdDoctor, new: cmdNew, preview: cmdPreview, check: cmdCheck, render: cmdRender, list: cmdList };
if (!commands[cmd]) die(`unknown command "${cmd ?? ''}". Commands: ${Object.keys(commands).join(', ')}`);
await commands[cmd]();

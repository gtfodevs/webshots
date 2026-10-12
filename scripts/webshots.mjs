#!/usr/bin/env node
// webshots CLI. Usually run through npm:
//   npm run new -- <name> [--title "Video title"]   scaffold shots/<name> from the template
//   npm run new -- <name> --music song.mp3 [--lyrics lyrics.txt]   scaffold a music shot + timeline
//   npm run preview -- <name>                       serve the stage at http://127.0.0.1:8231
//   npm run check -- <name>                         play every scene, screenshot it, find errors
//   npm run render -- <name>                        narrate + record + export -> out/<name>.mp4
//        [--format vertical] [--start 40 --end 95]   music shots: Shorts 1080x1920 / a time cut
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

function isMusic(n = name) { return existsSync(join(shotDir(n), `${n}.music.json`)); }
function musicCfg() { return JSON.parse(readFileSync(join(shotDir(name), `${name}.music.json`), 'utf8')); }

async function cmdNewMusic(audio) {
  const dir = shotDir(name);
  if (existsSync(dir)) die(`shots/${name} already exists`);
  if (!existsSync(audio)) die(`no such audio file: ${audio}`);
  cpSync(join(ROOT, 'template-music'), dir, { recursive: true });
  renameSync(join(dir, 'NAME.demo.ts'), join(dir, `${name}.demo.ts`));
  mkdirSync(join(dir, 'stage', 'assets'), { recursive: true });
  const ext = audio.split('.').pop();
  copyFileSync(audio, join(dir, 'stage', 'assets', `song.${ext}`));
  const lyrics = flag('--lyrics');
  if (lyrics) copyFileSync(lyrics, join(dir, 'lyrics.txt'));
  console.log('Analyzing the song (beats, bars, sections, energy' + (lyrics ? ', lyrics' : '') + ')...');
  const args = [join(ROOT, 'scripts', 'analyze_music.py'), join(dir, 'stage', 'assets', `song.${ext}`), '-o', join(dir, 'stage', 'timeline.json')];
  if (lyrics) args.push('--lyrics', join(dir, 'lyrics.txt')); else if (rest.includes('--no-words')) args.push('--no-words');
  if ((await run('python3', args)) !== 0) die('music analysis failed (pip install librosa faster-whisper)');
  const tl = JSON.parse(readFileSync(join(dir, 'stage', 'timeline.json'), 'utf8'));
  const scenes = tl.sections.map((s, i) => ({ scene: `s${i + 1}-${(s.label || 'part').split(' ').pop().replace(/[^a-z0-9]/gi, '')}`.toLowerCase(), at: s.t, label: s.label }));
  writeFileSync(join(dir, `${name}.scenes.json`), JSON.stringify(scenes, null, 1));
  writeFileSync(join(dir, `${name}.music.json`), JSON.stringify({ soundtrack: `stage/assets/song.${ext}`, duration: tl.duration, start: 0, end: tl.duration, loudness: -14, fadeOut: 2, theme: 'fantasy', lyricStyle: 'karaoke' }, null, 1));
  // One placeholder scene per detected section so check/preview work immediately.
  const html = join(dir, 'stage', 'index.html');
  const title = flag('--title', name.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()));
  const sections = scenes.map((s) => `  <section class="scene" id="s-${s.scene}"><div class="layer" data-depth="0.3"><div class="ph">${s.scene} · ${s.at.toFixed(1)}s</div></div></section>`).join('\n');
  const defs = scenes.map((s) => `Webshot.scene('${s.scene}', (tl, el) => { tl.add(Music.fx.pop(el.querySelector('.ph'))); });`).join('\n');
  writeFileSync(html, readFileSync(html, 'utf8').replaceAll('{{TITLE}}', title).replace('<!--SCENES-->', sections).replace('//SCENES', defs));
  console.log(`Created music shot shots/${name}/: ${tl.tempo} BPM, ${tl.bars.length} bars, ${tl.sections.length} sections, ${(tl.lyrics || []).length} lyric lines.`);
  console.log(`Next: edit stage/index.html (see docs/MUSIC_MODE.md), npm run check -- ${name}, npm run render -- ${name}`);
}

async function cmdNew() {
  if (flag('--music')) return cmdNewMusic(flag('--music'));
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
  let downbeats = [];
  try { downbeats = JSON.parse(readFileSync(join(shotDir(name), 'stage', 'timeline.json'), 'utf8')).downbeats || []; } catch {}
  const at = Object.fromEntries(manifest().map((s) => [s.scene, s.at ?? (s.bar != null ? downbeats[s.bar] ?? 0 : 0)]));
  let i = 0;
  for (const s of wanted.filter((x) => defined.includes(x))) {
    const t0 = Date.now();
    try {
      await page.evaluate((n) => window.scene(n), s);
      // Music shots: freeze the song clock a few beats into the scene so lyrics show deterministically.
      if (isMusic()) await page.evaluate((t) => window.Music && window.Music.freeze(t), at[s] + 6);
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
  if (isMusic()) return cmdRenderMusic();
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

// Music mode: record the stage against the song clock (no narration), then mux the soundtrack
// (loudnorm to the target LUFS, fades, trimmed to the cut) onto the full-resolution capture.
async function cmdRenderMusic() {
  const cfg = musicCfg();
  const format = flag('--format', cfg.format || 'landscape');
  const start = Number(flag('--start', cfg.start ?? 0));
  const end = Number(flag('--end', cfg.end ?? cfg.duration));
  const suffix = flag('--out', format === 'vertical' ? `${name}-vertical` : name);
  let raw;
  if (!process.argv.includes('--realtime') && cfg.capture !== 'realtime') {
    // Frame-exact capture on a virtual clock (lib/frame-runner.mjs): every frame is rendered, never dropped.
    const { renderFrames } = await import('../lib/frame-runner.mjs');
    mkdirSync(join(OUT, '.frames'), { recursive: true });
    raw = join(OUT, '.frames', `${suffix}.mp4`);
    await renderFrames({ name, out: raw, start, end, format, fps: Number(flag('--fps', cfg.fps ?? 30)), pixel: cfg.pixel || null });
    if (!existsSync(raw)) die('frame capture failed; see the log above');
  } else {
    const argo = join(ROOT, 'node_modules', '@argo-video', 'cli', 'bin', 'argo.js');
    if (!existsSync(argo)) die('dependencies missing: run npm run setup');
    const env = { WEBSHOT: name, WEBSHOTS_FORMAT: format, WEBSHOTS_START: String(start), WEBSHOTS_END: String(end) };
    // Only the recording step: Argo's export would try to mix (non-existent) narration.
    const code = await run(process.execPath, [argo, 'record', name, '-c', 'webshots.config.mjs'], env);
    raw = join(ROOT, '.argo', name, 'video.mp4');
    if (code !== 0 || !existsSync(raw)) die(`recording failed (exit ${code}); see the log above`);
  }
  const [W, H] = format === 'vertical' ? [1080, 1920] : [1920, 1080];
  const len = end - start, fade = Number(cfg.fadeOut ?? 2), fin = Number(cfg.fadeIn ?? (start > 0 ? 0.5 : 0));
  const af = [`atrim=${start}:${end}`, 'asetpts=PTS-STARTPTS', `loudnorm=I=${cfg.loudness ?? -14}:TP=-1.0:LRA=11`, 'aresample=48000',
    fin ? `afade=t=in:d=${fin}` : null, fade ? `afade=t=out:st=${Math.max(0, len - fade)}:d=${fade}` : null].filter(Boolean).join(',');
  const final = join(OUT, `${suffix}.mp4`);
  const c2 = await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-i', join(shotDir(name), cfg.soundtrack),
    '-map', '0:v:0', '-map', '1:a:0', '-t', String(len), '-vf', `scale=${W}:${H}:flags=${cfg.pixel ? 'neighbor' : 'lanczos'},format=yuv420p${fade ? `,fade=t=out:st=${Math.max(0, len - fade)}:d=${fade}` : ''}`,
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-af', af, '-ac', '2', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', final]);
  if (c2 !== 0) die('ffmpeg could not mux the soundtrack');
  console.log(`\nDone: out/${suffix}.mp4  (${format} ${W}x${H}, ${len.toFixed(1)}s, soundtrack at ${cfg.loudness ?? -14} LUFS)`);
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

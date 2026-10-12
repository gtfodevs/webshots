// Recorder for music shots. A music shot's <name>.demo.ts is just:
//
//   import { musicShot } from '../../lib/music-runner.ts';
//   musicShot(import.meta.url);
//
// There is no narration. Scenes in <name>.scenes.json carry an absolute song time
// ({ "scene": "verse1", "at": 27.3 }) or a bar number ({ "scene": "verse1", "bar": 15 },
// resolved through stage/timeline.json). The page clock (Music.start) begins at song
// time 0 together with the recording, and every cut is scheduled against wall time so
// it never drifts. The soundtrack itself is muxed afterwards by `npm run render`.

import { readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from '@argo-video/cli';
import { resolveAsset } from './serve.mjs';

export const ORIGIN = 'http://webshot.local';

export function sceneTimes(dir: string, name: string): { scene: string; at: number }[] {
  const scenes = JSON.parse(readFileSync(join(dir, `${name}.scenes.json`), 'utf8'));
  let bars: number[] = [];
  try { bars = JSON.parse(readFileSync(join(dir, 'stage', 'timeline.json'), 'utf8')).downbeats || []; } catch {}
  return scenes.map((s: any) => ({ scene: s.scene, at: s.at ?? (s.bar != null ? bars[s.bar] ?? 0 : 0) }));
}

export function musicShot(metaUrl: string): void {
  const file = fileURLToPath(metaUrl);
  const dir = dirname(file);
  const name = basename(file).replace(/\.demo\.ts$/, '');
  const music = JSON.parse(readFileSync(join(dir, `${name}.music.json`), 'utf8'));
  const plan = sceneTimes(dir, name);
  const start = Number(process.env.WEBSHOTS_START ?? music.start ?? 0);
  const end = Number(process.env.WEBSHOTS_END ?? music.end ?? music.duration);
  const format = process.env.WEBSHOTS_FORMAT || 'landscape';

  test(name, async ({ page, narration }) => {
    test.setTimeout(20 * 60_000);
    await page.route(`${ORIGIN}/**`, (route) => {
      const asset = resolveAsset(name, new URL(route.request().url()).pathname);
      if (!asset) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ body: readFileSync(asset.file), contentType: asset.type });
    });
    await page.goto(`${ORIGIN}/?format=${format}`);
    await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30_000 });
    // Jump into the scene that is active at `start` (for cuts like a Shorts hook).
    const first = [...plan].reverse().find((p) => p.at <= start) || plan[0];
    await narration.startRecording(page);
    const t0 = Date.now() - start * 1000;
    await page.evaluate((s) => (window as any).Music?.start(s), start);
    page.evaluate((n) => (window as any).scene(n), first.scene).catch(() => {});
    for (const { scene, at } of plan) {
      if (at <= start) continue;
      if (at >= end) break;
      const wait = at * 1000 - (Date.now() - t0);
      if (wait > 0) await page.waitForTimeout(wait);
      narration.mark(scene);
      page.evaluate((n) => (window as any).scene(n), scene).catch(() => {}); // never await: cuts must not drift
    }
    await page.waitForTimeout(Math.max(0, end * 1000 - (Date.now() - t0)));
  });
}

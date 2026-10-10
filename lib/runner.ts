// The recording script every shot shares. A shot's <name>.demo.ts is just:
//
//   import { shot } from '../../lib/runner.ts';
//   shot(import.meta.url);
//
// It serves the shot's stage at http://webshot.local, then plays the scenes in
// the order of <name>.scenes.json, holding each until its narration line ends.

import { readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from '@argo-video/cli';
import { resolveAsset } from './serve.mjs';

export const ORIGIN = 'http://webshot.local';

export function shot(metaUrl: string): void {
  const file = fileURLToPath(metaUrl);
  const name = basename(file).replace(/\.demo\.ts$/, '');
  const manifest = JSON.parse(readFileSync(join(dirname(file), `${name}.scenes.json`), 'utf8'));
  const scenes: string[] = manifest.map((s: { scene: string }) => s.scene);

  test(name, async ({ page, narration }) => {
    test.setTimeout(15 * 60_000);

    await page.route(`${ORIGIN}/**`, (route) => {
      const asset = resolveAsset(name, new URL(route.request().url()).pathname);
      if (!asset) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ body: readFileSync(asset.file), contentType: asset.type });
    });
    await page.goto(`${ORIGIN}/`);
    await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30_000 });
    await narration.startRecording(page);

    for (const scene of scenes) {
      narration.mark(scene);
      // Play the scene's entrance, then hold until its narration line ends.
      await page.evaluate((n) => (window as any).scene(n), scene);
      await page.waitForTimeout(narration.durationFor(scene, { fallbackMs: 3000 }));
    }
    await page.waitForTimeout(800);
  });
}

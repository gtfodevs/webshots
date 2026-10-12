// Maps a request path to a file for one shot's stage. Shared by the recorder
// (lib/runner.ts, via Playwright routing) and the preview/check server.
//
//   /            -> shots/<name>/stage/index.html
//   /kit.js      -> lib/stage-kit.js
//   /music.js    -> lib/music-kit.js   (music mode runtime)
//   /vendor/<f>  -> node_modules/gsap/dist/<f>   (gsap.min.js, MotionPathPlugin.min.js, ...)
//   /<anything>  -> shots/<name>/stage/<anything>

import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { dirname, extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = fileURLToPath(new URL('..', import.meta.url));
const require = createRequire(import.meta.url);
const GSAP_DIST = join(dirname(require.resolve('gsap/package.json')), 'dist');

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.json': 'application/json',
  '.woff2': 'font/woff2', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.webm': 'video/webm', '.mp4': 'video/mp4',
};

export function shotDir(name) {
  return join(ROOT, 'shots', name);
}

function inside(base, path) {
  const full = normalize(join(base, path));
  return full === base || full.startsWith(base + sep) ? full : null;
}

/** Returns { file, type } or null when the path is outside the stage or missing. */
export function resolveAsset(name, pathname) {
  let p = decodeURIComponent(pathname);
  if (p === '/' || p === '') p = '/index.html';
  let file;
  if (p === '/kit.js') file = join(ROOT, 'lib', 'stage-kit.js');
  else if (p === '/music.js') file = join(ROOT, 'lib', 'music-kit.js');
  else if (p.startsWith('/vendor/')) file = inside(GSAP_DIST, p.slice('/vendor/'.length));
  else file = inside(join(shotDir(name), 'stage'), p.slice(1));
  if (!file || !existsSync(file)) return null;
  return { file, type: TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream' };
}

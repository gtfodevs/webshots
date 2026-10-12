#!/usr/bin/env node
// Suno sync: the Suno profile is the source of truth for a channel's songs.
//
//   npm run suno:sync -- <song-id | @handle | profile-url> [--channel progressiveslop] [--limit 10] [--force]
//
// For each song it pulls, from Suno's public pages + CDN (no login):
//   song.mp4 (Suno's video, which carries the audio), song.m4a (audio extracted from it; the
//   .mp3 URL is usually 403 for public fetches), cover.jpeg, meta.json (title, tags/style,
//   created_at, duration, handle, urls) and lyrics.txt.
// Files land in channels/<channel>/songs/<id>/. A song is re-pulled only when its page content
// changes (sha256 of title + lyrics + tags + media urls), or with --force.
// channels/<channel>/songs.json is the index (newest first).

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from '../lib/serve.mjs';

const args = process.argv.slice(2);
const flag = (f, d) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : d; };
const target = args.find((a) => !a.startsWith('--') && !['--channel', '--limit'].some((f) => args[args.indexOf(a) - 1] === f));
if (!target) { console.error('usage: npm run suno:sync -- <song-id | @handle | profile-url> [--channel name] [--limit n] [--force]'); process.exit(1); }
const UA = { 'user-agent': 'Mozilla/5.0 (webshots suno-sync)' };
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

async function get(url, binary = false) {
  const r = await fetch(url, { headers: UA });
  if (!r.ok) return null;
  return binary ? Buffer.from(await r.arrayBuffer()) : r.text();
}
const unesc = (s) => s.replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const meta = (h, p) => (h.match(new RegExp(`<meta (?:property|name)="${p}" content="([^"]*)"`)) || [])[1];

async function songInfo(id) {
  const h = await get(`https://suno.com/song/${id}`);
  if (!h) return null;
  const flat = h.replace(/\\"/g, '"');
  const title = unesc(meta(h, 'og:title') || '');
  const desc = unesc(meta(h, 'description') || '');
  const handle = (desc.match(/\(@([^)]+)\)/) || [])[1] || null;
  const lyr = (h.match(/<p class="pr-6 whitespace-pre-wrap">([\s\S]*?)<\/p>/) || [])[1];
  const tags = (flat.match(/"tags":"((?:[^"\\]|\\.)*)"/) || [])[1] || '';
  const created = (flat.match(/"created_at":"([^"]+)"/) || [])[1] || null;
  const duration = Number((flat.match(/"duration":([\d.]+)/) || [])[1] || 0) || null;
  return { id, title, handle, created_at: created, duration, tags: unesc(tags), lyrics: lyr ? unesc(lyr) : '', url: `https://suno.com/song/${id}`,
    media: { video: `https://cdn1.suno.ai/${id}.mp4`, audio_mp3: `https://cdn1.suno.ai/${id}.mp3`, cover: `https://cdn1.suno.ai/image_large_${id}.jpeg`, og_video: meta(h, 'og:video') || null, og_image: meta(h, 'og:image') || null } };
}

async function profileSongIds(handle) {
  const h = await get(`https://suno.com/@${handle}?page=songs`);
  if (!h) throw new Error(`profile @${handle} not reachable`);
  return [...new Set(h.match(UUID) || [])].filter((u) => !/^0{8}/.test(u));
}

async function syncSong(id, channel, force) {
  const info = await songInfo(id);
  if (!info || !info.title) return { id, status: 'not-a-song' };
  if (channel.handle && info.handle && info.handle !== channel.handle) return { id, status: 'other-artist' };
  const dir = join(channel.dir, 'songs', id); mkdirSync(dir, { recursive: true });
  const hash = createHash('sha256').update(JSON.stringify([info.title, info.lyrics, info.tags, info.media])).digest('hex').slice(0, 16);
  const old = existsSync(join(dir, 'meta.json')) ? JSON.parse(readFileSync(join(dir, 'meta.json'), 'utf8')) : null;
  if (old && old.hash === hash && !force && existsSync(join(dir, 'song.m4a'))) return { id, title: info.title, status: 'unchanged', created_at: info.created_at };
  const got = {};
  for (const [file, url] of [['song.mp4', info.media.video], ['cover.jpeg', info.media.cover]]) {
    const b = await get(url, true); if (b) { writeFileSync(join(dir, file), b); got[file] = b.length; }
  }
  const mp3 = await get(info.media.audio_mp3, true); if (mp3) { writeFileSync(join(dir, 'song.mp3'), mp3); got['song.mp3'] = mp3.length; }
  if (got['song.mp4']) { try { execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', join(dir, 'song.mp4'), '-vn', '-c:a', 'copy', join(dir, 'song.m4a')]); got['song.m4a'] = true; } catch {} }
  if (info.lyrics) writeFileSync(join(dir, 'lyrics.txt'), info.lyrics);
  writeFileSync(join(dir, 'meta.json'), JSON.stringify({ ...info, lyrics: undefined, hash, synced_at: new Date().toISOString(), files: Object.keys(got) }, null, 1));
  return { id, title: info.title, status: old ? 'updated' : 'new', created_at: info.created_at, files: Object.keys(got) };
}

const channelName = flag('--channel', target.startsWith('@') ? target.slice(1) : (target.match(/@([\w-]+)/) || [])[1] || 'default');
const channel = { name: channelName, handle: target.match(UUID) ? null : channelName, dir: join(ROOT, 'channels', channelName) };
mkdirSync(channel.dir, { recursive: true });
let ids = target.match(UUID) ? [target.match(UUID)[0]] : await profileSongIds(channel.handle);
const limit = Number(flag('--limit', ids.length)); const force = args.includes('--force');
const results = [];
for (const id of ids) {
  if (results.filter((r) => ['new', 'updated', 'unchanged'].includes(r.status)).length >= limit) break;
  const r = await syncSong(id, channel, force); results.push(r);
  if (r.title) console.log(`  ${r.status.padEnd(9)} ${id}  ${r.title}`);
}
const idxFile = join(channel.dir, 'songs.json');
const idx = existsSync(idxFile) ? JSON.parse(readFileSync(idxFile, 'utf8')) : [];
for (const r of results.filter((r) => r.title)) { const i = idx.findIndex((x) => x.id === r.id); const row = { id: r.id, title: r.title, created_at: r.created_at }; i >= 0 ? (idx[i] = row) : idx.push(row); }
idx.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
writeFileSync(idxFile, JSON.stringify(idx, null, 1));
console.log(`\n${results.filter((r) => r.title).length} song(s) checked -> channels/${channelName}/ (index: songs.json)`);

/* Neon Dojo fighter engine, pure logic (no canvas). Shared by stage/index.html and scripts/fighter_qa.mjs.
   Everything is a deterministic function of the song clock t, built once from timeline.json:
     FIGHT.build(TL) -> { scenes, fights, sceneAt(t), fighterAt(fight, side, t), hud(fight, t), fx(fight, t), poseRects(char, anim, frame) }
   Placeholder art: each fighter is drawn from rects. The MASTER CORE (head + torso + belt) is the same
   rects in every frame (translated only), the limbs change per pose: the shared-master sprite method
   (docs/MUSIC_MODE.md, "THE sprite method"). When the real per-pose art lands, poseRects() is replaced by
   atlas frames built the same way and nothing else changes. Feet are anchored on the stage ground row. */
(function (root) {
'use strict';
const F = {};

// ---------- cast: master-core proportions (px at 480x270) ----------
F.CHARS = {
  uno:    { name: 'UNO',        h: 99, w: 29, head: 18, chrome: '#c9cdd9', acc: '#7b2cff', acc2: '#ffd34a', hero: 1 },
  aura:   { name: 'AURA',       h: 94, w: 23, head: 17, chrome: '#dadce6', acc: '#d0103c', acc2: '#5ee7ff', hero: 1, hair: '#2a1030' },
  tekko:  { name: 'TEKKO',      h: 86, w: 55, head: 13, chrome: '#b4b7c2', acc: '#ff3fd2', acc2: '#c08a2a' },
  kaze9:  { name: 'KAZE-9',     h: 114, w: 17, head: 14, chrome: '#c2c6d2', acc: '#5ee7ff', acc2: '#1d6f8a', montage: 1 },
  raijin: { name: 'RAIJIN',     h: 96, w: 34, head: 16, chrome: '#b6bac6', acc: '#ffe36b', acc2: '#5ee7ff', montage: 1 },
  lotus:  { name: 'LOTUS',      h: 104, w: 20, head: 16, chrome: '#d2d5df', acc: '#ff7ad9', acc2: '#3fe0c0' },
  shogun: { name: 'SHOGUN.EXE', h: 127, w: 42, head: 21, chrome: '#9a9daa', acc: '#d0102a', acc2: '#16101c', boss: 1 },
};
F.CUTIN = 0.65; F.HOLD = 0.1;
F.ROSTER = ['uno', 'aura', 'tekko', 'kaze9', 'raijin', 'lotus', 'shogun'];
F.STAGES = {
  rooftop: { name: 'NEON ROOFTOP DOJO', ground: 238, art: 'rooftop', sky: ['#120630', '#3a0f5c'], acc: '#ff3fd2' },
  alley:   { name: 'RAIN ALLEY NIGHT MARKET', ground: 238, art: 'rooftop', tint: '#8aa4ff', sky: ['#071226', '#123a5c'], acc: '#5ee7ff' },
  yard:    { name: 'NEO TRAIN YARD', ground: 238, art: 'temple', tint: '#ffc48a', sky: ['#0e0a1e', '#2c2a10'], acc: '#ffe36b' },
  garden:  { name: 'MOONLIT LOTUS TEMPLE', ground: 238, art: 'temple', sky: ['#1a0626', '#4a1446'], acc: '#ff7ad9' },
  temple:  { name: 'SHOGUN PALACE THRONE', ground: 238, art: 'palace', sky: ['#14040a', '#420a18'], acc: '#ff2a3a' },
};

// ---------- poses ----------
// A frame: { bob: hip drop px (+ = lower), lean: core x shift, legs: [[footDX, lift], [footDX, lift]] (front, back) as
// fractions of leg length, arms: [[handDX, handDY], [..]] (front, back) as fractions of torso height from the shoulder,
// air: no ground contact (ko_fall), down: lying (ko_down) }. durations in ms (hand-timed holds, uneven).
const P = (bob, legs, arms, x = {}) => Object.assign({ bob, legs, arms, lean: 0 }, x);
const STANCE_L = [[0.42, 0], [-0.34, 0]], GUARD = [[0.55, 0.15], [0.3, 0.35]];
F.ANIMS = {
  idle:    { loop: 1, durations: [300, 180, 340, 180], frames: [
            P(3, STANCE_L, GUARD), P(2, STANCE_L, [[0.55, 0.1], [0.3, 0.3]]), P(2, STANCE_L, [[0.56, 0.06], [0.31, 0.26]]), P(3, STANCE_L, [[0.56, 0.12], [0.31, 0.32]])] },
  walk:    { loop: 1, durations: [130, 110, 130, 110], frames: [          // BOB triangle [1,2,-1,0] (v4 method)
            P(4, [[0.45, 0], [-0.4, 0]], GUARD), P(5, [[0.12, 0], [-0.05, 0.22]], [[0.52, 0.16], [0.32, 0.34]]),
            P(1, [[0.4, 0.0], [-0.42, 0.0]], [[0.55, 0.12], [0.3, 0.32]], { swap: 1 }), P(2, [[0.02, 0.24], [-0.12, 0]], [[0.54, 0.18], [0.3, 0.36]])] },
  punch:   { durations: [110, 220], frames: [P(4, STANCE_L, [[0.2, 0.3], [0.35, 0.3]], { lean: -2 }), P(4, [[0.5, 0], [-0.36, 0]], [[1.05, 0.08], [0.15, 0.35]], { lean: 3 })] },
  kick:    { durations: [120, 240], frames: [P(2, [[0.22, 0.48], [-0.2, 0]], [[0.45, 0.2], [0.1, 0.3]], { lean: -1 }), P(1, [[0.98, 0.7], [-0.25, 0]], [[0.3, 0.1], [-0.15, 0.25]], { lean: -4 })] },
  special: { durations: [260, 360], frames: [P(7, [[0.5, 0], [-0.45, 0]], [[-0.25, 0.7], [-0.35, 0.65]], { lean: -3, glow: 1 }), P(5, [[0.62, 0], [-0.5, 0]], [[1.0, 0.25], [0.95, 0.4]], { lean: 4, glow: 2 })] },
  block:   { durations: [400], frames: [P(5, [[0.34, 0], [-0.4, 0]], [[0.35, -0.25], [0.28, -0.1]], { lean: -2 })] },
  hit:     { durations: [120, 230], frames: [P(2, [[0.36, 0], [-0.38, 0]], [[-0.1, -0.4], [-0.3, 0.1]], { lean: -5 }), P(4, [[0.3, 0], [-0.44, 0]], [[0.05, -0.2], [-0.2, 0.25]], { lean: -3 })] },
  ko_fall: { durations: [600], frames: [P(0, [[0.5, 0.3], [0.2, 0.5]], [[-0.6, -0.5], [-0.4, -0.7]], { lean: -8, air: 1 })] },
  ko_down: { durations: [1000], frames: [P(0, [[0, 0], [0, 0]], [[0, 0], [0, 0]], { down: 1 })] },
  victory: { durations: [260, 900], frames: [P(3, [[0.3, 0], [-0.3, 0]], [[0.4, -0.6], [0.2, 0.4]]), P(1, [[0.25, 0], [-0.28, 0]], [[0.3, -1.1], [0.15, 0.45]])] },
};
F.ANIMS.attack = F.ANIMS.punch; F.ANIMS.thrust = F.ANIMS.punch;
// Real sprite art (per-pose frames from <char>_sprites / uno_sprites.py, atlas stage/assets/px/<char>.json).
// A char listed here is drawn from its atlas; anims name atlas poses. idle_br1/2 = master idle with the chest up 1/2 px.
F.SPRITE_ANIMS = {
  uno: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [300, 180, 340, 180] },
    walk:    { loop: 1, frames: ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L'], durations: [130, 110, 130, 110] },
    punch:   { frames: ['punch_windup', 'punch_extend'], durations: [110, 220] },
    kick:    { frames: ['kick_chamber', 'kick_extend'], durations: [120, 240] },
    special: { frames: ['special_charge', 'special_release'], durations: [260, 360] },
    block:   { frames: ['block'], durations: [400] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
    victory: { frames: ['idle_br1', 'victory'], durations: [120, 900] },
  },
  // TEKKO: walk_*_R = walk_*_L with the lower body mirrored (sources were identical); ko_fall = hit tilted back 40 deg
  tekko: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [320, 200, 360, 200] },
    walk:    { loop: 1, frames: ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L'], durations: [150, 130, 150, 130] },
    punch:   { frames: ['punch_windup', 'punch_extend'], durations: [130, 220] },
    kick:    { frames: ['kick_chamber', 'kick_extend'], durations: [140, 240] },
    special: { frames: ['special_charge', 'special_release'], durations: [280, 360] },
    block:   { frames: ['block'], durations: [400] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
    victory: { frames: ['idle_br1', 'victory'], durations: [120, 900] },
  },
  // LOTUS: duplicates in the source set (see ASSET flags); special_release is airborne (lift = px above the ground)
  lotus: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [300, 180, 340, 180] },
    walk:    { loop: 1, frames: ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L'], durations: [130, 110, 130, 110] },
    punch:   { frames: ['punch_windup', 'punch_extend'], durations: [110, 220] },
    kick:    { frames: ['kick_chamber', 'kick_extend'], durations: [120, 240] },
    special: { frames: ['special_charge', 'special_release'], durations: [240, 380], lift: [0, 14] },
    block:   { frames: ['block'], durations: [400] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
    victory: { frames: ['idle_br1', 'victory'], durations: [120, 900] },
  },
  // SHOGUN.EXE (boss, 1.15x Uno): red glow / slash arcs / charge aura / KO smoke are additive fx layers per pose;
  // kick_chamber is a copy of walk_pass in the source set; thrust = bonus attack (punch_windup -> thrust_extra)
  shogun: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [340, 200, 380, 200] },
    walk:    { loop: 1, frames: ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L'], durations: [160, 140, 160, 140] },
    punch:   { frames: ['punch_windup', 'punch_extend'], durations: [130, 240] },
    thrust:  { frames: ['punch_windup', 'thrust_extra'], durations: [150, 260] },
    kick:    { frames: ['kick_chamber', 'kick_extend'], durations: [130, 240] },
    special: { frames: ['special_charge', 'special_release'], durations: [300, 380] },
    block:   { frames: ['block'], durations: [400] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
    victory: { frames: ['idle_br1', 'victory'], durations: [120, 900] },
  },
  // montage rivals: 4 source poses; breath from idle_a, ko_fall = hit tilted back; RAIJIN lightning/smoke = fx layers
  kaze9: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [260, 160, 300, 160] },
    attack:  { frames: ['idle_br2', 'attack'], durations: [100, 240] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
  },
  raijin: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [320, 200, 360, 200] },
    attack:  { frames: ['idle_br2', 'attack'], durations: [130, 260] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
  },
  // Aura: no idle_b (breath from the idle_a master); cyan energy is a separate additive fx layer per pose
  aura: {
    idle:    { loop: 1, frames: ['idle_a', 'idle_br1', 'idle_br2', 'idle_br1'], durations: [300, 180, 340, 180] },
    walk:    { loop: 1, frames: ['walk_contact_R', 'walk_pass_R', 'walk_contact_L', 'walk_pass_L'], durations: [130, 110, 130, 110] },
    punch:   { frames: ['punch_windup', 'punch_extend'], durations: [110, 220] },
    kick:    { frames: ['kick_chamber', 'kick_extend'], durations: [120, 240] },
    special: { frames: ['special_charge', 'special_release'], durations: [260, 360] },
    block:   { frames: ['block'], durations: [400] },
    hit:     { frames: ['hit'], durations: [350] },
    ko_fall: { frames: ['ko_fall'], durations: [600] },
    ko_down: { frames: ['ko_down'], durations: [1000] },
    victory: { frames: ['idle_br1', 'victory'], durations: [120, 900] },
  },
};
F.animOf = (c, a) => (F.SPRITE_ANIMS[c] && F.SPRITE_ANIMS[c][a]) || F.ANIMS[a];
// lean plan: KAZE-9 and RAIJIN (montage-only) get idle / attack / hit / KO (ASSET_LIST.md)
F.MOVESET = { full: ['idle', 'walk', 'punch', 'kick', 'special', 'block', 'hit', 'ko_fall', 'ko_down', 'victory'], montage: ['idle', 'attack', 'hit', 'ko_fall', 'ko_down'] };
F.MOVESET.boss = F.MOVESET.full.concat(['thrust']);
F.movesOf = (c) => (F.CHARS[c].montage ? F.MOVESET.montage : F.CHARS[c].boss ? F.MOVESET.boss : F.MOVESET.full);

// ---------- pose -> rects (x relative to the foot anchor, y relative to the ground row; bottom row = 0) ----------
// Rects are [x, y, w, h, colourKey, part]. part 'core' = master upper body (identical in every frame up to translation).
function line(out, x0, y0, x1, y1, th, col, part) {
  const n = Math.max(1, Math.ceil(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / 2));
  for (let i = 0; i <= n; i++) { const x = Math.round(x0 + (x1 - x0) * i / n), y = Math.round(y0 + (y1 - y0) * i / n); out.push([x - (th >> 1), y - (th >> 1), th, th, col, part]); }
}
function ik(hx, hy, fx, fy, L, dir) { // two-bone knee, knee points forward (dir)
  const dx = fx - hx, dy = fy - hy, d = Math.min(Math.hypot(dx, dy), 2 * L - 0.01), a = Math.atan2(dy, dx), b = Math.acos(d / (2 * L));
  return [hx + Math.cos(a - b * dir) * L, hy + Math.sin(a - b * dir) * L];
}
F.poseRects = function (c, anim, fi) {
  const C = F.CHARS[c], A = F.ANIMS[anim], f = A.frames[fi % A.frames.length], R = Math.round, out = [];
  const leg = R(C.h * 0.46), torso = R(C.h * 0.36), thick = Math.max(4, R(C.w / 4)), armTh = Math.max(3, R(C.w / 5));
  if (f.down) { // lying on the ground, head toward the back: core rotated 90 degrees (still the same rect sizes, swapped)
    out.push([-R(C.h * 0.55), -C.w + 1, torso, C.w, 'chrome', 'core_down'], [-R(C.h * 0.55) - C.head, -C.head + 1, C.head, C.head, 'chrome', 'head_down']);
    out.push([-R(C.h * 0.55) + torso, -thick + 1, leg + 4, thick, 'dark', 'leg'], [-R(C.h * 0.55) + 4, -C.w - 2, torso - 6, 3, 'dark', 'arm']);
    return out;
  }
  const lift0 = f.air ? 14 : 0, hipY = -(leg - f.bob) - lift0, hipX = f.lean >> 1;
  const shY = hipY - torso, coreX = f.lean;
  // legs (back first, drawn darker), feet are 3px tall slabs whose bottom row sits on the ground (y = 0) unless lifted
  [[1, 'dark'], [0, 'limb']].forEach(([k, col]) => {
    const [fdx, lift] = f.legs[k]; const fx = R(hipX + fdx * leg), fy = -R(lift * leg) - lift0;
    const [kx, ky] = ik(hipX, hipY, fx, fy - 2, leg / 2, 1);
    const n0 = out.length; line(out, hipX, hipY, kx, ky, thick, col, 'leg'); line(out, kx, ky, fx, fy - 2, thick, col, 'leg');
    for (let i = n0; i < out.length; i++) { const r = out[i]; if (r[1] + r[3] - 1 > fy) r[3] = fy - r[1] + 1; } // shin never pokes through the sole
    out.push([fx - 2, fy - 2, R(thick * 1.6), 3, col === 'dark' ? 'dark' : 'foot', 'foot']);
  });
  // MASTER CORE: torso + belt + head + eyes (sizes fixed per character)
  out.push([coreX - (C.w >> 1), shY, C.w, torso, 'chrome', 'core'], [coreX - (C.w >> 1), hipY - 4, C.w, 4, 'acc', 'core'],
    [coreX - (C.head >> 1) + 1, shY - C.head - 1, C.head, C.head, 'chrome', 'core'], [coreX - (C.head >> 1) - 1, shY - C.head + 2, 2, 6, 'acc2', 'core'],
    [coreX + (C.head >> 1) - 3, shY - C.head + 3, 3, 2, 'eye', 'core']);
  // arms (back, then front)
  [[1, 'dark'], [0, 'limb']].forEach(([k, col]) => {
    const [hdx, hdy] = f.arms[k]; const sx = coreX + (k ? -2 : 3), sy = shY + 3;
    const hx = R(sx + hdx * torso), hy = R(sy + hdy * torso); const [ex, ey] = ik(sx, sy, hx, hy, torso * 0.55, -1);
    line(out, sx, sy, ex, ey, armTh, col, 'arm'); line(out, ex, ey, hx, hy, armTh, col, 'arm');
    out.push([hx - 2, hy - 2, armTh + 2, armTh + 2, k ? 'dark' : 'fist', 'hand']);
  });
  return out;
};
F.frameKey = (c, a, i) => JSON.stringify(F.poseRects(c, a, i));
F.frameAt = function (anim, local, loop, c) { // local seconds since the anim started -> frame index
  const A = c ? F.animOf(c, anim) : F.ANIMS[anim], d = A.durations, tot = d.reduce((p, q) => p + q, 0); let ms = local * 1000;
  if (loop || A.loop) ms = ((ms % tot) + tot) % tot; else if (ms >= tot) return d.length - 1;
  let i = 0; while (i < d.length - 1 && ms >= d[i]) { ms -= d[i]; i++; } return i;
};

// ---------- timeline ----------
F.build = function (TL) {
  const BT = TL.beats, DB = TL.downbeats;
  const snap = (s) => { let b = BT[0]; for (const x of BT) if (Math.abs(x - s) < Math.abs(b - s)) b = x; return b; };
  const snapBar = (s) => { let b = DB[0]; for (const x of DB) if (Math.abs(x - s) < Math.abs(b - s)) b = x; return b; };
  const beatLen = 60 / TL.tempo, barLen = beatLen * 4;
  const S = [];
  const sc = (name, t0, o = {}) => S.push(Object.assign({ name, t0: t0 === 0 ? 0 : snapBar(t0) }, o));
  // A. attract
  sc('title', 0, { coin: snap(4.1) });
  // B. cutscenes, 8 panels x 2 bars from 7.1
  const CUT = [
    ['city', 'NEO-KYOTO. THE TOURNAMENT RETURNS.'], ['uno_eyes', 'UNO WAKES. THE "1" STILL SHINES.'],
    ['flashback', 'YEARS AGO: SENSEI GEARHART TAUGHT HIM TO STAND STILL.'], ['shogun_fire', 'THE DOJO FELL. THE BELT WAS TAKEN.'],
    ['fist', 'UNO: "I WILL TAKE IT BACK."'], ['aura_magic', 'AURA. CRIMSON HAIR, CYAN LIGHT.'],
    ['aura_chains', "SHE WAS SHOGUN'S PRISONER. NOT ANYMORE."], ['rooftop', 'TOGETHER.']];
  const barN = (sec) => DB.indexOf(snapBar(sec)), atBar = (sec, n) => DB[Math.min(DB.length - 1, barN(sec) + n)];
  CUT.forEach(([k, txt], i) => S.push({ name: 'cut', t0: atBar(7.1, 2 * i), panel: k, txt }));
  sc('select', 34.3, { lock: snap(37.6), pick: 'uno' }); sc('map', 39.3, { to: 'rooftop' });
  sc('vs', 41.0, { p1: ['uno'], p2: 'tekko', slam: snap(42.5) });
  // fights: exchanges = arrays of [sec, side(1 hero / 2 opp), move, result, dmg]; opponents fight back in EVERY exchange
  const fights = {};
  const fight = (id, o) => { o.ex = o.ex.map((e) => e.map(([s, side, move, res, dmg]) => ({ t: snap(s), side, move, res, dmg }))); fights[id] = o; return o; };
  fight('f1', { p1: 'uno', p2: 'tekko', stage: 'rooftop', t0: snapBar(44.3), round: 'ROUND 1', pips: [0, 0], ex: [
    [[46.4, 1, 'punch', 'hit', 8], [47.3, 2, 'special', 'hit', 12]],
    [[50.3, 1, 'kick', 'hit', 10], [51.6, 2, 'punch', 'hit', 8]],
    [[53.7, 2, 'kick', 'block', 2], [54.6, 1, 'punch', 'hit', 7], [55.9, 2, 'punch', 'block', 2]],
    [[57.4, 2, 'special', 'hit', 14], [58.9, 1, 'kick', 'block', 2]],
    [[62.7, 2, 'kick', 'block', 2], [64.5, 1, 'special', 'ko', 99]]], super: [64.5 - 0.95, 'uno'], win: snap(66.9) });
  S.push({ name: 'fight', t0: fights.f1.t0, fight: 'f1' });
  // D. montage 1: 7 cuts on downbeats, each a mini exchange (opponent swings too)
  const MONT = [['aura', 'kaze9', 'alley'], ['uno', 'raijin', 'yard'], ['aura', 'raijin', 'yard'], ['uno', 'kaze9', 'alley'], ['aura', 'tekko', 'rooftop'], ['uno', 'lotus', 'garden'], ['uno', 'raijin', 'yard']];
  const m0 = snapBar(68.7);
  MONT.forEach(([a, b, st], i) => {
    const t0 = atBar(68.7, i), id = 'm' + i, last = i === MONT.length - 1;
    const mv = F.CHARS[b].montage ? 'attack' : 'punch';
    fight(id, { p1: a, p2: b, stage: st, t0, montage: 1, ex: [[[t0 - 0 + beatLen * 0.9, 2, mv, i === 3 ? 'block' : 'hit', 6], [t0 + beatLen * 2.1, 1, i === 2 ? 'special' : 'kick', i === 2 || i === 4 || last ? 'ko' : 'hit', i === 2 || i === 4 || last ? 99 : 12]]],
      banner: i === 3 ? 'PERFECT' : null, walkOff: last });
    S.push({ name: 'fight', t0, fight: id, cut: 1 });
  });
  // E. fight 2: Aura vs LOTUS
  sc('vs', 80.7, { p1: ['aura'], p2: 'lotus', slam: snap(81.4) });
  fight('f2', { p1: 'aura', p2: 'lotus', stage: 'garden', t0: snapBar(82.1), round: 'ROUND 1', pips: [1, 0], ex: [
    [[84.0, 2, 'kick', 'block', 2], [85.2, 1, 'punch', 'hit', 8]],
    [[88.5, 1, 'kick', 'hit', 10], [89.6, 2, 'punch', 'hit', 9]],
    [[91.6, 1, 'punch', 'hit', 8], [93.0, 2, 'special', 'hit', 14]],
    [[95.4, 2, 'kick', 'block', 2], [96.3, 2, 'kick', 'hit', 10], [98.6, 1, 'kick', 'hit', 10]],
    [[100.2, 2, 'punch', 'block', 2], [102.1, 1, 'punch', 'hit', 9], [103.4, 2, 'kick', 'block', 2]],
    [[104.4, 2, 'punch', 'hit', 6], [105.6, 1, 'special', 'ko', 99]]], super: [105.6 - 0.95, 'aura'], win: snap(106.4) });
  S.push({ name: 'fight', t0: fights.f2.t0, fight: 'f2' });
  // F. boss drama
  sc('boss_intro', 108.0, { counts: [snap(108.0), snap(108.0 + beatLen), snap(108.0 + 2 * beatLen), snap(108.0 + 3 * beatLen)], helm: snapBar(111.3), belt: snapBar(113.0), card: snap(115.2), warn: snap(118.0) });
  sc('vs', 119.7, { p1: ['uno', 'aura'], p2: 'shogun', slam: snap(121.4) });
  // G + H. boss fight with tag-ins; bridge standoff; SHOGUN super cut-in; freeze frame KO
  fight('boss', { p1: 'uno', p2: 'shogun', stage: 'temple', t0: snapBar(123.4), round: 'FINAL ROUND', pips: [2, 0], tag: [[snap(130.2), 'aura'], [snap(133.5), 'uno']], ex: [
    [[125.0, 2, 'punch', 'block', 3], [126.7, 2, 'special', 'ko_down', 18], [127.6, 1, 'kick', 'block', 2]],
    [[128.3, 2, 'kick', 'block', 3], [129.4, 1, 'punch', 'hit', 7]],
    [[131.0, 2, 'thrust', 'hit', 9], [131.7, 1, 'punch', 'hit', 12]],
    [[133.0, 2, 'special', 'block', 4], [134.4, 1, 'kick', 'hit', 9], [135.9, 2, 'punch', 'hit', 10]],
    [[140.8, 1, 'special', 'block', 4], [141.6, 2, 'kick', 'hit', 8]],
    [[143.0, 2, 'special', 'block', 4], [144.2, 1, 'special', 'ko', 99]]],
    standoff: [snap(137.1), 142.0], super: [143.0 - 0.95, 'shogun'], freeze: [snap(144.2), snap(144.2) + barLen], win: snap(147.8) });
  S.push({ name: 'fight', t0: fights.boss.t0, fight: 'boss' });
  // I. ending
  sc('ending', 150.8, { crawl: snap(159.3), walk: snap(162.2), over: snap(165.5) });
  S.sort((a, b) => a.t0 - b.t0);
  S.forEach((s, i) => (s.t1 = i + 1 < S.length ? S[i + 1].t0 : TL.duration));
  const sceneAt = (t) => { let s = S[0]; for (const x of S) if (t >= x.t0 - 1e-6) s = x; return s; };

  // ---------- per-fight derived state ----------
  for (const [id, f] of Object.entries(fights)) {
    f.id = id; f.events = f.ex.flat().sort((a, b) => a.t - b.t); f.ground = F.STAGES[f.stage].ground;
    f.end = (S.find((s) => s.fight === id) || {}).t1 || f.t0 + 30;
    f.ko = f.events.find((e) => e.res === 'ko');
    // hit-stop (frames frozen) after every connecting hit: 4 frames (special 6)
    f.stops = f.events.filter((e) => e.res !== 'block').map((e) => [e.t, (e.move === 'special' || e.res === 'ko' ? 6 : 4) / 30]);
  }
  const warp = (f, t) => { let d = 0; for (const [s, l] of f.stops) d += Math.max(0, Math.min(t - s, l)); return t - d; };
  function hp(f, side, t) { let v = 100; for (const e of f.events) if (e.t <= t && e.side !== side) v -= e.dmg; if (f.ko && t >= f.ko.t && f.ko.side !== side) v = 0; return Math.max(0, Math.min(100, f.ko && f.ko.side === side ? Math.max(v, 22) : v)); }
  const trail = (f, side, t) => { const now = hp(f, side, t), past = hp(f, side, t - 0.45), k = Math.min(1, Math.max(0, (t - lastHit(f, side, t) - 0.45) / 0.35)); return Math.max(now, past + (now - past) * k); };
  const lastHit = (f, side, t) => { let l = -9; for (const e of f.events) if (e.t <= t && e.side !== side && e.res !== 'block') l = e.t; return l; };
  // ---------- fighter state machine: idle-breath / walk / attack / block / hit / KO / victory ----------
  // Priority: KO > victory > hit > block > attack > walk (approach / retreat) > idle. Times are hit-stop warped.
  function fighterAt(f, side, t) {
    const W = warp(f, t), me = side === 1 ? (f.tagged ? f.tagged(t) : f.p1) : f.p2, home = side === 1 ? 168 : 312, dir = side === 1 ? 1 : -1;
    const C = F.CHARS[me], moves = F.movesOf(me), st = { char: me, side, flip: side === 2, x: home, anim: 'idle', frame: 0, air: 0 };
    const pick = (anim, local, loop) => { const a = moves.includes(anim) ? anim : (anim === 'punch' || anim === 'kick' || anim === 'special' ? 'attack' : anim === 'walk' || anim === 'victory' || anim === 'block' ? 'idle' : anim); st.anim = a; st.frame = F.frameAt(a, local, loop, me); };
    pick('idle', W - f.t0 + side * 0.37, 1);
    let x = home;
    for (const e of f.events) {
      const dt = W - warp(f, e.t), atk = e.side === side, reach = 70 + (C.w >> 1);
      if (atk) { // approach (walk) -> strike -> retreat (walk back)
        const app = 0.42, k = dt < -app ? 0 : dt < -0.16 ? (dt + app) / (app - 0.16) : dt < 0.3 ? 1 : dt < 0.7 ? 1 - (dt - 0.3) / 0.4 : 0;
        x += dir * Math.round(k * (Math.abs(312 - 168) - reach));
        if (dt >= -app && dt < -0.16) pick('walk', dt + app, 1);
        else if (dt >= -0.16 && dt < 0.3) pick(e.move, dt + 0.16);
        else if (dt >= 0.3 && dt < 0.7) pick('walk', dt - 0.3, 1);
      } else {
        const kb = e.res === 'block' ? 4 : 12; const k = dt < 0 ? 0 : dt < 0.25 ? dt / 0.25 : dt < 0.8 ? 1 - (dt - 0.25) / 0.55 : 0;
        x -= dir * Math.round(k * kb) - dir * Math.round((dt >= -0.6 && dt < 0.8 ? 1 : 0) * 0);
        if (e.res === 'block' && dt >= -0.12 && dt < 0.3) pick('block', dt + 0.12);
        else if (e.res !== 'block' && e.res !== 'ko' && dt >= 0 && dt < 0.35) pick('hit', dt);
        else if (e.res === 'ko_down' && dt >= 0.35 && dt < 1.6) { pick(dt < 0.75 ? 'ko_fall' : 'ko_down', dt - 0.35); }
      }
    }
    if (f.ko) { const dt = W - warp(f, f.ko.t);
      if (f.ko.side !== side && dt >= 0) { const fall = Math.min(1, dt / 0.6); x -= dir * Math.round(46 * fall); if (dt < 0.6) { pick('ko_fall', dt); st.air = 1; st.lift = Math.round(Math.sin(fall * Math.PI) * 22); } else pick('ko_down', dt - 0.6); }
      if (f.ko.side === side && f.win && t >= f.win) pick('victory', t - f.win);
    }
    if (f.walkOff && side === 1 && f.ko && t > f.ko.t + 0.5) { pick('walk', t - f.ko.t, 1); x -= Math.round((t - f.ko.t - 0.5) * 60); st.flip = true; }
    if (f.standoff && t >= f.standoff[0] && t < f.standoff[1]) { pick('idle', t - f.standoff[0], 1); x = home + dir * 30; }
    if (st.anim === 'ko_fall') st.air = 1;
    { const SA = F.SPRITE_ANIMS[me] && F.SPRITE_ANIMS[me][st.anim]; if (SA && SA.lift && SA.lift[st.frame]) { st.air = 1; st.lift = SA.lift[st.frame]; } }
    st.x = x; st.y = f.ground - (st.lift || 0);
    return st;
  }
  function hud(f, t) {
    const timer = Math.max(0, 99 - Math.floor(Math.max(0, t - f.t0) / (2 * beatLen)));
    return { p1: { name: F.CHARS[f.tagged ? f.tagged(t) : f.p1].name, hp: hp(f, 1, t), trail: trail(f, 1, t) }, p2: { name: F.CHARS[f.p2].name, hp: hp(f, 2, t), trail: trail(f, 2, t) }, timer, pips: f.pips || [0, 0] };
  }
  function fx(f, t) { // sparks, shake, combo, banners
    const out = { sparks: [], shake: 0, combo: null, banner: null };
    for (const e of f.events) { const dt = t - e.t;
      if (dt >= 0 && dt < 0.2) { out.sparks.push({ x: e.side === 1 ? 262 : 218, y: f.ground - (e.move === 'kick' ? 44 : 54), kind: e.res === 'block' ? 'block' : e.move === 'special' || e.res === 'ko' ? 'big' : 'small', frame: Math.min(2, Math.floor(dt / 0.067)), side: e.side }); if (e.res !== 'block') out.shake = Math.max(out.shake, dt < 0.2 ? (e.move === 'special' || e.res === 'ko' ? 4 : 2) : 0); }
    }
    // combo: consecutive connecting hits by the same side within 1.4 s
    let run = [], best = null; for (const e of f.events) { if (e.t > t) break; if (e.res === 'block') { run = []; continue; } if (run.length && (run[run.length - 1].side !== e.side || e.t - run[run.length - 1].t > 1.4)) run = []; run.push(e); if (run.length >= 2 && t - e.t < 0.9) best = { n: run.length, side: e.side }; }
    out.combo = best;
    if (!f.montage && t >= f.t0 && t < f.t0 + barLen) out.banner = t < f.t0 + barLen * 0.55 ? f.round : 'FIGHT!';
    if (f.ko && t >= f.ko.t && t < f.ko.t + barLen * 1.2) out.banner = 'K.O.';
    if (f.win && t >= f.win) out.banner = f.p2 === 'shogun' ? 'YOU WIN' : 'YOU WIN';
    if (f.banner && t >= f.events[f.events.length - 1].t) out.banner = f.banner;
    if (f.freeze && t >= f.freeze[0] && t < f.freeze[1]) out.freeze = 1;
    // super: SF2 cut-in band for F.CUTIN s, with the world held still from F.HOLD s before it (no other fx stacked)
    if (f.super && t >= f.super[0] && t < f.super[0] + F.CUTIN) out.cutin = { who: f.super[1], t0: f.super[0], t1: f.super[0] + F.CUTIN };
    if (f.super && t >= f.super[0] - F.HOLD && t < f.super[0] + F.CUTIN) { out.hold = f.super[0] - F.HOLD; out.sparks = []; out.combo = null; out.shake = 0; }
    return out;
  }
  // tag team (boss fight): which hero is in
  for (const f of Object.values(fights)) if (f.tag) { const tags = f.tag; f.tagged = (t) => { let c = f.p1; for (const [s, who] of tags) if (t >= s) c = who; return c; }; }
  return { TL, scenes: S, fights, sceneAt, fighterAt, hud, fx, snap, snapBar, beatLen, barLen, warp, hp };
};
if (typeof module !== 'undefined' && module.exports) module.exports = F; else root.FIGHT = F;
})(typeof globalThis !== 'undefined' ? globalThis : this);

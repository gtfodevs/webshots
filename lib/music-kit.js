/* webshots music kit (served at /music.js). Load after /kit.js and GSAP.
 *
 * A music stage is a normal webshots stage (scenes, Webshot.scene, Webshot.start) plus a song
 * clock. The recorder calls Music.start() at song time 0; everything here is driven by that clock
 * and by the analyzed timeline (timeline.json: beats, downbeats/bars, sections, energy, lyrics).
 *
 *   await Music.load('timeline.json');           // before Webshot.start()
 *   Music.onBeat((b) => ...); Music.onBar(...); Music.onSection(...); Music.onLyric(...);
 *   Music.cam.punch(); Music.cam.shake(); Music.cam.to({x, y, zoom}, beats);
 *   Music.parallax('#layers');                   // [data-depth] children drift with the camera
 *   Music.particles(el, {kind:'embers'});
 *   Music.fx.slam(el) / float / shatter / pop / pulse / wobble / squash
 *   Music.lyrics({style:'karaoke'|'slam'|'ticker'|'comic', theme:'fantasy'})
 *   Comic: Music.comic.panels(el), .sfx(text, opts), .bubble(el, text), .caption(el, text)
 *
 * Layer model (see docs/MUSIC_MODE.md): every scene is a stack of layers inside #camera:
 *   bg (data-depth .2) / mid (.5) / fg (1) / ui (no data-depth: never moved by the camera). A layer is any element;
 *   type="clip" layers (<video>) and a future type="3d" slot (<canvas data-layer="3d">) follow the
 *   same depth/camera contract, so video and 3D can be mixed in later without changing scenes.
 */
(() => {
  const M = (window.Music = {});
  let TL = { beats: [], downbeats: [], bars: [], sections: [], energy: [], lyrics: [] };
  let T0 = null, raf = 0, frozen = null;
  const hooks = { beat: [], bar: [], section: [], lyric: [], frame: [] };
  const fired = { beat: -1, bar: -1, section: -1, lyric: -1 };

  M.load = async (url = 'timeline.json') => {
    TL = await (await fetch(url)).json();
    TL.lyrics = TL.lyrics || [];
    M.timeline = TL;
    M.beatLen = TL.beats.length > 1 ? (TL.beats[TL.beats.length - 1] - TL.beats[0]) / (TL.beats.length - 1) : 0.5;
    M.barLen = M.beatLen * 4;
    return TL;
  };
  /** Song time in seconds (frozen time in check mode, so screenshots are deterministic). */
  M.time = () => (frozen != null ? frozen : T0 == null ? 0 : (performance.now() - T0) / 1000);
  M.start = (offset = 0) => { T0 = performance.now() - offset * 1000; cancelAnimationFrame(raf); loop(); };
  M.freeze = (t) => { frozen = t; tick(true); };
  const idxAt = (arr, t, key) => { let lo = -1; for (let i = 0; i < arr.length; i++) { if ((key ? arr[i][key] : arr[i]) <= t) lo = i; else break; } return lo; };
  M.beatAt = (t = M.time()) => idxAt(TL.beats, t);
  M.barAt = (t = M.time()) => idxAt(TL.downbeats, t);
  M.sectionAt = (t = M.time()) => TL.sections[idxAt(TL.sections, t, 't')];
  M.energyAt = (t = M.time()) => { const i = idxAt(TL.energy, t, 't'); return i >= 0 ? TL.energy[i].v : 0; };
  /** 0..1 phase within the current beat; 0 = on the beat. */
  M.phase = (t = M.time()) => { const i = M.beatAt(t); if (i < 0) return 0; const a = TL.beats[i], b = TL.beats[i + 1] ?? a + M.beatLen; return (t - a) / (b - a); };
  /** Beat-locked envelope: 1 on the beat, decays to 0 (use for pulses). */
  M.pulse = (t = M.time(), sharp = 4) => Math.exp(-sharp * M.phase(t));
  /** Seconds -> beats and back, for beat-locked durations. */
  M.beats = (n) => n * M.beatLen;
  M.bars = (n) => n * M.barLen;
  /** Time of the next beat/bar at or after t, for quantizing cuts. */
  M.nextBeat = (t = M.time()) => TL.beats.find((b) => b >= t) ?? t;
  M.nextBar = (t = M.time()) => TL.downbeats.find((b) => b >= t) ?? t;
  M.quantize = (t, grid = 'beat') => { const arr = grid === 'bar' ? TL.downbeats : TL.beats; return arr.reduce((a, b) => (Math.abs(b - t) < Math.abs(a - t) ? b : a), t); };

  ['beat', 'bar', 'section', 'lyric', 'frame'].forEach((k) => { M['on' + k[0].toUpperCase() + k.slice(1)] = (fn) => (hooks[k].push(fn), () => (hooks[k] = hooks[k].filter((f) => f !== fn))); });
  function fire(kind, i, payload) { if (i !== fired[kind] && i >= 0) { fired[kind] = i; hooks[kind].forEach((f) => { try { f(payload, i); } catch (e) { console.error(e); } }); } }
  function tick(quiet) {
    const t = M.time();
    if (!quiet) {
      fire('beat', M.beatAt(t), { i: M.beatAt(t), t: TL.beats[M.beatAt(t)], bar: M.barAt(t), downbeat: TL.downbeats.includes(TL.beats[M.beatAt(t)]), energy: M.energyAt(t) });
      fire('bar', M.barAt(t), { i: M.barAt(t), t: TL.downbeats[M.barAt(t)] });
      const si = idxAt(TL.sections, t, 't'); fire('section', si, TL.sections[si]);
    }
    let li = -1; TL.lyrics.forEach((l, i) => { if (t >= l.t - 0.12 && t < l.end) li = i; });
    if (li !== fired.lyric) { fired.lyric = li; hooks.lyric.forEach((f) => f(TL.lyrics[li] || null, li)); }
    hooks.frame.forEach((f) => f(t));
  }
  function loop() { tick(false); raf = requestAnimationFrame(loop); }

  /* ---------- easing ---------- */
  // Beat-locked ease: lands exactly on the next beat when duration = M.beats(n).
  M.ease = { hit: 'expo.out', land: 'back.out(2.2)', snap: 'power4.out', drop: 'bounce.out', swing: 'sine.inOut' };

  /* ---------- camera ---------- */
  const cam = { x: 0, y: 0, zoom: 1, rot: 0, el: null };
  // The camera moves layers (parallax by data-depth) and comic pages, never the ui layer,
  // so lyrics, captions and SFX stay put while the world pans, zooms and shakes.
  function applyCam() {
    document.querySelectorAll('.scene [data-depth], .scene .c-page').forEach((l) => {
      const d = l.dataset.depth != null ? +l.dataset.depth : 1;
      l.style.transformOrigin = '50% 50%';
      l.style.transform = `translate(${-cam.x * d}px,${-cam.y * d}px) scale(${1 + (cam.zoom - 1) * Math.max(d, 0.4)}) rotate(${cam.rot}deg)`;
    });
  }
  M.cam = {
    state: cam,
    set(v) { Object.assign(cam, v); applyCam(); },
    to(v, beats = 4, ease = 'sine.inOut') { return gsap.to(cam, { ...v, duration: M.beats(beats), ease, onUpdate: applyCam }); },
    punch(amount = 0.06, beats = 1) { return gsap.fromTo(cam, { zoom: cam.zoom + amount }, { zoom: cam.zoom, duration: M.beats(beats), ease: 'expo.out', onUpdate: applyCam }); },
    shake(px = 14, beats = 0.75) {
      const base = { x: cam.x, y: cam.y }; const tl = gsap.timeline({ onUpdate: applyCam });
      const n = 8; for (let i = 0; i < n; i++) tl.to(cam, { x: base.x + (Math.random() - 0.5) * px * 2 * (1 - i / n), y: base.y + (Math.random() - 0.5) * px * 2 * (1 - i / n), rot: (Math.random() - 0.5) * px * 0.1 * (1 - i / n), duration: M.beats(beats) / n });
      return tl.to(cam, { ...base, rot: 0, duration: 0.05 });
    },
    reset() { gsap.killTweensOf(cam); Object.assign(cam, { x: 0, y: 0, zoom: 1, rot: 0 }); applyCam(); },
  };

  /* ---------- parallax ---------- */
  M.parallax = (root, { drift = 30, beats = 16 } = {}) => {
    const layers = [...(typeof root === 'string' ? document.querySelector(root) : root).querySelectorAll('[data-depth]')];
    return layers.map((l) => gsap.to(l, { xPercent: 0, x: `-=${drift * +l.dataset.depth}`, duration: M.beats(beats), ease: 'none', repeat: -1, yoyo: true }));
  };

  /* ---------- particles ---------- */
  const KINDS = {
    embers: { colors: ['#ffb02e', '#ff6a1a', '#ffd76a'], size: [3, 7], vy: [-260, -120], vx: [-40, 40], life: [1.4, 2.6], from: 'bottom' },
    sparkles: { colors: ['#fff', '#7ef9ff', '#ffe66d'], size: [3, 6], vy: [-60, 60], vx: [-60, 60], life: [0.6, 1.2], from: 'center', shape: 'star' },
    confetti: { colors: ['#ff4fa3', '#ffc83d', '#5ee7ff', '#7cff6b'], size: [6, 12], vy: [120, 300], vx: [-60, 60], life: [2, 3.2], from: 'top', shape: 'rect' },
    dust: { colors: ['rgba(255,255,255,.5)'], size: [2, 4], vy: [-20, 20], vx: [10, 40], life: [3, 5], from: 'any' },
  };
  const rnd = (a, b) => a + Math.random() * (b - a);
  M.particles = (host, { kind = 'embers', rate = 18, burst = 0, area } = {}) => {
    const k = KINDS[kind] || KINDS.embers; const el = typeof host === 'string' ? document.querySelector(host) : host;
    const box = area || { x: 0, y: 0, w: 1280, h: 720 };
    const spawn = (n, cx, cy) => { for (let i = 0; i < n; i++) {
      const p = document.createElement('i'); const s = rnd(...k.size);
      Object.assign(p.style, { position: 'absolute', width: s + 'px', height: (k.shape === 'rect' ? s * 0.5 : s) + 'px', background: k.colors[i % k.colors.length], borderRadius: k.shape ? '1px' : '50%', pointerEvents: 'none', boxShadow: kind === 'embers' ? '0 0 8px #ff8a2a' : 'none', clipPath: k.shape === 'star' ? 'polygon(50% 0,61% 39%,100% 50%,61% 61%,50% 100%,39% 61%,0 50%,39% 39%)' : 'none' });
      const x = cx ?? (k.from === 'center' ? box.x + box.w / 2 : box.x + rnd(0, box.w)); const y = cy ?? (k.from === 'bottom' ? box.y + box.h : k.from === 'top' ? box.y - 10 : k.from === 'center' ? box.y + box.h / 2 : box.y + rnd(0, box.h));
      p.style.left = x + 'px'; p.style.top = y + 'px'; el.appendChild(p);
      const life = rnd(...k.life);
      gsap.to(p, { x: rnd(...k.vx) * life, y: rnd(...k.vy) * life, rotation: rnd(-360, 360), opacity: 0, duration: life, ease: 'power1.out', onComplete: () => p.remove() });
    } };
    if (burst) spawn(burst);
    const iv = rate ? setInterval(() => spawn(Math.max(1, Math.round(rate / 10 * (0.5 + M.energyAt())))), 100) : 0;
    return { burst: (n = 30, x, y) => spawn(n, x, y), stop: () => clearInterval(iv) };
  };

  /* ---------- motion presets ---------- */
  const $ = (t) => (typeof t === 'string' ? document.querySelectorAll(t) : t);
  M.fx = {
    slam: (t, o = {}) => gsap.fromTo($(t), { scale: o.from ?? 3, autoAlpha: 0, rotation: o.rot ?? -6 }, { scale: 1, autoAlpha: 1, rotation: o.rot ?? -6, duration: o.duration ?? M.beats(0.5), ease: 'power4.in', onComplete: () => o.shake !== false && M.cam.shake(o.shake ?? 10, 0.5) }),
    pop: (t, o = {}) => gsap.fromTo($(t), { scale: 0, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: o.duration ?? M.beats(0.75), ease: 'back.out(2.6)', stagger: o.stagger ?? 0 }),
    float: (t, o = {}) => gsap.to($(t), { y: `-=${o.px ?? 12}`, rotation: o.rot ?? 0, duration: M.beats(o.beats ?? 2), yoyo: true, repeat: -1, ease: 'sine.inOut' }),
    pulse: (t, o = {}) => { const els = $(t); return M.onBeat((b) => { if (o.downbeatOnly && !b.downbeat) return; gsap.fromTo(els, { scale: 1 + (o.amount ?? 0.08) * (b.downbeat ? 1.6 : 1) }, { scale: 1, duration: M.beats(0.9), ease: 'expo.out', transformOrigin: o.origin ?? '50% 50%' }); }); },
    squash: (t, o = {}) => gsap.timeline().to($(t), { scaleX: 1.25, scaleY: 0.75, duration: M.beats(0.15), transformOrigin: o.origin ?? '50% 100%' }).to($(t), { scaleX: 0.9, scaleY: 1.15, duration: M.beats(0.2) }).to($(t), { scaleX: 1, scaleY: 1, duration: M.beats(0.4), ease: 'elastic.out(1,.4)' }),
    wobble: (t, o = {}) => gsap.to($(t), { rotation: o.deg ?? 4, duration: M.beats(o.beats ?? 0.5), yoyo: true, repeat: -1, ease: 'sine.inOut', transformOrigin: '50% 50%' }),
    shatter: (t, o = {}) => {
      // Splits an element into a grid of clipped copies that fly apart (or assemble with reverse:true).
      const el = typeof t === 'string' ? document.querySelector(t) : t; const r = el.getBoundingClientRect(); const host = el.parentElement;
      const n = o.pieces ?? 4, pieces = [];
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
        const c = el.cloneNode(true); c.removeAttribute('id'); c.style.position = 'absolute'; c.style.left = el.offsetLeft + 'px'; c.style.top = el.offsetTop + 'px'; c.style.margin = '0'; c.style.width = r.width + 'px';
        const x0 = (j / n) * 100, y0 = (i / n) * 100, x1 = ((j + 1) / n) * 100, y1 = ((i + 1) / n) * 100, jit = () => (Math.random() - 0.5) * 8;
        c.style.clipPath = `polygon(${x0 + jit()}% ${y0 + jit()}%, ${x1 + jit()}% ${y0 + jit()}%, ${x1 + jit()}% ${y1 + jit()}%, ${x0 + jit()}% ${y1 + jit()}%)`;
        host.appendChild(c); pieces.push(c);
      }
      el.style.visibility = 'hidden';
      const fly = { x: () => rnd(-500, 500), y: () => rnd(-300, 400), rotation: () => rnd(-200, 200), autoAlpha: 0 };
      return o.reverse
        ? gsap.from(pieces, { ...fly, duration: M.beats(o.beats ?? 2), ease: 'power3.out', stagger: 0.02, onComplete: () => { el.style.visibility = ''; pieces.forEach((p) => p.remove()); } })
        : gsap.to(pieces, { ...fly, duration: M.beats(o.beats ?? 2), ease: 'power2.out', stagger: 0.01, onComplete: () => pieces.forEach((p) => p.remove()) });
    },
  };

  /* ---------- themes ---------- */
  M.themes = {
    fantasy: { font: '"Cinzel Decorative", serif', sfx: 'Bangers, Impact, sans-serif', ink: '#1b1030', a: '#ffc83d', b: '#ff4fa3', c: '#5ee7ff', paper: '#fff6e0' },
    hiphop: { font: 'Bangers, Impact, sans-serif', sfx: 'Bangers, Impact, sans-serif', ink: '#0b0b0b', a: '#ffe600', b: '#ff2e63', c: '#08d9d6', paper: '#fffef5' },
    synthwave: { font: '"Monoton", "Bungee", sans-serif', sfx: 'Bungee, Impact, sans-serif', ink: '#120024', a: '#ff2bd6', b: '#00e5ff', c: '#ffd319', paper: '#1a0033' },
    party: { font: 'Bungee, Impact, sans-serif', sfx: 'Bungee, Impact, sans-serif', ink: '#111', a: '#ff4fa3', b: '#ffc83d', c: '#5ee7ff', paper: '#fff' },
  };
  M.theme = (name) => { const th = M.themes[name] || M.themes.fantasy; const r = document.documentElement.style; Object.entries(th).forEach(([k, v]) => r.setProperty('--m-' + k, v)); M.currentTheme = th; return th; };

  /* ---------- lyrics ---------- */
  const CSS = `
  .m-lyr{position:absolute;left:0;right:0;z-index:80;text-align:center;pointer-events:none;padding:0 80px}
  .m-lyr .w{display:inline-block;margin:0 .14em;opacity:0;transform:translateY(22px) scale(.6);transition:opacity .1s,transform .22s cubic-bezier(.3,1.8,.5,1),color .15s}
  .m-lyr .w.on{opacity:1;transform:none}
  .m-lyr.karaoke{bottom:40px}.m-lyr.karaoke .w{opacity:.35;transform:none;font:900 40px/1.25 Inter,sans-serif;color:#fff;text-shadow:0 3px 0 var(--m-ink),0 0 16px rgba(0,0,0,.8)}
  .m-lyr.karaoke .w.on{opacity:1;color:var(--m-a)}
  .m-lyr.slam{top:50%;transform:translateY(-50%)}.m-lyr.slam .w{font:400 92px/1 var(--m-sfx);letter-spacing:.03em;color:var(--m-b);-webkit-text-stroke:4px var(--m-ink);paint-order:stroke fill;text-shadow:7px 7px 0 var(--m-ink)}
  .m-lyr.slam .w{transform:scale(2.6) rotate(-8deg)}.m-lyr.slam .w.on{transform:rotate(-3deg)}
  .m-lyr.ticker{bottom:0;height:64px;background:var(--m-ink);overflow:hidden;white-space:nowrap;text-align:left;padding:0}
  .m-lyr.ticker .w{font:700 34px/64px Inter,sans-serif;color:var(--m-a);transform:translateX(40px)}
  .m-lyr.comic{bottom:36px}.m-lyr.comic .box{display:inline-block;background:var(--m-paper);border:4px solid var(--m-ink);box-shadow:6px 6px 0 var(--m-ink);padding:10px 22px;transform:rotate(-1deg)}
  .m-lyr.comic .w{font:400 40px/1.15 "Comic Neue","Bangers",sans-serif;color:var(--m-ink);text-transform:uppercase;letter-spacing:.02em}
  .m-lyr .w.hot{color:var(--m-a)!important}
  .m-lyr.comic .w.hot{color:var(--m-b)!important}`;
  M.lyrics = (opts = {}) => {
    const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    const host = document.createElement('div'); host.className = 'm-lyr'; document.body.appendChild(host);
    const styleFor = opts.styleFor || (() => opts.style || 'karaoke');
    const hot = opts.hot ? new RegExp(opts.hot, 'i') : null;
    let words = [];
    M.onLyric((line, i) => {
      host.innerHTML = ''; words = [];
      if (!line || (opts.hide && opts.hide(line, M.time()))) return;
      const style = styleFor(line, i); host.className = 'm-lyr ' + style;
      const wrap = style === 'comic' ? Object.assign(document.createElement('span'), { className: 'box' }) : host;
      if (wrap !== host) host.appendChild(wrap);
      line.words.forEach((w) => { const s = document.createElement('span'); s.className = 'w' + (hot && hot.test(w.w) ? ' hot' : ''); s.textContent = w.w; s.dataset.t = w.t; wrap.appendChild(s); words.push(s); });
      if (style === 'slam') gsap.fromTo(host, { y: 0 }, { y: 0 });
    });
    M.onFrame((t) => words.forEach((s) => { if (!s.classList.contains('on') && t >= +s.dataset.t - 0.04) { s.classList.add('on'); if (host.classList.contains('slam') && /kingdom|drum|fire|whole/i.test(s.textContent)) M.cam.punch(0.03, 0.5); } }));
    return host;
  };

  /* ---------- comic ---------- */
  const CCSS = `
  .c-page{position:absolute;inset:0;background:var(--m-ink,#111)}
  .c-panel{position:absolute;overflow:hidden;border:6px solid var(--m-ink,#111);background:var(--m-paper,#fff6e0);box-shadow:0 0 0 4px #fff inset}
  .c-halftone::after{content:"";position:absolute;inset:0;pointer-events:none;background-image:radial-gradient(rgba(0,0,0,.28) 1.2px,transparent 1.6px);background-size:7px 7px;mix-blend-mode:multiply}
  .c-ink{filter:contrast(1.25) saturate(1.25)}
  .c-sfx{position:absolute;font-family:var(--m-sfx,Bangers),Impact,sans-serif;font-size:110px;line-height:1;letter-spacing:.04em;color:var(--m-a,#ffc83d);-webkit-text-stroke:5px var(--m-ink,#111);paint-order:stroke fill;text-shadow:8px 8px 0 var(--m-ink,#111);white-space:nowrap;pointer-events:none;z-index:40}
  .c-sfx span{display:inline-block}
  .c-bubble{position:absolute;background:#fff;color:#111;border:4px solid #111;border-radius:40px;padding:14px 24px;font:700 26px/1.2 "Comic Neue","Bangers",sans-serif;text-transform:uppercase;max-width:380px;z-index:45}
  .c-bubble::after{content:"";position:absolute;left:var(--tail-x,30px);bottom:-26px;border:14px solid transparent;border-top:18px solid #111}
  .c-bubble::before{content:"";position:absolute;left:calc(var(--tail-x,30px) + 4px);bottom:-16px;border:10px solid transparent;border-top:14px solid #fff;z-index:1}
  .c-caption{position:absolute;background:#ffe66d;color:#111;border:4px solid #111;padding:8px 16px;font:700 22px/1.2 "Comic Neue","Bangers",sans-serif;text-transform:uppercase;box-shadow:5px 5px 0 #111;z-index:45}`;
  let ccss = false; const injectC = () => { if (!ccss) { const s = document.createElement('style'); s.textContent = CCSS; document.head.appendChild(s); ccss = true; } };
  M.comic = {
    /** Reveal panels (children with .c-panel) one per beat, wiping in from alternating sides. */
    panels(root, { beats = 1, from = 'alt' } = {}) {
      injectC(); const ps = [...(typeof root === 'string' ? document.querySelector(root) : root).querySelectorAll('.c-panel')];
      const tl = gsap.timeline();
      ps.forEach((p, i) => { const dir = from === 'alt' ? (i % 2 ? 'inset(0 0 0 100%)' : 'inset(0 100% 0 0)') : 'inset(100% 0 0 0)';
        tl.fromTo(p, { clipPath: dir, scale: 1.04 }, { clipPath: 'inset(0 0 0 0)', scale: 1, duration: M.beats(0.6), ease: 'power3.out' }, i * M.beats(beats)); });
      return tl;
    },
    /** SFX lettering with squash/stretch/wobble; per-letter jitter; optional beat reaction. */
    sfx(host, text, { x = 640, y = 300, size = 110, color, rot = -10, beat = true, style = 'slam' } = {}) {
      injectC(); const el = document.createElement('div'); el.className = 'c-sfx';
      el.style.left = x + 'px'; el.style.top = y + 'px'; el.style.fontSize = size + 'px'; if (color) el.style.color = color;
      el.innerHTML = [...text].map((c, i) => `<span style="transform:rotate(${(i % 2 ? 1 : -1) * (4 + Math.random() * 6)}deg) translateY(${(Math.random() - .5) * 14}px)">${c === ' ' ? '&nbsp;' : c}</span>`).join('');
      (typeof host === 'string' ? document.querySelector(host) : host).appendChild(el);
      gsap.set(el, { xPercent: -50, yPercent: -50, rotation: rot });
      const tl = gsap.timeline();
      if (style === 'slam') tl.fromTo(el, { scale: 3.2, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: M.beats(0.35), ease: 'power4.in' }).to(el, { scaleX: 1.25, scaleY: 0.8, duration: M.beats(0.12) }).to(el, { scaleX: 1, scaleY: 1, duration: M.beats(0.6), ease: 'elastic.out(1.2,.35)' });
      else tl.fromTo(el.children, { scale: 0, y: 40 }, { scale: 1, y: 0, duration: M.beats(0.5), ease: 'back.out(3)', stagger: M.beats(0.06) });
      if (beat) { const off = M.onBeat((b) => gsap.fromTo(el, { scale: b.downbeat ? 1.14 : 1.06 }, { scale: 1, duration: M.beats(0.8), ease: 'expo.out' })); el._off = off; }
      gsap.to(el.children, { rotation: '+=6', yoyo: true, repeat: -1, duration: M.beats(0.5), ease: 'sine.inOut', stagger: M.beats(0.05) });
      return el;
    },
    /** Speech bubble that pops in and types its text. */
    bubble(host, text, { x, y, tail = 30, type = true } = {}) {
      injectC(); const el = document.createElement('div'); el.className = 'c-bubble'; el.style.left = x + 'px'; el.style.top = y + 'px'; el.style.setProperty('--tail-x', tail + 'px');
      (typeof host === 'string' ? document.querySelector(host) : host).appendChild(el);
      const tl = gsap.timeline().fromTo(el, { scale: 0, transformOrigin: `${tail}px 110%` }, { scale: 1, duration: M.beats(0.5), ease: 'back.out(2.4)' });
      if (type) { const o = { n: 0 }; tl.to(o, { n: text.length, duration: Math.min(M.beats(3), text.length * 0.04), ease: 'none', onUpdate: () => (el.textContent = text.slice(0, Math.round(o.n))) }); } else el.textContent = text;
      return el;
    },
    caption(host, text, { x = 24, y = 24, type = true } = {}) {
      injectC(); const el = document.createElement('div'); el.className = 'c-caption'; el.style.left = x + 'px'; el.style.top = y + 'px';
      (typeof host === 'string' ? document.querySelector(host) : host).appendChild(el);
      const tl = gsap.timeline().fromTo(el, { x: -40, autoAlpha: 0 }, { x: 0, autoAlpha: 1, duration: M.beats(0.5), ease: 'power3.out' });
      if (type) { const o = { n: 0 }; tl.to(o, { n: text.length, duration: text.length * 0.03, ease: 'none', onUpdate: () => (el.textContent = text.slice(0, Math.round(o.n))) }); } else el.textContent = text;
      return el;
    },
  };
})();

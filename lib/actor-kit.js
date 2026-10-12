/* webshots actor kit (served at /actors.js). Load after /music.js.
 *
 * Turns approved transparent cutouts into living actors: every character runs its own loops,
 * independently and at its own phase, instead of stills that swap on the beat.
 *
 *   await Actors.load('assets/cast/rig.json');        // from scripts/rig_actor.py
 *   Actors.define('uno', { poses: { stand: 'uno-stand', sword: 'uno-sword' }, cloth: 'cape', ... });
 *   const uno = Actors.actor(hostEl, 'uno', { x: 400, y: 660, h: 430, pose: 'stand', anim: 'idle' });
 *   uno.play('groove');                // named loop (idle, groove, walk, cheer, react, attack, cast, dance, menace, bounce, ...)
 *   uno.pose('sword', { smear: 'up' }); // pose-to-pose: anticipation -> smear ghost + speed lines -> overshoot
 *   uno.accent('flare'); uno.impact('BAM!');
 *   Actors.bg(plateEl, 'lair', { glow: ['red'], eyes: [[617, 176]] });   // animated background
 *
 * How it works
 * - Each actor is a WebGL canvas drawing its cutout on a 24x32 vertex mesh. Rig points (eyes, neck,
 *   shoulders, hip, feet, headphones, extra glows) come from rig.json. The vertex shader derives smooth
 *   per-vertex weights from them (head, chest, arms/sides, hem, hair), so the head bobs, the chest
 *   breathes, arms and cape edges swing about shoulder pivots and gown/cape hems sway with a travelling
 *   sine wave, all from one image, with no cut seams. The fragment shader adds a chrome glint sweep,
 *   hit flashes and a beat-reactive rim light.
 * - A 2D overlay canvas per actor draws light: eye glow (pulse, flare, blink), headphone pulses,
 *   magic particles (stateless, so frozen check frames are deterministic).
 * - Everything is a pure function of the song clock (Music.time()), each actor with its own phase,
 *   subdivision and seed. Hops, squash, smears and impacts are GSAP tweens on a wrapper element.
 */
(() => {
  const A = (window.Actors = {});
  let RIG = {}, DEFS = {}, live = [], base = 'assets/cast/';
  const TAU = Math.PI * 2;
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ss = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
  const B = (n) => (window.Music ? Music.beats(n) : n * 0.5);

  A.load = async (url = 'assets/cast/rig.json') => { RIG = await (await fetch(url)).json(); base = url.replace(/[^/]*$/, ''); return RIG; };
  A.define = (who, def) => (DEFS[who] = { cloth: 'cape', hair: false, bob: 1, sway: 1, sub: 1, swing: 0, eye: '#ff2a2a', phones: '#5ee7ff', ...def });

  /* ---------- song-clock helpers ---------- */
  let beatIdxOfBar = null;
  function beatPos(t) {
    const M = window.Music; if (!M || !M.timeline || !M.timeline.beats.length) return { b: t / 0.5, inBar: (t / 0.5) % 4 };
    const i = M.beatAt(t); const ph = M.phase(t); const b = Math.max(0, i) + (i < 0 ? 0 : ph);
    if (!beatIdxOfBar) { const TL = M.timeline; beatIdxOfBar = TL.downbeats.map((d) => TL.beats.findIndex((x) => Math.abs(x - d) < 0.02)); }
    const bar = M.barAt(t); const b0 = bar >= 0 ? beatIdxOfBar[bar] : 0;
    return { b, inBar: b - (b0 >= 0 ? b0 : 0), energy: M.energyAt ? M.energyAt(t) : 0.6 };
  }
  A.beatPos = beatPos;

  /* ---------- named animation library ----------
     Each returns parameter offsets for this frame. k = {t, b (continuous beat), ph (0..1 in the
     actor's own subdivided beat), bar (beat within bar), e (energy), s (actor seed), d (definition), age (s since play)} */
  // beat envelope with a short eased attack (no single-frame snaps on big mesh moves), then exp decay
  const pulse = (ph, sharp = 5, att = 0.09) => { const p = ((ph % 1) + 1) % 1; return p < att ? Math.sin((Math.PI / 2) * (p / att)) : Math.exp(-sharp * (p - att)); };
  const LIB = {
    idle: (k) => ({ breath: 0.012 * Math.sin(TAU * (k.t / 3.4 + k.s)), headY: 0.004 * Math.sin(TAU * (k.t / 3.4 + k.s + 0.2)) + 0.005 * pulse(k.ph, 6) * k.d.bob,
      headRot: 1.2 * Math.sin(TAU * (k.t / 5.1 + k.s)), sway: 0.6 + 0.2 * Math.sin(k.t * 0.7), armL: 1.2 * Math.sin(TAU * (k.t / 3.4 + k.s)), armR: -1.2 * Math.sin(TAU * (k.t / 3.4 + k.s + 0.1)), lean: 0.4 * Math.sin(TAU * (k.t / 6 + k.s)) }),
    groove: (k) => ({ headY: 0.02 * pulse(k.ph, 4) * k.d.bob, headRot: 3 * Math.sin(TAU * (k.b / 2 + k.s)), bobY: -10 * Math.abs(Math.sin(Math.PI * (k.b + k.s))) * k.d.bob,
      lean: 2.2 * Math.sin(TAU * (k.b / 4 + k.s)), sway: 1.4, armL: 4 * Math.sin(TAU * (k.b / 2 + k.s)), armR: -4 * Math.sin(TAU * (k.b / 2 + k.s)), breath: 0.01 * pulse(k.ph, 3) }),
    walk: (k) => { const st = k.b + k.s; return { bobY: -9 * Math.abs(Math.sin(Math.PI * st)), lean: 3 * (k.d.dir || 1), headY: 0.006 * Math.cos(TAU * st), headRot: 1.5 * Math.sin(Math.PI * st),
      armL: 9 * Math.sin(Math.PI * st), armR: 9 * Math.sin(Math.PI * st), sway: 2.2, swayFreq: 2.2, rock: 2.5 * Math.sin(Math.PI * st) }; },
    cheer: (k) => ({ bobY: -26 * Math.max(0, Math.sin(Math.PI * (k.bar % 2) / 2)) , headRot: -4 + 4 * Math.sin(TAU * k.b), headY: -0.01 * pulse(k.ph), armL: -10 - 6 * pulse(k.ph, 3), armR: 10 + 6 * pulse(k.ph, 3), eyes: 0.5 * pulse(k.ph, 3), sway: 1.6 }),
    react: (k) => { const a = Math.exp(-k.age * 2.5); return { jitter: 5 * a, headRot: -8 * a, headY: -0.012 * a, lean: -5 * a, eyes: 1.2 * a, armL: -6 * a, armR: 6 * a }; },
    attack: (k) => { const p = k.bar % 2; const lunge = p < 0.25 ? -p / 0.25 : p < 0.45 ? -1 + 2.4 * ((p - 0.25) / 0.2) : 1.4 * Math.exp(-(p - 0.45) * 4); return { lean: 6 * lunge * (k.d.dir || 1), headRot: 3 * lunge, armR: -12 * lunge, armL: 4 * lunge, gleam: p > 0.4 && p < 1.2 ? 1 : 0, eyes: 0.6 * Math.max(0, lunge), sway: 2 }; },
    cast: (k) => ({ armL: 5 * Math.sin(TAU * k.b / 2), armR: -3 + 3 * Math.sin(TAU * (k.b / 2 + 0.25)), headRot: 2 * Math.sin(TAU * k.b / 4), bobY: -6 - 6 * Math.sin(TAU * k.b / 4), magic: 1, eyes: 0.6 + 0.4 * pulse(k.ph, 3), sway: 1.8, hairBoost: 1.5 }),
    dance: (k) => { const side = Math.sin(Math.PI * (k.b + k.s)); return { lean: 7 * side, headRot: 6 * Math.sin(Math.PI * (k.b + k.s) + 0.6), headY: 0.022 * pulse(k.ph, 4), bobY: -18 * Math.abs(Math.cos(Math.PI * (k.b + k.s))),
      armL: 10 * Math.sin(TAU * (k.b / 2 + k.s)), armR: -10 * Math.sin(TAU * (k.b / 2 + k.s + 0.25)), sway: 2.8, swayFreq: 1.6, flare: 0.04 * Math.abs(side), rock: 3 * side, eyes: 0.3 * pulse(k.ph) }; },
    twirl: (k) => ({ rock: 5 * Math.sin(TAU * k.b / 2), sway: 3.4, swayFreq: 2.4, flare: 0.07, hairBoost: 2.2, bobY: -8 * Math.abs(Math.sin(Math.PI * k.b)), headRot: 4 * Math.sin(TAU * k.b / 2) }),
    menace: (k) => ({ lean: -2 + 1.5 * Math.sin(TAU * k.t / 4), headRot: -2 * Math.sin(TAU * k.t / 4), breath: 0.02 * Math.sin(TAU * k.t / 2.6), eyes: 0.5 + 0.5 * Math.sin(TAU * k.b / 4), sway: 2.6, swayFreq: 0.9, armL: 2 * Math.sin(TAU * k.t / 4) }),
    bounce: (k) => { const e = k.b * 2 + k.s; return { bobY: -14 * Math.abs(Math.sin(Math.PI * e)), headRot: 9 * Math.sin(Math.PI * e), lean: 4 * Math.sin(Math.PI * e / 2), armL: 12 * Math.sin(Math.PI * e), armR: 12 * Math.sin(Math.PI * e + 1), sway: 2 }; },
    gallop: (k) => { const e = k.b + k.s; return { bobY: -16 * Math.abs(Math.sin(Math.PI * e)), rock: 3 * Math.sin(TAU * e), headY: 0.015 * Math.sin(TAU * e), headRot: 4 * Math.sin(TAU * e) }; },
    hover: (k) => ({ bobY: -12 - 10 * Math.sin(TAU * (k.t / 1.6 + k.s)), rock: 3 * Math.sin(TAU * (k.t / 2.4 + k.s)), headRot: 4 * Math.sin(TAU * k.t / 1.3), wing: 1 }),
    sleep: (k) => ({ breath: 0.03 * Math.sin(TAU * k.t / 2.8), headY: 0.01 * Math.sin(TAU * k.t / 2.8), eyes: -0.85 }),
    guard: (k) => ({ breath: 0.008 * Math.sin(TAU * (k.t / 3 + k.s)), headRot: 2 * Math.sin(TAU * (k.b / 8 + k.s)), headY: 0.006 * pulse(k.ph, 5), eyes: 0.2 * pulse(k.ph, 3) }),
    flex: (k) => { const p = pulse(k.ph, 3); return { armL: -8 * p - 3, armR: 8 * p + 3, breath: 0.03 * p, headRot: -3 * p, eyes: 0.4 * p, bobY: -4 * p }; },
  };
  A.anims = LIB;
  A.addAnim = (name, fn) => (LIB[name] = fn);

  /* ---------- WebGL mesh renderer ---------- */
  const VS = `
  attribute vec2 aUv; uniform vec2 uAsp; uniform float uNeck,uHip,uFeet,uTop,uCx,uHeadR,uBodyW,uSh;
  uniform vec3 uHead; uniform float uBreath,uArmL,uArmR,uLean,uSway,uSwayPh,uSwayFreq,uFlare,uHair,uHairPh,uRock,uFlip,uWing,uPad;
  varying vec2 vUv; varying float vW;
  vec2 rot(vec2 p, vec2 c, float a){ float s=sin(a),k=cos(a); p-=c; return c+vec2(p.x*k-p.y*s,p.x*s+p.y*k); }
  void main(){
    vUv=aUv; float ar=uAsp.x/uAsp.y; vec2 p=vec2(aUv.x*ar,aUv.y); float cx=uCx*ar;
    float hgt=max(uFeet-uTop,.2);
    // head: rigid above the neck, near the head column
    float wH=(1.-smoothstep(uNeck-.015,uNeck+.035,p.y))*(1.-smoothstep(uHeadR*1.6,uHeadR*3.2,abs(p.x-cx)));
    // breathing: torso stretches up from the hip, chest widens
    float wT=1.-smoothstep(uHip-.05,uHip+.05,p.y);
    float chest=exp(-pow((p.y-(uNeck+uSh)*.5-.06)/.09,2.));
    p.y-=uBreath*(uHip-p.y)*wT; p.x+=uBreath*1.4*(p.x-cx)*chest*(1.-wH);
    // arms / cape edges: rotate about shoulder pivots, only outside the torso column
    float vband=smoothstep(uNeck-.03,uNeck+.02,p.y)*(1.-smoothstep(uHip+.05,uHip+.25,p.y));
    float wL=smoothstep(uBodyW*.55,uBodyW*1.15,(cx-p.x))*vband, wR=smoothstep(uBodyW*.55,uBodyW*1.15,(p.x-cx))*vband;
    p=mix(p,rot(p,vec2(cx-uBodyW*.7,uSh),radians(uArmL)),wL);
    p=mix(p,rot(p,vec2(cx+uBodyW*.7,uSh),radians(uArmR)),wR);
    // hem: travelling sine wave below the hip, growing towards the feet, plus flare
    float wHem=pow(clamp((p.y-uHip)/max(uFeet-uHip,.1),0.,1.),1.5);
    p.x+=wHem*(uSway*.012*sin(uSwayPh+p.y*7.)+uFlare*(p.x-cx));
    // hair: side strands from the head down, wave + lag
    float wHair=uHair*smoothstep(uHeadR*.7,uHeadR*1.6,abs(p.x-cx))*smoothstep(uTop,uNeck,p.y)*(1.-smoothstep(uHip,uHip+.15,p.y));
    p.x+=wHair*.012*sin(uHairPh+p.y*11.); p.y+=wHair*.004*cos(uHairPh*1.3+p.y*9.);
    // wings (quadrupeds/dragons): upper-back region flaps
    float wWing=uWing*smoothstep(uCx*ar+.05,uCx*ar+.35,p.x)*(1.-smoothstep(uTop+.1,uHip,p.y));
    p.y+=wWing*.05*sin(uSwayPh*2.);
    // head transform last so it rides on the breathing torso
    vec2 hp=vec2(cx,uNeck); vec2 ph=rot(p,hp,radians(uHead.z))+vec2(uHead.x,uHead.y);
    p=mix(p,ph,wH);
    // whole-body lean (from the feet) and rock (rotate about the feet)
    p.x+=radians(uLean)*(uFeet-p.y);
    p=rot(p,vec2(cx,uFeet),radians(uRock));
    vW=wH;
    vec2 uv=vec2(p.x/ar,p.y);
    // canvas has padding around the image (uPad of the image size each side)
    vec2 q=(uv+uPad)/(1.+2.*uPad);
    if(uFlip>.5) q.x=1.-q.x;
    gl_Position=vec4(q.x*2.-1.,1.-q.y*2.,0.,1.);
  }`;
  const FS = `
  precision mediump float; varying vec2 vUv; varying float vW; uniform sampler2D uTex; uniform float uGleam,uGleamPos,uFlash,uRim,uGleamTop;
  void main(){
    vec4 c=texture2D(uTex,vUv); if(c.a<.01) discard;
    float lum=dot(c.rgb,vec3(.3,.59,.11));
    float band=exp(-pow((vUv.x*.6+vUv.y-uGleamPos)/.035,2.));
    float top=uGleamTop>0. ? 1.-smoothstep(uGleamTop,uGleamTop+.05,vUv.y) : 1.;
    c.rgb+=vec3(1.,.97,1.)*band*uGleam*pow(lum,1.6)*1.6*top;
    c.rgb+=uRim*vec3(.55,.25,1.)*pow(lum,3.)*.5;
    c.rgb=mix(c.rgb,vec3(1.),uFlash*c.a);
    gl_FragColor=vec4(c.rgb*c.a,c.a);
  }`;
  const GX = 24, GY = 32;
  function mesh() { const v = [], idx = []; for (let j = 0; j <= GY; j++) for (let i = 0; i <= GX; i++) v.push(i / GX, j / GY);
    for (let j = 0; j < GY; j++) for (let i = 0; i < GX; i++) { const a = j * (GX + 1) + i, b = a + 1, c = a + GX + 1, d = c + 1; idx.push(a, b, c, b, d, c); }
    return { v: new Float32Array(v), i: new Uint16Array(idx) }; }
  const MESH = mesh();
  const imgCache = {};
  const loadImg = (src) => imgCache[src] || (imgCache[src] = new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src; }));

  function makeGL(canvas) {
    const gl = canvas.getContext('webgl', { premultipliedAlpha: true, alpha: true, preserveDrawingBuffer: true, antialias: true });
    const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr); gl.useProgram(pr);
    const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, MESH.v, gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'aUv'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, MESH.i, gl.STATIC_DRAW);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    const U = {}; ['uAsp', 'uNeck', 'uHip', 'uFeet', 'uTop', 'uCx', 'uHeadR', 'uBodyW', 'uSh', 'uHead', 'uBreath', 'uArmL', 'uArmR', 'uLean', 'uSway', 'uSwayPh', 'uSwayFreq', 'uFlare', 'uHair', 'uHairPh', 'uRock', 'uFlip', 'uWing', 'uPad', 'uTex', 'uGleam', 'uGleamPos', 'uFlash', 'uRim', 'uGleamTop'].forEach((n) => (U[n] = gl.getUniformLocation(pr, n)));
    const tex = {}; const texFor = (img) => { if (tex[img.src]) return tex[img.src]; const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return (tex[img.src] = t); };
    return { gl, U, texFor };
  }

  /* JS twin of the vertex shader's head transform, for placing eye/ear lights on the warped image. */
  function headPoint(r, P, u, v, ar) {
    let x = u * ar, y = v; const cx = r.head.cx * ar;
    y -= P.breath * (r.hip - y);
    const a = (P.headRot * Math.PI) / 180, hx = cx, hy = r.head.neck; const dx = x - hx, dy = y - hy;
    x = hx + dx * Math.cos(a) - dy * Math.sin(a) + P.headX; y = hy + dx * Math.sin(a) + dy * Math.cos(a) + P.headY;
    x += ((P.lean * Math.PI) / 180) * (r.feet - y);
    const ra = (P.rock * Math.PI) / 180, fx = x - cx, fy = y - r.feet; x = cx + fx * Math.cos(ra) - fy * Math.sin(ra); y = r.feet + fx * Math.sin(ra) + fy * Math.cos(ra);
    return [x / ar, y];
  }

  const CSS = `
  .ak{position:absolute;width:0;height:0}
  .ak .ak-m,.ak .ak-t{position:absolute;left:0;top:0;width:0;height:0}
  .ak canvas{position:absolute;pointer-events:none}
  .ak .ak-shadow{position:absolute;border-radius:50%;background:radial-gradient(rgba(10,0,30,.55),rgba(10,0,30,0) 70%);transform:translate(-50%,-50%)}
  .ak-ghost{position:absolute;pointer-events:none;filter:blur(1.5px) brightness(1.4);mix-blend-mode:screen}
  .ak-lines{position:absolute;pointer-events:none;overflow:visible}
  .ak-star{position:absolute;pointer-events:none;overflow:visible}`;
  let cssOn = false;
  const PAD = 0.18;

  /** Create an actor. who = a defined character; opts: x, y (feet, in host px), h (css height of the figure),
   *  pose, anim, flip, seed (phase offset 0..1), sub (beat subdivision for its bob: 0.5 = half-time, 2 = eighths). */
  A.actor = (host, who, o = {}) => {
    if (!cssOn) { const s = document.createElement('style'); s.textContent = CSS; document.head.appendChild(s); cssOn = true; }
    const d = DEFS[who] || A.define(who, { poses: { stand: who } });
    const el = document.createElement('div'); el.className = 'ak ak-' + who;
    el.style.left = (o.x ?? 640) + 'px'; el.style.top = (o.y ?? 640) + 'px'; if (o.z != null) el.style.zIndex = o.z;
    el.innerHTML = `<div class="ak-shadow"></div><div class="ak-m"><div class="ak-t"><canvas class="ak-gl"></canvas><canvas class="ak-fx"></canvas></div></div>`;
    (typeof host === 'string' ? document.querySelector(host) : host).appendChild(el);
    const a = { el, who, d, m: el.querySelector('.ak-m'), tw: el.querySelector('.ak-t'), cv: el.querySelector('.ak-gl'), fxc: el.querySelector('.ak-fx'),
      h: o.h ?? 400, flip: !!o.flip, seed: o.seed ?? hash(live.length + 1) , sub: o.sub ?? d.sub, animName: o.anim || 'idle', animT: 0, layers: [], accents: [],
      gleamTop: 0, magicOn: 0, dir: o.flip ? -1 : 1, visible: true };
    a.sh = el.querySelector('.ak-shadow');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    a.size = (key) => { const r = RIG[key]; const hh = a.h / ((r.feet - r.head.top) || 1); const w = hh * (r.w / r.h); return { W: w * (1 + 2 * PAD), H: hh * (1 + 2 * PAD), w, hh }; };
    a.place = () => { const r = RIG[a.key]; const { W, H, hh } = a.size(a.key); const cx = r.head.cx; // feet point = (head column x, feet v)
      const left = -(PAD * W / (1 + 2 * PAD) + (a.flip ? 1 - cx : cx) * (W / (1 + 2 * PAD))), top = -(PAD * H / (1 + 2 * PAD) + r.feet * hh);
      [a.cv, a.fxc].forEach((c) => { c.style.left = left + 'px'; c.style.top = top + 'px'; c.style.width = W + 'px'; c.style.height = H + 'px'; });
      if (a.cv.width !== Math.round(W * dpr)) { a.cv.width = a.fxc.width = Math.round(W * dpr); a.cv.height = a.fxc.height = Math.round(H * dpr); }
      a.sh.style.width = W * 0.55 + 'px'; a.sh.style.height = W * 0.09 + 'px'; a.box = { left, top, W, H, hh, w: W / (1 + 2 * PAD) }; };
    a.g = makeGL(a.cv); a.ctx = a.fxc.getContext('2d');
    a.setPose = async (p) => { const key = d.poses[p] || d.poses.stand || Object.values(d.poses)[0]; a.poseName = p; a.key = key; a.img = await loadImg(base + key + '.png'); a.place(); a.draw(window.Music ? Music.time() : 0); };
    a.ready = a.setPose(o.pose || Object.keys(d.poses)[0]);
    /** play(name | [names], {mix}) — layered: base idle + named loop (or several mixed). */
    a.play = (name, opt = {}) => { a.animName = name; a.animT = window.Music ? Music.time() : 0; if (opt.dir) a.dir = opt.dir; return a; };
    a.draw = (t) => draw(a, t);
    a.kill = () => { const ext = a.g.gl.getExtension('WEBGL_lose_context'); ext && ext.loseContext(); live = live.filter((x) => x !== a); el.remove(); };
    live.push(a); return a;
  };

  function params(a, t) {
    const bp = beatPos(t); const sub = a.sub || 1;
    const k = { t, b: bp.b * sub, bar: bp.inBar, e: bp.energy, s: a.seed, d: { ...a.d, dir: a.dir }, age: t - a.animT };
    // own phase, quantized to 16ths so every actor still lands on the grid (on the beat, the 'and', the 'e', the 'a')
    k.ph = ((k.b + Math.round(a.seed * 4) / 4) % 1 + 1) % 1;
    k.b = bp.b * sub; k.b += 0; // continuous
    const P = { breath: 0, headX: 0, headY: 0, headRot: 0, armL: 0, armR: 0, lean: 0, sway: 1, swayFreq: 1, flare: 0, hair: a.d.hair ? 1 : 0, rock: 0, bobY: 0, jitter: 0, eyes: 0, gleam: 0, magic: 0, wing: 0, hairBoost: 1 };
    const add = (o, w = 1) => Object.entries(o).forEach(([kk, v]) => { if (kk === 'sway' || kk === 'swayFreq' || kk === 'hairBoost') P[kk] = Math.max(P[kk], v); else P[kk] += v * w; });
    add(LIB.idle(k));
    const names = Array.isArray(a.animName) ? a.animName : [a.animName];
    names.forEach((n) => n !== 'idle' && LIB[n] && add(LIB[n](k)));
    a.accents = a.accents.filter((x) => t - x.t < x.dur); a.accents.forEach((x) => add(x.fn((t - x.t) / x.dur, k)));
    P.headRot *= a.d.headScale ?? 1; P.headY *= a.d.headScale ?? 1;
    P.swayPh = TAU * (t * 0.55 * P.swayFreq + a.seed); P.hairPh = TAU * (t * 0.45 * P.hairBoost + a.seed * 2);
    P.hair *= P.hairBoost; P.sway *= a.d.sway;
    if (P.jitter) { P.headX += (hash(Math.floor(t * 30) + a.seed) - 0.5) * 0.004 * P.jitter; P.rock += (hash(Math.floor(t * 30) * 1.7) - 0.5) * P.jitter * 0.6; }
    if (a.d.gleamTop?.[a.poseName] && bp.inBar % 4 < 0.6) P.gleam = Math.max(P.gleam, 1); // blade gleam once a bar
    P.pulse = pulse(k.ph, 4); P.k = k;
    return P;
  }

  function draw(a, t) {
    if (!a.img || !a.el.isConnected) return;
    const r = RIG[a.key]; const P = params(a, t); const { gl, U, texFor } = a.g; a.P = P;
    gl.viewport(0, 0, a.cv.width, a.cv.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.bindTexture(gl.TEXTURE_2D, texFor(a.img));
    const f = (n, v) => gl.uniform1f(U[n], v);
    gl.uniform2f(U.uAsp, r.w, r.h); f('uNeck', r.head.neck); f('uHip', r.hip); f('uFeet', r.feet); f('uTop', r.head.top); f('uCx', r.head.cx);
    const ar = r.w / r.h; const headR = Math.max(0.03, (r.ears && r.ears.length >= 2 ? Math.abs(r.ears[r.ears.length - 1][0] - r.ears[0][0]) / 2 : 0.08) * ar);
    f('uHeadR', a.d.headR ?? headR); f('uBodyW', (a.d.bodyW ?? r.bodyW) * ar); f('uSh', r.shoulders);
    gl.uniform3f(U.uHead, P.headX, P.headY, P.headRot); f('uBreath', P.breath); f('uArmL', P.armL * (a.d.arms ?? 1)); f('uArmR', P.armR * (a.d.arms ?? 1));
    f('uLean', P.lean * (a.flip ? -1 : 1)); f('uSway', P.sway); f('uSwayPh', P.swayPh); f('uSwayFreq', P.swayFreq); f('uFlare', P.flare); f('uHair', P.hair); f('uHairPh', P.hairPh);
    f('uRock', P.rock * (a.flip ? -1 : 1)); f('uFlip', a.flip ? 1 : 0); f('uWing', P.wing * (a.d.wings ? 1 : 0)); f('uPad', PAD); gl.uniform1i(U.uTex, 0);
    // chrome glint: sweeps across every few bars per actor (offset), plus attack gleams
    const gl8 = ((P.k.b / (a.sub || 1)) / 8 + a.seed) % 1; const sweep = gl8 < 0.14 ? gl8 / 0.14 : -1;
    f('uGleam', Math.max(sweep >= 0 ? 0.55 : 0, P.gleam)); f('uGleamPos', P.gleam ? ((t * 1.6) % 1) * 2.2 - 0.3 : sweep * 2.2 - 0.3); f('uGleamTop', P.gleam ? (a.d.gleamTop?.[a.poseName] || 0) : 0);
    f('uFlash', a.flash || 0); f('uRim', (a.d.rim ?? 0.5) * P.pulse * (window.Music ? 0.5 + Music.energyAt(t) : 1));
    gl.drawElements(gl.TRIANGLES, MESH.i.length, gl.UNSIGNED_SHORT, 0);
    // DOM-level body motion (bob/jitter); GSAP owns the inner .ak-t for hops, squash, smears
    a.m.style.transform = `translate(0px,${P.bobY.toFixed(2)}px)`;
    a.sh.style.transform = `translate(-50%,-50%) scale(${(1 + P.bobY / 120).toFixed(3)})`;
    lights(a, r, P, t);
  }

  /* ---------- light overlay: eyes, headphones, magic ---------- */
  function lights(a, r, P, t) {
    const c = a.ctx, Wc = a.fxc.width, Hc = a.fxc.height; c.clearRect(0, 0, Wc, Hc);
    const ar = r.w / r.h, s = 1 + 2 * PAD;
    const toPx = ([u, v]) => { let x = (u + PAD) / s; if (a.flip) x = 1 - x; return [x * Wc, ((v + PAD) / s) * Hc]; };
    const unit = Hc / s; // px per image height
    // blink: per-actor deterministic schedule (every 2.4-5.5 s, 0.14 s long), skip when eyes overridden closed
    const per = 2.4 + 3.1 * hash(a.seed * 9.1); const slot = Math.floor((t + a.seed * per) / per); const inSlot = (t + a.seed * per) - slot * per;
    const blink = inSlot < 0.14 && hash(slot + a.seed * 31) > 0.15 ? 1 - Math.sin((Math.PI * inSlot) / 0.14) : 1;
    const lvl = clamp((0.7 + 0.3 * Math.sin(TAU * (t / 1.7 + a.seed)) + 0.6 * P.eyes) * blink, 0, 1.8);
    c.globalCompositeOperation = 'lighter';
    (r.eyes || []).forEach((e) => {
      const [x, y] = toPx(headPoint(r, P, e[0], e[1], ar)); const rad = unit * (a.d.eyeR ?? 0.014) * (0.7 + 0.35 * lvl);
      if (lvl < 0.3) { c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgba(40,40,55,.9)'; c.beginPath(); c.ellipse(x, y, rad * 0.55, rad * 0.22 * (0.3 + lvl), 0, 0, TAU); c.fill(); c.globalCompositeOperation = 'lighter'; return; }
      const g = c.createRadialGradient(x, y, 0, x, y, rad * 2); g.addColorStop(0, `rgba(255,235,220,${0.45 * lvl})`); g.addColorStop(0.3, `rgba(255,40,30,${0.32 * lvl})`); g.addColorStop(1, 'rgba(255,0,0,0)');
      c.fillStyle = g; c.beginPath(); c.arc(x, y, rad * 2, 0, TAU); c.fill();
      if (P.eyes > 0.6) { c.strokeStyle = `rgba(255,80,60,${0.35 * (P.eyes - 0.6)})`; c.lineWidth = unit * 0.004; c.beginPath(); c.moveTo(x - rad * 4, y); c.lineTo(x + rad * 4, y); c.stroke(); }
    });
    // headphones: ring pulse on the actor's own beat
    const hp = P.pulse; (r.ears || []).forEach((e, i) => {
      const [x, y] = toPx(headPoint(r, P, e[0], e[1], ar)); const rad = unit * 0.022 * (1 + 0.4 * hp);
      const col = i % 2 ? a.d.phones2 || '#ff3fd2' : a.d.phones;
      const g = c.createRadialGradient(x, y, rad * 0.2, x, y, rad * 1.5); g.addColorStop(0, hexA(col, 0.38 * hp + 0.06)); g.addColorStop(1, hexA(col, 0));
      c.fillStyle = g; c.beginPath(); c.arc(x, y, rad * 1.5, 0, TAU); c.fill();
    });
    // extra light sources (wizard/villain orbs) breathe
    Object.entries(r.glow || {}).forEach(([k, g]) => {
      if (k === 'gold' || (k === 'magic' && !(P.magic || a.d.magicAlways))) return;
      const [x, y] = toPx(g); const isMagic = k === 'magic'; const col = isMagic ? '#5ee7ff' : a.d.orb || '#ff3030';
      const rad = unit * (isMagic ? 0.09 : 0.045) * (1 + 0.25 * Math.sin(TAU * (t / 1.3 + a.seed)) + 0.3 * P.pulse);
      const gr = c.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, hexA('#ffffff', 0.5)); gr.addColorStop(0.3, hexA(col, 0.45)); gr.addColorStop(1, hexA(col, 0));
      c.fillStyle = gr; c.beginPath(); c.arc(x, y, rad, 0, TAU); c.fill();
      if (isMagic) for (let i = 0; i < 40; i++) { // stateless spiral particles
        const life = 1.4, born = Math.floor((t - i * 0.035) / life) * life + i * 0.035, age = (t - born) / life; if (age < 0 || age > 1) continue;
        const ang = TAU * hash(i * 3.3 + Math.floor(born)) + age * 5, R = rad * (0.3 + age * 1.6);
        const px = x + Math.cos(ang) * R, py = y + Math.sin(ang) * R * 0.8 - age * unit * 0.12, sz = unit * 0.006 * (1 - age) + 1;
        c.fillStyle = i % 3 ? `rgba(120,250,255,${1 - age})` : `rgba(255,120,240,${1 - age})`; c.beginPath(); c.arc(px, py, sz, 0, TAU); c.fill();
      }
    });
    c.globalCompositeOperation = 'source-over';
  }
  const hexA = (h, al) => { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${clamp(al, 0, 1)})`; };

  /* ---------- frame loop: driven by the song clock ---------- */
  let hooked = false;
  A.tick = (t) => live.forEach((a) => a.draw(t));
  A.start = () => { if (hooked || !window.Music) return; hooked = true; Music.onFrame((t) => A.tick(t)); };
  /** Drop every actor inside root (call on scene enter). */
  A.clear = (root) => live.filter((a) => !root || root.contains(a.el)).forEach((a) => a.kill());

  /* ---------- pose transitions, accents and comic marks ---------- */
  /** Pose change with anticipation -> smear -> overshoot. dir: 'up'|'left'|'right'|'spin'|'none'. */
  A.transition = (a, pose, { smear = 'up', beats = 0.5, lines = true } = {}) => {
    const tl = gsap.timeline();
    const ghost = document.createElement('canvas'); ghost.className = 'ak-ghost'; ghost.width = a.cv.width; ghost.height = a.cv.height;
    Object.assign(ghost.style, { left: a.cv.style.left, top: a.cv.style.top, width: a.cv.style.width, height: a.cv.style.height });
    try { ghost.getContext('2d').drawImage(a.cv, 0, 0); } catch (e) {}
    a.tw.appendChild(ghost);
    const sx = smear === 'left' ? -1 : smear === 'right' ? 1 : 0, up = smear === 'up' ? 1 : 0;
    tl.to(a.tw, { scaleY: 0.9, scaleX: 1.06, duration: B(beats * 0.3), ease: 'power2.in', transformOrigin: '0 0' }) // anticipation squat
      .add(() => { a.setPose(pose); if (lines && smear !== 'none') A.speedLines(a, smear); })
      .fromTo(ghost, { opacity: 0.75 }, { opacity: 0, x: sx * 60, y: up * -50, scaleY: up ? 1.25 : 1, scaleX: sx ? 1.3 : 1, duration: B(beats * 0.6), ease: 'power2.out', onComplete: () => ghost.remove() }, '<')
      .fromTo(a.tw, { scaleY: up ? 1.14 : 0.96, scaleX: up ? 0.92 : 1.1, rotation: sx * -6 + (smear === 'spin' ? -25 : 0) }, { scaleY: 1, scaleX: 1, rotation: 0, duration: B(beats * 1.2), ease: 'elastic.out(1.1,.45)' }, '<');
    return tl;
  };
  /** Short additive pose accents layered over the loop: flare (eyes), recoil, nod, jump. */
  const ACC = {
    flare: (p) => ({ eyes: 1.6 * (1 - p) }),
    recoil: (p) => ({ lean: -8 * Math.sin(Math.PI * p), headRot: -6 * Math.sin(Math.PI * p), eyes: 1 * (1 - p) }),
    nod: (p) => ({ headY: 0.02 * Math.sin(Math.PI * p), headRot: 3 * Math.sin(Math.PI * p) }),
    flex: (p) => ({ armL: -10 * Math.sin(Math.PI * p), armR: 10 * Math.sin(Math.PI * p), breath: 0.03 * Math.sin(Math.PI * p), eyes: (1 - p) }),
    shiver: (p) => ({ jitter: 6 * (1 - p) }),
  };
  A.accent = (a, name, beats = 1) => { a.accents.push({ t: window.Music ? Music.time() : 0, dur: B(beats), fn: ACC[name] }); if (name === 'flare') { a.flash = 0; } return a; };
  A.hop = (a, px = 40, beats = 0.6) => gsap.timeline()
    .to(a.tw, { scaleY: 0.88, scaleX: 1.08, duration: B(beats * 0.15), transformOrigin: '0 0' })
    .to(a.tw, { y: -px, scaleY: 1.1, scaleX: 0.93, duration: B(beats * 0.4), ease: 'power2.out' })
    .to(a.tw, { y: 0, scaleY: 1, scaleX: 1, duration: B(beats * 0.35), ease: 'power2.in' })
    .to(a.tw, { scaleY: 0.9, scaleX: 1.08, duration: B(0.08) }).to(a.tw, { scaleY: 1, scaleX: 1, duration: B(0.4), ease: 'elastic.out(1,.4)' });
  A.flash = (a, beats = 0.5) => gsap.fromTo(a, { flash: 0.85 }, { flash: 0, duration: B(beats), ease: 'power2.out' });
  A.speedLines = (a, dir = 'up', n = 7) => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'ak-lines');
    const { left, top, W, H } = a.box; Object.assign(s.style, { left: left + 'px', top: top + 'px', width: W + 'px', height: H + 'px' });
    let html = ''; for (let i = 0; i < n; i++) { const x = W * (0.25 + 0.5 * hash(i + a.seed * 7)), y = H * (0.2 + 0.6 * hash(i * 2.1 + a.seed));
      const L = 60 + 80 * hash(i * 5.3); const [dx, dy] = dir === 'left' ? [L, 0] : dir === 'right' ? [-L, 0] : [0, L];
      html += `<line x1="${x}" y1="${y}" x2="${x + dx}" y2="${y + dy}" stroke="${i % 2 ? '#fff' : '#5ee7ff'}" stroke-width="${3 + (i % 3)}" stroke-linecap="round"/>`; }
    s.innerHTML = html; a.tw.appendChild(s);
    gsap.fromTo(s, { opacity: 1 }, { opacity: 0, duration: B(0.7), ease: 'power1.in', onComplete: () => s.remove() });
    gsap.to(s.children, { y: dir === 'up' ? 40 : 0, x: dir === 'left' ? 40 : dir === 'right' ? -40 : 0, duration: B(0.7) });
  };
  /** Comic impact star (+ optional lettering via Music.comic.sfx) at an actor's chest or a point. */
  A.impact = (host, x, y, { color = '#ffe14d', size = 160, text, rot = -8 } = {}) => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'ak-star'); s.setAttribute('viewBox', '-100 -100 200 200');
    Object.assign(s.style, { left: x - size / 2 + 'px', top: y - size / 2 + 'px', width: size + 'px', height: size + 'px', zIndex: 30 });
    const pts = []; for (let i = 0; i < 24; i++) { const R = i % 2 ? 46 : 96 - (i % 4) * 12; const an = (i / 24) * TAU; pts.push(`${(Math.cos(an) * R).toFixed(1)},${(Math.sin(an) * R).toFixed(1)}`); }
    s.innerHTML = `<polygon points="${pts.join(' ')}" fill="${color}" stroke="#1b1030" stroke-width="7" stroke-linejoin="round"/><polygon points="${pts.join(' ')}" fill="#fff" transform="scale(.45)" opacity=".85"/>`;
    (typeof host === 'string' ? document.querySelector(host) : host).appendChild(s);
    gsap.timeline({ onComplete: () => s.remove() }).fromTo(s, { scale: 0.2, rotation: rot - 30 }, { scale: 1, rotation: rot, duration: B(0.25), ease: 'back.out(3)' }).to(s, { scale: 1.1, opacity: 0, duration: B(1.2), ease: 'power1.in' }, '+=' + B(0.5));
    if (text && window.Music) { const t = Music.comic.sfx(host, text, { x, y, size: size * 0.42, rot, beat: false }); gsap.to(t, { autoAlpha: 0, scale: 1.2, duration: B(0.6), delay: B(2.2), onComplete: () => t.remove() }); }
    return s;
  };
  /** Screen point of an actor's chest/head (host coordinates) for attaching accents. */
  A.anchor = (a, part = 'chest') => { const r = RIG[a.key]; const x = parseFloat(a.el.style.left), y = parseFloat(a.el.style.top);
    const v = part === 'head' ? r.head.top + 0.05 : part === 'feet' ? r.feet : (r.head.neck + r.hip) / 2; return [x, y - (r.feet - v) * a.box.hh]; };

  /* ---------- animated backgrounds ----------
     Actors.bg(plateEl, name, {glow:[keys], pulse:'beat'|'bar', shimmer:[keys], twinkle:[keys], lasers:[...], disco:{x,y}, eyes:[[x,y]], fountain:{x,y}})
     Coordinates are in source-image px (scripts/bg_lightmap.py writes <name>.fx.json + glow maps). */
  A.bg = async (plate, name, o = {}) => {
    const fx = await (await fetch(`assets/bg/bg-${name}.fx.json`)).json(); const [IW, IH] = fx.size;
    plate.style.position = 'absolute'; plate.style.overflow = 'hidden';
    plate.innerHTML = `<img src="assets/bg/bg-${name}.jpg" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">`;
    const pct = (x, y) => [(x / IW) * 100 + '%', (y / IH) * 100 + '%'];
    const els = { glow: [], tw: [], lasers: [], eyes: [], disco: null, fountain: null };
    (o.glow || []).forEach((k, i) => { const g = document.createElement('img'); g.src = `assets/bg/${fx.glow[k].file}`; g.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;mix-blend-mode:screen;opacity:0;pointer-events:none';
      if ((o.shimmer || []).includes(k)) g.style.webkitMaskImage = g.style.maskImage = 'linear-gradient(100deg,rgba(0,0,0,.25) 0%,#000 45%,#000 55%,rgba(0,0,0,.25) 100%)', g.style.maskSize = g.style.webkitMaskSize = '300% 100%';
      plate.appendChild(g); els.glow.push({ k, g, i }); });
    (o.twinkle || []).forEach((k) => (fx.points[k] || []).slice(0, o.twinkleN || 26).forEach(([x, y], i) => { const s = document.createElement('div'); const [l, t] = pct(x, y);
      s.style.cssText = `position:absolute;left:${l};top:${t};width:34px;height:34px;margin:-17px;pointer-events:none;mix-blend-mode:screen;background:radial-gradient(#fff 0,rgba(255,255,255,.6) 8%,rgba(160,240,255,0) 40%),linear-gradient(90deg,transparent 46%,#fff 50%,transparent 54%),linear-gradient(0deg,transparent 46%,#fff 50%,transparent 54%);opacity:0`;
      plate.appendChild(s); els.tw.push({ s, seed: hash(i + x) }); }));
    (o.lasers || []).forEach((L, i) => { const d = document.createElement('div'); const [l, t] = pct(L.x, L.y);
      d.style.cssText = `position:absolute;left:${l};top:${t};width:14px;height:${L.len || 1400}px;margin-left:-7px;transform-origin:50% 0;pointer-events:none;mix-blend-mode:screen;background:linear-gradient(${L.color || '#5ee7ff'},rgba(0,0,0,0));filter:blur(2px)`;
      plate.appendChild(d); els.lasers.push({ d, L, i }); });
    if (o.disco) { const d = document.createElement('div'); const [l, t] = pct(o.disco.x, o.disco.y);
      d.style.cssText = `position:absolute;left:${l};top:${t};width:${o.disco.r || 70}px;height:${o.disco.r || 70}px;margin:-${(o.disco.r || 70) / 2}px;border-radius:50%;pointer-events:none;background:repeating-conic-gradient(#e8e8ff 0 10deg,#7a6aa8 10deg 20deg),#ccc;box-shadow:0 0 30px #b28cff,0 0 70px rgba(94,231,255,.6);overflow:hidden`;
      d.innerHTML = '<i style="position:absolute;inset:0;border-radius:50%;background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.9),rgba(255,255,255,0) 35%),radial-gradient(circle at 50% 50%,rgba(0,0,0,0) 55%,rgba(20,0,40,.6))"></i>';
      plate.appendChild(d); els.disco = d;
      const spots = document.createElement('div'); spots.style.cssText = 'position:absolute;inset:0;pointer-events:none;mix-blend-mode:screen'; plate.appendChild(spots); els.spots = spots;
      for (let i = 0; i < 26; i++) { const s = document.createElement('i'); s.style.cssText = `position:absolute;width:16px;height:9px;border-radius:50%;background:${i % 3 ? '#9ff6ff' : '#ff8cf0'};filter:blur(1px);opacity:.8`; spots.appendChild(s); } }
    (o.eyes || []).forEach(([x, y]) => { const e = document.createElement('div'); const [l, t] = pct(x, y);
      e.style.cssText = `position:absolute;left:${l};top:${t};width:140px;height:140px;margin:-70px;border-radius:50%;pointer-events:none;mix-blend-mode:screen;background:radial-gradient(#fff2c0 0,#ff3a1a 12%,rgba(255,20,0,.35) 30%,rgba(255,0,0,0) 65%)`;
      plate.appendChild(e); els.eyes.push(e); });
    if (o.fountain) { const f = document.createElement('div'); const [l, t] = pct(o.fountain.x, o.fountain.y);
      f.style.cssText = `position:absolute;left:${l};top:${t};width:${o.fountain.w || 220}px;height:${o.fountain.h || 260}px;transform:translate(-50%,-100%);pointer-events:none;mix-blend-mode:screen;overflow:hidden`;
      for (let i = 0; i < 18; i++) { const d = document.createElement('i'); d.style.cssText = `position:absolute;left:${10 + 80 * hash(i)}%;bottom:0;width:3px;height:40px;border-radius:2px;background:linear-gradient(rgba(180,255,255,0),#bffcff);`; f.appendChild(d); }
      plate.appendChild(f); els.fountain = f; }
    const frame = (t) => { if (!plate.isConnected) return;
      const bp = beatPos(t); const ph = bp.b % 1, pl = Math.exp(-4 * ph), bar = Math.exp(-2.2 * (bp.inBar % 4) / 1);
      els.glow.forEach(({ k, g, i }) => { const base = (o.base ?? 0.35) + 0.15 * Math.sin(TAU * (t / 3.3 + i * 0.37));
        const hit = o.pulse === 'bar' ? bar : o.pulse === 'none' ? 0 : pl; g.style.opacity = clamp(base + (o.amount ?? 0.45) * hit, 0, 1).toFixed(3);
        if (g.style.maskImage) g.style.maskPosition = g.style.webkitMaskPosition = `${(100 - ((t * 18 + i * 40) % 160)).toFixed(1)}% 0`; });
      els.tw.forEach(({ s, seed }) => { const p = ((t / (1.6 + seed * 2.2) + seed) % 1); const v = p < 0.18 ? Math.sin((Math.PI * p) / 0.18) : 0; s.style.opacity = v.toFixed(3); s.style.transform = `scale(${(0.4 + v).toFixed(2)}) rotate(${(t * 40 + seed * 90).toFixed(1)}deg)`; });
      els.lasers.forEach(({ d, L, i }) => { const a = (L.from ?? -30) + ((L.to ?? 30) - (L.from ?? -30)) * (0.5 + 0.5 * Math.sin(TAU * (bp.b / (L.beats || 8)) + (L.phase ?? i))); d.style.transform = `rotate(${a.toFixed(2)}deg)`; d.style.opacity = (0.45 + 0.55 * pl).toFixed(3); });
      if (els.disco) { els.disco.style.backgroundPosition = '0 0'; els.disco.style.transform = `rotate(${(t * 60) % 360}deg)`; els.disco.style.filter = `brightness(${(1 + 0.6 * pl).toFixed(2)})`;
        [...els.spots.children].forEach((s, i) => { const an = TAU * (i / 26) + t * 0.9, rr = 0.25 + 0.2 * hash(i); s.style.left = (50 + Math.cos(an) * rr * 100).toFixed(2) + '%'; s.style.top = (62 + Math.sin(an) * rr * 40).toFixed(2) + '%'; s.style.opacity = (0.35 + 0.6 * pl * hash(i + 3)).toFixed(2); }); }
      els.eyes.forEach((e) => { const fl = o.eyesFlare ? o.eyesFlare(t, bp) : (bp.inBar % 4 < 0.2 ? 1 : 0.3 + 0.3 * Math.exp(-3 * (bp.inBar % 4))); e.style.opacity = clamp(0.25 + 0.75 * fl, 0, 1).toFixed(3); e.style.transform = `scale(${(0.7 + 0.6 * fl).toFixed(2)})`; });
      if (els.fountain) [...els.fountain.children].forEach((d, i) => { const p = ((t * 0.9 + hash(i)) % 1); d.style.transform = `translateY(${(-p * 220).toFixed(1)}px) translateX(${((hash(i * 3) - 0.5) * p * 120).toFixed(1)}px)`; d.style.opacity = (Math.sin(Math.PI * p) * 0.8).toFixed(2); });
    };
    if (plate._off) plate._off(); if (window.Music) plate._off = Music.onFrame(frame); frame(window.Music ? Music.time() : 0);
    return els;
  };
})();

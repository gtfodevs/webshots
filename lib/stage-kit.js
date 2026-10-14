/* Webshot stage kit: the small contract between a stage page and the recorder.
 *
 * A stage is one 1280x720 HTML page. Each scene is a <section class="scene" id="s-NAME">
 * and is registered with:
 *
 *   Webshot.scene('NAME', (tl, el, idle) => {
 *     tl.from(el.querySelector('h2'), { y: -40, autoAlpha: 0, duration: 0.6, ease: 'back.out(2)' });
 *     idle(() => gsap.to('#cloud', { y: '-=12', yoyo: true, repeat: -1, duration: 0.8 }));
 *   });
 *   Webshot.start();
 *
 * - `tl` is a GSAP timeline that already crossfades from the previous scene.
 *   Add the scene's entrance to it; the recorder waits for it to finish.
 * - `idle(fn)` registers a looping animation. It starts AFTER the entrance
 *   (so it never fights an entrance tween) and stops when the next scene starts.
 *   Use relative moves (y: '-=12'), never absolute ones, so positions survive.
 * - Position SVG things with a static <g transform="translate(...)"> and animate
 *   an inner <g> that has no transform attribute.
 *
 * Scene changes (varied transitions, the default for narrated explainers):
 * every scene change gets a transition from TRANSITIONS, picked in a fixed
 * rotation so no two consecutive changes share a type (deterministic, so check
 * and render match). Override per scene with Webshot.scene(name, build, { transition: 'iris' })
 * or globally with Webshot.transitions('varied' | 'fade' | 'none' | ['wipe', 'iris']).
 * Music stages (window.Music present) keep the plain 0.35 s fade unless they opt in
 * with Webshot.transitions('varied'). Custom stages that build their own timelines can
 * call Webshot.transition(tl, fromEl, toEl, type?) to get the same effects.
 *
 * The recorder calls window.scene(name) (returns a Promise) once
 * document.body.dataset.ready === '1' (set by Webshot.start() after fonts load).
 */
(() => {
  const defs = new Map();
  const opts = new Map();
  let current = null;
  let idles = [];

  // Varied scene transitions. Order is a fixed rotation chosen so neighbours differ
  // in family (slide / mask / scale / fade); never the same type twice in a row.
  const TRANSITIONS = ['slide_left', 'iris', 'zoom_pop', 'wipe', 'slide_up', 'whip', 'fade', 'slide_right'];
  const DUR = 0.45;
  let mode = null; // null = auto (varied, or 'fade' on music stages)
  let turn = 0;
  let last = null;

  function pick(override) {
    if (override) return override;
    const m = mode ?? (window.Music ? 'fade' : 'varied');
    if (m === 'none') return 'cut';
    if (m === 'fade') return 'fade';
    const list = Array.isArray(m) ? m : TRANSITIONS;
    let t = list[turn % list.length];
    turn += 1;
    if (t === last && list.length > 1) { t = list[turn % list.length]; turn += 1; }
    return t;
  }

  /** Add a scene change from `from` to `to` onto `tl`. Returns the type used. */
  function transition(tl, from, to, type) {
    const clear = 'transform,clipPath,filter,zIndex';
    if (!from || from === to) { tl.set(to, { autoAlpha: 1 }); return 'none'; }
    const t = pick(type);
    last = t;
    if (t === 'cut') {
      if (from && from !== to) tl.set(from, { autoAlpha: 0 });
      tl.set(to, { autoAlpha: 1 });
      return t;
    }
    if (t === 'fade') {
      tl.to(from, { autoAlpha: 0, duration: 0.35, ease: 'power1.in' });
      tl.set(to, { autoAlpha: 1 });
      return t;
    }
    const d = DUR;
    const slide = { slide_left: ['-100%', '100%', 'x'], slide_right: ['100%', '-100%', 'x'], slide_up: ['-100%', '100%', 'y'], whip: ['-100%', '100%', 'x'] }[t];
    tl.set(to, { autoAlpha: 1, zIndex: 2 });
    tl.set(from, { zIndex: 1 });
    if (slide) {
      const [outTo, inFrom, axis] = slide;
      const ease = t === 'whip' ? 'power3.inOut' : 'power2.inOut';
      tl.fromTo(to, { [axis + 'Percent']: parseFloat(inFrom) }, { [axis + 'Percent']: 0, duration: d, ease }, '<');
      tl.to(from, { [axis + 'Percent']: parseFloat(outTo), duration: d, ease }, '<');
      if (t === 'whip') {
        tl.fromTo([to, from], { filter: 'blur(0px)' }, { filter: 'blur(14px)', duration: d / 2, yoyo: true, repeat: 1, ease: 'power1.in' }, '<');
      }
    } else if (t === 'iris') {
      tl.fromTo(to, { clipPath: 'circle(0% at 50% 50%)' }, { clipPath: 'circle(75% at 50% 50%)', duration: d, ease: 'power2.inOut' }, '<');
    } else if (t === 'wipe') {
      tl.fromTo(to, { clipPath: 'inset(0% 100% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: d, ease: 'power2.inOut' }, '<');
    } else { // zoom_pop
      tl.fromTo(to, { scale: 0.82, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: d, ease: 'back.out(1.6)' }, '<');
      tl.to(from, { autoAlpha: 0, duration: d * 0.8, ease: 'power1.in' }, '<');
    }
    tl.set(from, { autoAlpha: 0, clearProps: clear });
    tl.set(to, { clearProps: clear });
    return t;
  }

  function stopIdles() {
    idles.forEach((t) => t && t.kill && t.kill());
    idles = [];
  }

  function play(name) {
    const build = defs.get(name);
    const el = document.getElementById('s-' + name);
    if (!build || !el) return Promise.reject(new Error(`unknown scene "${name}"`));
    stopIdles();
    const tl = gsap.timeline();
    const used = transition(tl, current, el, (opts.get(name) || {}).transition);
    el.dataset.transition = used;
    current = el;
    const pending = [];
    build(tl, el, (fn) => pending.push(fn));
    tl.add(() => { idles = pending.map((fn) => fn()); });
    return new Promise((resolve) => tl.eventCallback('onComplete', resolve));
  }

  const NS = 'http://www.w3.org/2000/svg';

  window.Webshot = {
    scene(name, build, o) { defs.set(name, build); if (o) opts.set(name, o); },
    /** 'varied' (default for explainers) | 'fade' | 'none' | [types] */
    transitions(m) { mode = m; turn = 0; last = null; },
    transition,
    TRANSITIONS,
    /** Create an SVG element: Webshot.svg('circle', { cx: 10, cy: 10, r: 5 }, parent) */
    svg(tag, attrs = {}, parent) {
      const node = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      if (parent) parent.appendChild(node);
      return node;
    },
    start() {
      ['DrawSVGPlugin', 'MotionPathPlugin', 'MorphSVGPlugin', 'TextPlugin', 'SplitText']
        .forEach((p) => window[p] && gsap.registerPlugin(window[p]));
      const fonts = document.fonts ? document.fonts.ready : Promise.resolve();
      fonts.then(() => { document.body.dataset.ready = '1'; });
    },
  };
  window.scene = play;
  // A stage with its own scene table may assign window.sceneNames; the getter is the default.
  let names = null;
  Object.defineProperty(window, 'sceneNames', { configurable: true, get: () => names || [...defs.keys()], set: (v) => { names = v; } });
})();

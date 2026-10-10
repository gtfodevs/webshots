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
 * The recorder calls window.scene(name) (returns a Promise) once
 * document.body.dataset.ready === '1' (set by Webshot.start() after fonts load).
 */
(() => {
  const defs = new Map();
  let current = null;
  let idles = [];

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
    if (current && current !== el) tl.to(current, { autoAlpha: 0, duration: 0.35, ease: 'power1.in' });
    tl.set(el, { autoAlpha: 1 });
    current = el;
    const pending = [];
    build(tl, el, (fn) => pending.push(fn));
    tl.add(() => { idles = pending.map((fn) => fn()); });
    return new Promise((resolve) => tl.eventCallback('onComplete', resolve));
  }

  const NS = 'http://www.w3.org/2000/svg';

  window.Webshot = {
    scene(name, build) { defs.set(name, build); },
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
  Object.defineProperty(window, 'sceneNames', { get: () => [...defs.keys()] });
})();

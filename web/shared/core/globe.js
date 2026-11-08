// The 3-D atlas view, shared by Live and Score: the real embeddings (a thin sample, saved with the atlas) in the colour of their cluster,
// on a sphere you drag to rotate (or switch Rotate on: it turns slowly about three axes at once, at rates that never line up, so the view
// never repeats). What each page adds on top is its `overlay(g, project, T)`: project(p) -> [x, y, depth] of a 3-D point.
import {ref} from './state.js';
import {header} from './ui.js';

// mountGlobe(root, ctx, {title, key, cloud: () => [[x, y, z]], labels: () => [cluster], overlay}) -> {draw}
export function mountGlobe(root, ctx, {title = 'Atlas', key = title, cloud, labels, overlay}) {
  const T = ctx.theme;
  const PX = ctx.size, HALF = PX / 2, R = HALF - 20;      // the canvas: its size is CANVAS in theme.js
  root.innerHTML = header(title, key) + `<canvas data-ref="canvas" width="${PX}" height="${PX}"></canvas>`;
  ref(root, 'tools').innerHTML = `<button data-ref="rotate" title="rotate slowly by itself">Rotate</button>`;
  const vc = ref(root, 'canvas');
  const view = {yaw: 0.6, pitch: -0.35, roll: 0, drag: null, auto: false};
  const RATES = {yaw: 0.31, pitch: 0.113, roll: 0.071};     // rad/s of the automatic rotation: unrelated, so it never repeats

  // orthographic projection with depth kept for the drawing order
  function project(p) {
    const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw), cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
    const x1 = p[0] * cy + p[2] * sy, z1 = -p[0] * sy + p[2] * cy;
    const y2 = p[1] * cp - z1 * sp, z2 = p[1] * sp + z1 * cp;
    const cr = Math.cos(view.roll), sr = Math.sin(view.roll);                 // roll: turn about the line of sight
    return [HALF + (x1 * cr - y2 * sr) * R, HALF - (x1 * sr + y2 * cr) * R, z2];
  }

  function draw() {
    const g = vc.getContext('2d');
    g.fillStyle = T.bg; g.fillRect(0, 0, PX, PX);
    g.strokeStyle = T.panel;
    const rings = [(t) => [Math.cos(t), Math.sin(t), 0], (t) => [Math.cos(t), 0, Math.sin(t)], (t) => [0, Math.cos(t), Math.sin(t)]];
    rings.forEach((f) => {
      g.beginPath();
      for (let k = 0; k <= 96; k++) {
        const q = project(f(2 * Math.PI * k / 96));
        if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]);
      }
      g.stroke();
    });
    g.strokeStyle = T.line; g.beginPath(); g.arc(HALF, HALF, R, 0, 2 * Math.PI); g.stroke();
    const points = cloud() || [], labs = labels() || [];
    const order = points.map((p, i) => { const q = project(p); return [q[0], q[1], q[2], i]; });
    order.sort((a, b) => a[2] - b[2]);
    order.forEach((q) => { g.fillStyle = ctx.palette[labs[q[3]]] || T.line; g.fillRect(q[0] - 1.2, q[1] - 1.2, 2.4, 2.4); });
    if (overlay) overlay(g, project, T);
  }

  vc.addEventListener('pointerdown', (e) => { if (e.button !== 0) return; vc.setPointerCapture(e.pointerId); view.drag = [e.clientX, e.clientY]; });
  vc.addEventListener('pointermove', (e) => {
    if (!view.drag) return;
    view.yaw += (e.clientX - view.drag[0]) * 0.01;
    view.pitch += (e.clientY - view.drag[1]) * 0.01;
    view.drag = [e.clientX, e.clientY];
    draw();
  });
  const end = () => { view.drag = null; };
  vc.addEventListener('pointerup', end); vc.addEventListener('pointercancel', end);

  // the automatic rotation: yaw, pitch and roll advance at their own rates
  let lastT = 0;
  function spin(now) {
    if (!view.auto) return;
    const dt = Math.min(0.1, (now - lastT) / 1000); lastT = now;
    view.yaw += RATES.yaw * dt; view.pitch += RATES.pitch * dt; view.roll += RATES.roll * dt;
    draw(); requestAnimationFrame(spin);
  }
  const rotateBtn = ref(root, 'rotate');
  rotateBtn.addEventListener('click', () => {
    view.auto = !view.auto; rotateBtn.classList.toggle('on', view.auto);
    if (view.auto) { lastT = performance.now(); requestAnimationFrame(spin); }
  });
  return {draw, canvas: vc};
}

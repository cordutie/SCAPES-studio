// The interpolation panel of the Score page, in the place of the playground: the speed of the interpolation between a clip and the next one.
// A square of time (x, 0 .. 1 across the gap) and position (y, 0 = the first clip, 1 = the next one). The dots are joined by their Lagrange
// polynomial (core/curve.js). The two ends are fixed; drag a dot to move it, double-click an empty place to add one, double-click a dot to
// remove it. Default (top left) puts the dots back. It opens with the symbol between two clips on the timeline.
import {bus, dist, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {header} from '../../shared/core/ui.js';
import {followTab} from '../core/tabs.js';
import {DEFAULT_CURVE, MAX_POINTS, MIN_DX, copy, position} from '../core/curve.js';

const M = 48, DOT_R = 8, GRAB_PX = 14;                       // the margin around the square, the dots and their grab distance

export function mount(root, ctx) {
  const T = ctx.theme, PX = ctx.size;
  root.innerHTML = header('Interpolation') + `<canvas data-ref="canvas" width="${PX}" height="${PX}"></canvas>`;
  const top = root.querySelector('.top');
  const reset = document.createElement('button');                // at the top left, next to the title
  reset.textContent = 'Default'; reset.title = 'back to the default curve';
  top.insertBefore(reset, ref(root, 'tools'));
  ref(root, 'tools').innerHTML = `<span class="readout" data-ref="names"></span><button data-ref="back">Back</button>`;
  const pc = ref(root, 'canvas'), names = ref(root, 'names');
  followTab(root);

  const clip = () => S.clips.find((c) => c.id === S.interp) || null;
  const pts = () => { const c = clip(); return c ? (c.curve || (c.curve = copy(DEFAULT_CURVE))) : copy(DEFAULT_CURVE); };
  const S_ = PX - 2 * M;
  const toPx = (p) => [M + p[0] * S_, PX - M - p[1] * S_];
  const toUnit = (e) => { const r = pc.getBoundingClientRect(); return [(e.clientX - r.left - M) / S_, (PX - M - (e.clientY - r.top)) / S_]; };
  const sortPts = (a) => a.sort((p, q) => p[0] - q[0]);
  const last = (a) => a.length - 1;

  function draw() {
    const g = pc.getContext('2d');
    g.fillStyle = T.bg; g.fillRect(0, 0, PX, PX);
    const a = clip();
    if (!a) return;
    const b = ctx.timeline.next(a), p = sortPts(pts());
    g.strokeStyle = T.panel; g.lineWidth = 1;
    for (let k = 0; k <= 4; k++) {                                // the grid, every quarter
      const u = toPx([k / 4, k / 4]);
      g.beginPath(); g.moveTo(u[0], toPx([0, 0])[1]); g.lineTo(u[0], toPx([0, 1])[1]); g.moveTo(toPx([0, 0])[0], u[1]); g.lineTo(toPx([1, 0])[0], u[1]); g.stroke();
    }
    g.strokeStyle = T.line; g.strokeRect(M, M, S_, S_);
    g.font = `600 13px ${T.font}`; g.fillStyle = T.text;
    g.textAlign = 'center'; g.fillText('time →', PX / 2, PX - 14);
    g.textAlign = 'left';                                          // y = 1 (the next clip) above the square, y = 0 (the first clip) under it
    if (b) { g.fillStyle = ctx.palette[b.colour] || T.text; g.fillText('1 · ' + b.label, M, M - 14); }
    g.fillStyle = ctx.palette[a.colour] || T.text; g.fillText('0 · ' + a.label, M, PX - M + 20);
    g.fillStyle = T.text; g.textAlign = 'right'; g.fillText('1', PX - M, PX - M + 20); g.textAlign = 'left';
    g.strokeStyle = T.text; g.lineWidth = 2.5; g.beginPath();      // the curve, as the server uses it (the position limited to 0 .. 1)
    for (let k = 0; k <= 240; k++) {
      const q = toPx([k / 240, position(p, k / 240)]);
      if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]);
    }
    g.stroke(); g.lineWidth = 1;
    p.forEach((d, i) => {
      const q = toPx(d), end = i === 0 || i === last(p);
      g.beginPath(); g.arc(q[0], q[1], DOT_R, 0, 2 * Math.PI);
      if (end) { g.fillStyle = T.bg; g.fill(); g.strokeStyle = T.text; g.lineWidth = 2; g.stroke(); }
      else { g.fillStyle = T.accent; g.fill(); g.strokeStyle = T.bg; g.lineWidth = 1.5; g.stroke(); }
      g.lineWidth = 1;
    });
    names.textContent = b ? `${a.label} → ${b.label}` : '';
  }

  const near = (e) => {
    const p = pts(), here = toPx(toUnit(e));
    let best = -1, bd = GRAB_PX;
    p.forEach((d, i) => { const dd = dist(here, toPx(d)); if (dd < bd) { bd = dd; best = i; } });
    return best;
  };
  let drag = null;
  pc.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    const i = near(e), p = sortPts(pts());
    if (i <= 0 || i >= last(p)) return;                           // the ends do not move
    pc.setPointerCapture(e.pointerId);
    drag = {id: e.pointerId, dot: p[i]};
  });
  pc.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const p = sortPts(pts()), i = p.indexOf(drag.dot), u = toUnit(e);
    drag.dot[0] = Math.min(p[i + 1][0] - MIN_DX, Math.max(p[i - 1][0] + MIN_DX, u[0]));       // it keeps between its neighbours in time
    drag.dot[1] = Math.min(1, Math.max(0, u[1]));
    draw();
  });
  const release = (e) => { if (drag && e.pointerId === drag.id) { drag = null; commit(); } };
  pc.addEventListener('pointerup', release); pc.addEventListener('pointercancel', release);
  pc.addEventListener('dblclick', (e) => {
    const p = sortPts(pts()), i = near(e), u = toUnit(e);
    if (i > 0 && i < last(p)) p.splice(i, 1);                     // a dot (not an end): removed
    else if (i < 0 && p.length < MAX_POINTS && u[0] > 0 && u[0] < 1 && p.every((d) => Math.abs(d[0] - u[0]) >= MIN_DX)) p.push([u[0], Math.min(1, Math.max(0, u[1]))]);
    else return;
    sortPts(p); commit();
  });
  // the clip keeps the curve (the timeline marks a changed one)
  function commit() { const a = clip(); if (a) ctx.timeline.setCurve(a, copy(sortPts(pts()))); draw(); }
  reset.addEventListener('click', () => { const a = clip(); if (a) { ctx.timeline.setCurve(a, null); draw(); } });
  ref(root, 'back').addEventListener('click', () => { S.interp = null; bus.emit('interp'); ctx.timeline.refresh(); });

  bus.on('interp', draw); bus.on('clips', draw); bus.on('tab', draw); bus.on('boot', draw);
  draw();
}

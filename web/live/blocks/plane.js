// The semantic playground: drop cluster dots on it, move the control point, and the embedding is the mean of the clusters around it.
// Two modes. Control (the default): the dots stand still (drawn filled); a press and move sets the point, a click sets it there (also
// on a dot), and with Glide on a click starts a straight glide to it. Edit dots (the button, or hold Ctrl): the dots are drawn as
// open rings and can be dragged; the press does not control the sound. Double-click a dot (either mode) removes it, and the
// control point goes to the nearest place of what is left.
import {S, bus, clampP, dist, ref} from '../../shared/core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {linear} from '../../shared/core/maps.js';
import {header} from '../../shared/core/ui.js';
import {drawPointer} from '../../shared/core/pointer.js';

const DOT_R = 8;                  // px: the dots
const GRAB_PX = 12, MOVE_TOL = 5;     // px: distance that grabs a dot; press-and-move threshold

export function mount(root, ctx) {
  const T = ctx.theme;
  const PX = ctx.size, HALF = PX / 2;      // the canvas: its size is CANVAS in theme.js
  root.innerHTML = header('Semantic playground') + `<canvas data-ref="canvas" width="${ctx.size}" height="${ctx.size}"></canvas>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<button data-ref="edit" title="move the dots instead of controlling the sound (hold Ctrl for the same, while held)">Edit</button>
    <button data-ref="glide" title="a click glides to the point instead of jumping">Glide</button>`;
  tools.append(createKnob({map: linear(0, 60), value: S.glideT, def: S.glideT, step: 0.5, size: 26, inline: true, label: 'Glide time',
    format: (v) => v.toFixed(1) + ' s', onChange: (v) => { S.glideT = v; }}).el);
  const pc = ref(root, 'canvas');
  // edit mode: the button latches it, Ctrl turns it on while held
  let latched = false, ctrlDown = false;
  const editing = () => latched || ctrlDown;
  function syncEdit() {
    const was = S.editDots; S.editDots = editing();
    ref(root, 'edit').classList.toggle('on', S.editDots);
    if (was !== S.editDots) draw();
  }
  window.addEventListener('keydown', (e) => { if (e.key === 'Control' && !ctrlDown) { ctrlDown = true; syncEdit(); } });
  window.addEventListener('keyup', (e) => { if (e.key === 'Control') { ctrlDown = false; syncEdit(); } });
  window.addEventListener('blur', () => { ctrlDown = false; syncEdit(); });

  const planeRaw = (e) => { const r = pc.getBoundingClientRect(); return [(e.clientX - r.left) / PX * 2 - 1, 1 - (e.clientY - r.top) / PX * 2]; };
  const toPx = (p) => [(p[0] + 1) * HALF, (1 - p[1]) * HALF];
  // the index of the dot nearest to a plane point, if within GRAB_PX px; otherwise -1
  function dotNear(p) {
    let best = -1, bd = GRAB_PX;
    const a = toPx(p);
    S.dots.forEach((d, i) => { if (!d) return; const dd = dist(a, toPx(d)); if (dd < bd) { bd = dd; best = i; } });
    return best;
  }

  // ask for a point: the next live call projects it on the zone of the dots. False with no dots
  function moveCtrl(p) {
    if (!S.dots.some((x) => x !== null)) return false;
    S.aim = p.slice(); S.needLocate = true; return true;
  }

  function draw() {
    const g = pc.getContext('2d');
    g.fillStyle = T.bg; g.fillRect(0, 0, PX, PX);
    g.strokeStyle = T.panel;
    g.beginPath(); g.moveTo(HALF, 0); g.lineTo(HALF, PX); g.moveTo(0, HALF); g.lineTo(PX, HALF); g.stroke();
    // the zone of the dots: a gray polygon (3+), a segment (2), a ring (1)
    const ids = S.lastLive && S.lastLive.outline ? S.lastLive.outline : [];
    const corners = ids.filter((i) => S.dots[i]).map((i) => toPx(S.dots[i]));
    if (corners.length >= 3) {
      g.beginPath();
      corners.forEach((q, k) => { if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]); });
      g.closePath();
      g.fillStyle = T.zone; g.fill();
    } else if (corners.length === 2) {
      g.beginPath(); g.moveTo(corners[0][0], corners[0][1]); g.lineTo(corners[1][0], corners[1][1]);
      g.strokeStyle = T.accentFaint; g.lineWidth = 3; g.stroke(); g.lineWidth = 1;
    } else if (corners.length === 1) {
      g.beginPath(); g.arc(corners[0][0], corners[0][1], 10, 0, 2 * Math.PI);
      g.strokeStyle = T.accentFaint; g.lineWidth = 2; g.stroke(); g.lineWidth = 1;
    }
    // the dots, in the colour of their block: filled and still in control mode, open rings (to grab) in edit mode
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d), col = ctx.palette[i] || T.line;
      g.beginPath(); g.arc(q[0], q[1], DOT_R, 0, 2 * Math.PI);
      if (S.editDots) { g.fillStyle = T.bg; g.fill(); g.strokeStyle = col; g.lineWidth = 3; g.stroke(); g.lineWidth = 1; }
      else { g.fillStyle = col; g.fill(); g.strokeStyle = T.bg; g.lineWidth = 1.5; g.stroke(); g.lineWidth = 1; }
    });
    // the names, right of and below the dot (left of it when they would run past the edge)
    g.font = `600 13px ${T.font}`; g.fillStyle = T.text;
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d), text = S.names[i] || '', w = g.measureText(text).width;
      g.fillText(text, q[0] + 10 + w > PX ? q[0] - 10 - w : q[0] + 10, q[1] + 4);
    });
    const c = toPx(S.ctrl);                                // the control point (core/pointer.js)
    drawPointer(g, T, c[0], c[1]);
  }

  // --- glide: a straight line to the clicked point, in S.glideT seconds (0 jumps) ---
  let glideTok = null;
  async function startGlide(target) {
    if (!S.dots.some((x) => x !== null)) return;
    const l0 = S.ctrl.slice(), Tg = S.glideT, t0 = performance.now(), tok = {};
    glideTok = tok;
    let proj = null;
    try { proj = (await ctx.api.project({dots: S.dots, p: target})).c; } catch (e) { proj = null; }
    if (glideTok !== tok) return;                          // a press and move, or a new click, took over
    if (!proj) { glideTok = null; return; }
    const end = proj.slice();
    const step = () => {
      if (glideTok !== tok) return;
      const f = Tg <= 0 ? 1 : Math.min(1, (performance.now() - t0) / 1000 / Tg);
      if (!moveCtrl(f >= 1 ? end.slice() : [l0[0] + f * (end[0] - l0[0]), l0[1] + f * (end[1] - l0[1])])) { glideTok = null; return; }
      draw(); ctx.live.request();
      if (f < 1) requestAnimationFrame(step); else glideTok = null;
    };
    if (Tg <= 0) step(); else requestAnimationFrame(step);
  }

  // --- the gesture in progress: where it was pressed, the dot it grabbed (or -1), and its state ---
  let pg = null;
  pc.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    pc.setPointerCapture(e.pointerId);
    const raw = planeRaw(e), i = dotNear(clampP(raw)), grab = S.editDots && i >= 0;
    pg = {id: e.pointerId, x: e.clientX, y: e.clientY, hit: grab ? i : -1, edit: S.editDots, dragging: false, moving: false, off: null};
    if (grab) pg.off = [S.dots[i][0] - raw[0], S.dots[i][1] - raw[1]];     // the dot does not jump
  });
  // the control point at the weighted position of the selection
  function selCtrl() {
    let x = 0, y = 0;
    S.sel.idx.forEach((i, k) => { x += S.sel.lam[k] * S.dots[i][0]; y += S.sel.lam[k] * S.dots[i][1]; });
    return [x, y];
  }
  function gestureMove(g, e) {
    const far = dist([e.clientX, e.clientY], [g.x, g.y]) >= MOVE_TOL, raw = planeRaw(e);
    if (g.hit >= 0) {                                      // a grabbed dot follows the pointer
      if (!far && !g.dragging) return;
      g.dragging = true; S.draggingDot = true;
      S.dots[g.hit] = clampP([raw[0] + g.off[0], raw[1] + g.off[1]]);
      if (S.sel && S.sel.idx.includes(g.hit)) S.ctrl = selCtrl();
    } else if (g.edit) {                                   // edit mode: a press away from a dot does nothing
      return;
    } else {                                               // else the control point follows (a glide is cancelled)
      if (far && !g.moving) { g.moving = true; glideTok = null; }
      if (!g.moving || !moveCtrl(clampP(raw))) return;
    }
    draw(); ctx.live.request();
  }
  pc.addEventListener('pointermove', (e) => { if (pg && e.pointerId === pg.id) gestureMove(pg, e); });
  // release: a click (under 5 px) with Glide on starts a glide; with it off, a click elsewhere than on a dot moves the point
  function endPlane(e) {
    if (!pg || e.pointerId !== pg.id) return;
    const g = pg; pg = null;
    gestureMove(g, e);
    S.draggingDot = false;
    if (g.dragging || g.moving || dist([e.clientX, e.clientY], [g.x, g.y]) >= MOVE_TOL) return;
    const p = clampP(planeRaw(e));
    if (g.edit) return;                                    // edit mode never controls the sound
    if (S.glide) { startGlide(p); return; }
    if (!moveCtrl(p)) return;
    draw(); ctx.live.request();
  }
  pc.addEventListener('pointerup', endPlane);
  pc.addEventListener('pointercancel', endPlane);
  pc.addEventListener('dblclick', (e) => {                 // remove the dot; the next live call brings the control point back into the zone
    const i = dotNear(clampP(planeRaw(e)));
    if (i < 0) return;
    glideTok = null;
    S.dots[i] = null;
    if (!S.dots.some((x) => x !== null)) { S.sel = null; S.lastLive = null; }
    draw(); bus.emit('dots'); ctx.live.request();
  });

  // --- the glide bar ---
  ref(root, 'edit').addEventListener('click', () => { latched = !latched; syncEdit(); });
  ref(root, 'glide').addEventListener('click', (e) => { S.glide = !S.glide; e.target.classList.toggle('on', S.glide); });

  bus.on('live', draw); bus.on('dots', draw); bus.on('boot', draw);
  ctx.plane = {canvas: pc, planeRaw, draw};
}

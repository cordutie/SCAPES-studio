// The semantic playground of the Score page. It works as the one of Live: place sources on it as dots (drag them from the sources), press
// and move to set the control point (it stands for the mix of the dots around it, drawn as lines as strong as the weights), Edit (or hold
// Ctrl) to move the dots, double-click a dot to remove it. What is new here:
//   - a double-click on an empty place makes a free dot: it stands for the mix that was there (its CLAP embedding), whatever it is later;
//   - Score (or hold Shift): every dot, and the control point, glows to show they can be picked: drag one onto the timeline to make a clip.
import {bus, clampP, dist, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {comp, mixOf, labelOf, clusterOf} from '../core/mix.js';
import {header} from '../../shared/core/ui.js';
import {drawPointer} from '../../shared/core/pointer.js';
import {followTab} from '../core/tabs.js';

const DOT_R = 8, GRAB_PX = 14, MOVE_PX = 5, MAX_FREE = 100;

export function mount(root, ctx) {
  const T = ctx.theme, PX = ctx.size, HALF = PX / 2;
  root.innerHTML = header('Semantic playground', 'Score playground') + `<canvas data-ref="canvas" width="${PX}" height="${PX}"></canvas>`;
  ref(root, 'tools').innerHTML = `<button data-ref="edit" title="move the dots instead of controlling the point (hold Ctrl for the same, while held)">Edit</button>
    <button data-ref="score" title="the dots glow: drag one onto the timeline to make a clip of it (hold Shift for the same, while held)">Score</button>
    <button data-ref="clear">Clear</button>`;
  const pc = ref(root, 'canvas');
  followTab(root);
  const n = () => S.sources.length;
  const toPx = (p) => [(p[0] + 1) * HALF, (1 - p[1]) * HALF];
  const planeRaw = (e) => { const r = pc.getBoundingClientRect(); return [(e.clientX - r.left) / PX * 2 - 1, 1 - (e.clientY - r.top) / PX * 2]; };
  const placed = () => S.dots.some((d) => d !== null);
  const colour = (i) => ctx.palette[i < n() ? S.sources[i].cluster : clusterOf(comp(i))] || T.line;
  const nameOf = (i) => (i < n() ? S.sources[i].name : '≈ ' + labelOf(comp(i)));

  // --- the modes: Edit (button or Ctrl) moves dots, Score (button or Shift) picks them for the timeline, else a press controls the point ---
  let latch = null, ctrl = false, shift = false;                       // latch: 'edit' | 'score' | null
  const mode = () => (latch === 'edit' || ctrl ? 'edit' : latch === 'score' || shift ? 'score' : 'control');
  let shown = 'control', raf = 0;
  function syncMode() {
    const m = mode();
    ref(root, 'edit').classList.toggle('on', m === 'edit'); ref(root, 'score').classList.toggle('on', m === 'score');
    pc.style.cursor = m === 'edit' ? 'move' : '';
    if (m !== shown) { shown = m; draw(); }
    if (m === 'score' && !raf) pulse();
  }
  function pulse() {                                                    // the glow breathes while Score is on
    raf = 0;
    if (mode() !== 'score') return;
    draw(); raf = requestAnimationFrame(pulse);
  }
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Control' && !ctrl) { ctrl = true; syncMode(); }
    if (e.key === 'Shift' && !shift) { shift = true; syncMode(); }
  });
  window.addEventListener('keyup', (e) => {
    if (e.key === 'Control') { ctrl = false; syncMode(); }
    if (e.key === 'Shift') { shift = false; syncMode(); }
  });
  window.addEventListener('blur', () => { ctrl = shift = false; syncMode(); });
  const latchTo = (m) => { latch = latch === m ? null : m; syncMode(); };
  ref(root, 'edit').addEventListener('click', () => latchTo('edit'));
  ref(root, 'score').addEventListener('click', () => latchTo('score'));

  function dotNear(p) {
    let best = -1, bd = GRAB_PX;
    const a = toPx(p);
    S.dots.forEach((d, i) => { if (!d) return; const dd = dist(a, toPx(d)); if (dd < bd) { bd = dd; best = i; } });
    return best;
  }
  const onPoint = (p) => S.point && S.point.c && dist(toPx(S.point.c), toPx(p)) <= GRAB_PX;

  function draw() {
    const g = pc.getContext('2d'), m = mode();
    g.fillStyle = T.bg; g.fillRect(0, 0, PX, PX);
    g.strokeStyle = T.panel;
    g.beginPath(); g.moveTo(HALF, 0); g.lineTo(HALF, PX); g.moveTo(0, HALF); g.lineTo(PX, HALF); g.stroke();
    const pt = S.point;
    const corners = pt ? pt.outline.filter((i) => S.dots[i]).map((i) => toPx(S.dots[i])) : [];
    if (corners.length >= 3) {                                  // the zone of the dots: a gray polygon (3+), a segment (2), a ring (1)
      g.beginPath(); corners.forEach((q, k) => (k ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.closePath(); g.fillStyle = T.zone; g.fill();
    } else if (corners.length === 2) {
      g.beginPath(); g.moveTo(corners[0][0], corners[0][1]); g.lineTo(corners[1][0], corners[1][1]);
      g.strokeStyle = T.accentFaint; g.lineWidth = 3; g.stroke(); g.lineWidth = 1;
    }
    const c = pt && pt.c ? toPx(pt.c) : null;
    if (c && pt.sel) {                                          // the mix: a line to each dot around the point, as strong as its weight
      pt.sel.idx.forEach((i, k) => {
        if (!S.dots[i]) return;                                  // a dot that was just removed: the answer has not come yet
        const q = toPx(S.dots[i]);
        g.beginPath(); g.moveTo(c[0], c[1]); g.lineTo(q[0], q[1]);
        g.strokeStyle = colour(i); g.globalAlpha = 0.25 + 0.75 * pt.sel.lam[k]; g.lineWidth = 1 + 4 * pt.sel.lam[k]; g.stroke();
      });
      g.globalAlpha = 1; g.lineWidth = 1;
    }
    const breathe = 0.5 + 0.5 * Math.sin(performance.now() / 260);
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d), col = colour(i);
      if (m === 'score') {                                       // glowing: these can be picked
        g.beginPath(); g.arc(q[0], q[1], DOT_R + 5 + 4 * breathe, 0, 2 * Math.PI);
        g.strokeStyle = T.accent; g.globalAlpha = 0.35 + 0.5 * breathe; g.lineWidth = 3; g.stroke(); g.globalAlpha = 1; g.lineWidth = 1;
      }
      g.beginPath(); g.arc(q[0], q[1], m === 'score' ? DOT_R + 2 : DOT_R, 0, 2 * Math.PI);
      if (m === 'edit') { g.fillStyle = T.bg; g.fill(); g.strokeStyle = col; g.lineWidth = 3; g.stroke(); g.lineWidth = 1; }
      else { g.fillStyle = col; g.fill(); g.strokeStyle = i < n() ? T.bg : T.text; g.lineWidth = i < n() ? 1.5 : 2; g.stroke(); g.lineWidth = 1; }
    });
    g.font = `600 13px ${T.font}`; g.fillStyle = T.text;
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d), text = nameOf(i), w = g.measureText(text).width;
      g.fillText(text, q[0] + 14 + w > PX ? q[0] - 14 - w : q[0] + 14, q[1] + 4);
    });
    if (c) {
      if (m === 'score') {
        g.beginPath(); g.arc(c[0], c[1], 17 + 4 * breathe, 0, 2 * Math.PI);
        g.strokeStyle = T.accent; g.globalAlpha = 0.35 + 0.5 * breathe; g.lineWidth = 3; g.stroke(); g.globalAlpha = 1; g.lineWidth = 1;
      }
      drawPointer(g, T, c[0], c[1]);
    }
  }

  // ask where the point is among the dots (the latest question wins)
  let busy = false, again = false;
  async function ask() {
    if (busy) { again = true; return; }
    busy = true;
    try {
      do {
        again = false;
        const r = await ctx.api.locate({dots: S.dots, c: S.c, px: PX});
        S.point = r.sel ? r : null;
        S.c = r.c || null;
        draw(); bus.emit('point');
      } while (again);
    } finally { busy = false; }
  }

  // --- the gesture in progress ---
  let pg = null, chip = null;
  const snapshot = () => (S.point && S.point.sel ? {comp: mixOf(S.point.sel.idx, S.point.sel.lam), colour: S.point.sel.idx[0]} : null);
  function carry(e, item) {                                            // a chip follows the pointer; over the timeline it shows where it lands
    if (!chip) {
      chip = document.createElement('div');
      chip.className = 'chip';
      chip.textContent = labelOf(item.comp);
      chip.style.borderColor = ctx.palette[clusterOf(item.comp)] || T.line;
      ctx.root.appendChild(chip);
    }
    const a = ctx.root.getBoundingClientRect();
    chip.style.left = (e.clientX - a.left) + 'px'; chip.style.top = (e.clientY - a.top) + 'px';
    ctx.timeline.hover(e.clientX, e.clientY);
  }
  pc.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    pc.setPointerCapture(e.pointerId);
    const p = clampP(planeRaw(e)), i = dotNear(p), m = mode();
    pg = {id: e.pointerId, x: e.clientX, y: e.clientY, mode: 'point', moved: false};
    if (m === 'edit' && i >= 0) Object.assign(pg, {mode: 'dot', i, off: [S.dots[i][0] - p[0], S.dots[i][1] - p[1]]});
    else if (m === 'edit') pg.mode = 'none';                            // a press away from a dot does nothing in Edit
    else if (m === 'score') {
      const item = i >= 0 ? {comp: comp(i)} : onPoint(p) ? snapshot() : null;   // the point as it is now, wherever it moves later
      if (item) Object.assign(pg, {mode: 'carry', item}); else pg.mode = 'none';
    } else if (placed()) { S.c = p; ask(); }
  });
  pc.addEventListener('pointermove', (e) => {
    if (!pg || e.pointerId !== pg.id) return;
    if (!pg.moved && dist([e.clientX, e.clientY], [pg.x, pg.y]) < MOVE_PX) return;
    pg.moved = true;
    const raw = planeRaw(e);
    if (pg.mode === 'dot') { S.dots[pg.i] = clampP([raw[0] + pg.off[0], raw[1] + pg.off[1]]); draw(); bus.emit('dots'); ask(); }
    else if (pg.mode === 'point' && placed()) { S.c = clampP(raw); ask(); }
    else if (pg.mode === 'carry') carry(e, pg.item);
  });
  const release = (e) => {
    if (!pg || e.pointerId !== pg.id) return;
    const g = pg; pg = null;
    if (chip) { chip.remove(); chip = null; ctx.timeline.leave(); }
    if (g.mode === 'carry' && g.moved) ctx.timeline.dropAt(e.clientX, e.clientY, g.item);
  };
  pc.addEventListener('pointerup', release); pc.addEventListener('pointercancel', release);

  // double-click: on a dot removes it; on an empty place makes a free dot that stands for the mix there
  pc.addEventListener('dblclick', async (e) => {
    const p = clampP(planeRaw(e)), i = dotNear(p);
    if (i >= 0) {
      S.dots[i] = null;
      if (!placed()) { S.point = null; S.c = null; }
      draw(); bus.emit('dots'); ask();
      return;
    }
    if (!placed() || S.free.length >= MAX_FREE) return;
    const r = await ctx.api.locate({dots: S.dots, c: p, px: PX});
    if (!r.sel) return;
    const where = clampP(r.c);
    if (dotNear(where) >= 0) return;                                   // that place is a dot already
    S.free.push({comp: mixOf(r.sel.idx, r.sel.lam)}); S.dots.push(where);
    draw(); bus.emit('dots'); ask();
  });

  ref(root, 'clear').addEventListener('click', () => {
    S.dots = Array(n()).fill(null); S.free = []; S.point = null; S.c = null;
    draw(); bus.emit('dots');
  });

  // what the sources block uses: a source dropped at the plane point p (a dot already there moves)
  ctx.playground = {
    canvas: pc, planeRaw,
    place(i, p) { S.dots[i] = clampP(p); draw(); bus.emit('dots'); ask(); },
    draw,
  };
  bus.on('boot', draw); bus.on('tab', draw);
  draw();
}

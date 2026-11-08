// The semantic playground of the Score page: place sources as dots, then move the point between them (it stands for the mix of the sources
// around it, drawn as lines of different strength). Drag a dot to move it; double-click it to remove it; press on the empty area to steer
// the point. Drag the point itself out of the canvas onto the timeline to make a clip of it (or press + Timeline).
import {bus, clampP, dist, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {header} from '../../shared/core/ui.js';
import {drawPointer} from '../../shared/core/pointer.js';

const DOT_R = 9, GRAB_PX = 14;

export function mount(root, ctx) {
  const T = ctx.theme, PX = ctx.size, HALF = PX / 2;
  root.innerHTML = header('Semantic playground', 'Score playground') + `<canvas data-ref="canvas" width="${PX}" height="${PX}"></canvas>`;
  ref(root, 'tools').innerHTML = `<button data-ref="add" title="add the point to the end of the timeline">+ Timeline</button><button data-ref="clear">Clear</button>`;
  const pc = ref(root, 'canvas');
  const toPx = (p) => [(p[0] + 1) * HALF, (1 - p[1]) * HALF];
  const planeRaw = (e) => { const r = pc.getBoundingClientRect(); return [(e.clientX - r.left) / PX * 2 - 1, 1 - (e.clientY - r.top) / PX * 2]; };
  const placed = () => S.dots.some((d) => d !== null);
  const colour = (i) => ctx.palette[S.sources[i].cluster] || T.line;

  function dotNear(p) {
    let best = -1, bd = GRAB_PX;
    const a = toPx(p);
    S.dots.forEach((d, i) => { if (!d) return; const dd = dist(a, toPx(d)); if (dd < bd) { bd = dd; best = i; } });
    return best;
  }

  function draw() {
    const g = pc.getContext('2d');
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
    if (c && pt.sel) {                                          // the mix: a line to each source around the point, as strong as its weight
      pt.sel.idx.forEach((i, k) => {
        if (!S.dots[i]) return;                                  // a dot that was just removed: the answer has not come yet
        const q = toPx(S.dots[i]);
        g.beginPath(); g.moveTo(c[0], c[1]); g.lineTo(q[0], q[1]);
        g.strokeStyle = colour(i); g.globalAlpha = 0.25 + 0.75 * pt.sel.lam[k]; g.lineWidth = 1 + 4 * pt.sel.lam[k]; g.stroke();
      });
      g.globalAlpha = 1; g.lineWidth = 1;
    }
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d);
      g.beginPath(); g.arc(q[0], q[1], DOT_R, 0, 2 * Math.PI); g.fillStyle = colour(i); g.fill();
      g.strokeStyle = T.bg; g.lineWidth = 1.5; g.stroke(); g.lineWidth = 1;
    });
    g.font = `600 13px ${T.font}`; g.fillStyle = T.text;
    S.dots.forEach((d, i) => {
      if (!d) return;
      const q = toPx(d), text = S.sources[i].name, w = g.measureText(text).width;
      g.fillText(text, q[0] + 12 + w > PX ? q[0] - 12 - w : q[0] + 12, q[1] + 4);
    });
    if (c) drawPointer(g, T, c[0], c[1]);
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
        if (r.c) S.c = r.c;
        else S.c = null;
        draw(); bus.emit('point');
      } while (again);
    } finally { busy = false; }
  }

  // --- the gesture in progress ---
  let pg = null, chip = null;
  const snapshot = () => (S.point && S.point.sel ? {idx: S.point.sel.idx.slice(), lam: S.point.sel.lam.slice(), c: S.point.c.slice()} : null);
  function carryChip(e, snap) {
    if (!chip) {
      chip = document.createElement('div');
      chip.className = 'chip';
      const best = snap.idx.reduce((b, i, k) => (snap.lam[k] > snap.lam[b] ? k : b), 0);
      chip.textContent = S.sources[snap.idx[best]].name + (snap.idx.length > 1 ? ` +${snap.idx.length - 1}` : '');
      chip.style.borderColor = colour(snap.idx[best]);
      ctx.root.appendChild(chip);
    }
    const a = ctx.root.getBoundingClientRect();
    chip.style.left = (e.clientX - a.left) + 'px'; chip.style.top = (e.clientY - a.top) + 'px';
    ctx.timeline.hover(e.clientX, e.clientY);
  }
  pc.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    pc.setPointerCapture(e.pointerId);
    const p = clampP(planeRaw(e)), i = dotNear(p);
    const onPoint = S.point && S.point.c && dist(toPx(S.point.c), toPx(p)) <= GRAB_PX;
    // a press on the point picks it up: the clip made by dropping it is the point as it was now, wherever it slides on the way out
    pg = {id: e.pointerId, mode: i >= 0 ? 'dot' : onPoint ? 'carry' : 'point', i, off: i >= 0 ? [S.dots[i][0] - p[0], S.dots[i][1] - p[1]] : null,
          pick: onPoint ? snapshot() : null};
    if (pg.mode === 'point' && placed()) { S.c = p; ask(); }
  });
  pc.addEventListener('pointermove', (e) => {
    if (!pg || e.pointerId !== pg.id) return;
    const raw = planeRaw(e), inside = Math.abs(raw[0]) <= 1 && Math.abs(raw[1]) <= 1;
    if (pg.mode === 'dot') {
      S.dots[pg.i] = clampP([raw[0] + pg.off[0], raw[1] + pg.off[1]]);
      draw(); bus.emit('dots'); ask();
    } else if (pg.mode === 'point' || (pg.mode === 'carry' && inside)) {
      if (chip) { chip.remove(); chip = null; ctx.timeline.leave(); }
      S.c = clampP(raw); ask();
    } else if (pg.mode === 'carry') {
      if (!chip) { S.c = pg.pick.c.slice(); ask(); }                  // it left the canvas: the point goes back to where it was picked up
      carryChip(e, pg.pick);
    }
  });
  const release = (e) => {
    if (!pg || e.pointerId !== pg.id) return;
    const g = pg; pg = null;
    if (chip) {
      chip.remove(); chip = null;
      if (g.pick) ctx.timeline.dropAt(e.clientX, e.clientY, g.pick);
    }
  };
  pc.addEventListener('pointerup', release); pc.addEventListener('pointercancel', release);
  pc.addEventListener('dblclick', (e) => {
    const i = dotNear(clampP(planeRaw(e)));
    if (i < 0) return;
    S.dots[i] = null;
    if (!placed()) { S.point = null; S.c = null; }
    draw(); bus.emit('dots'); ask();
  });

  ref(root, 'clear').addEventListener('click', () => {
    S.dots = Array(S.sources.length).fill(null); S.point = null; S.c = null;
    draw(); bus.emit('dots');
  });
  ref(root, 'add').addEventListener('click', () => { const snap = snapshot(); if (snap) ctx.timeline.append(snap); });

  // what the sources block uses: a source dropped at the plane point p (a dot already there moves)
  ctx.playground = {
    canvas: pc, planeRaw,
    place(i, p) { S.dots[i] = clampP(p); draw(); bus.emit('dots'); ask(); },
    draw,
  };
  bus.on('boot', draw);
  draw();
}

// The structure playground (the disk): the error point, the part of the embedding that the clusters' means do not hold. Drag it, or switch Auto
// on and it moves by itself with the dynamics of the data, a new target every 1 / Hz seconds.
import {S, bus, clampD, sleep, ref} from '../../shared/core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {linear} from '../../shared/core/maps.js';
import {header} from '../../shared/core/ui.js';
import {drawPointer} from '../../shared/core/pointer.js';


export function mount(root, ctx) {
  const T = ctx.theme;
  const PX = ctx.size, HALF = PX / 2, R = HALF - 20;      // the canvas: its size is CANVAS in theme.js
  root.innerHTML = header('Structure playground') + `<canvas data-ref="canvas" width="${ctx.size}" height="${ctx.size}"></canvas>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<button data-ref="prior" title="the point moves by itself, following how the data changes">Auto</button>`;
  tools.append(createKnob({map: linear(0.5, 20), value: S.hz, def: S.hz, step: 0.5, size: 26, inline: true, label: 'Auto rate',
    format: (v) => v.toFixed(1) + ' Hz', onChange: (v) => { S.hz = v; if (S.prior) priorStart(); }}).el);
  const dc = ref(root, 'canvas'), priorBtn = ref(root, 'prior');
  const diskRaw = (e) => { const r = dc.getBoundingClientRect(); return [(e.clientX - r.left - HALF) / R, (HALF - (e.clientY - r.top)) / R]; };

  function draw() {
    const g = dc.getContext('2d');
    g.fillStyle = T.bg; g.fillRect(0, 0, PX, PX);
    g.strokeStyle = T.panel;
    g.beginPath(); g.moveTo(HALF, 0); g.lineTo(HALF, PX); g.moveTo(0, HALF); g.lineTo(PX, HALF); g.stroke();
    g.strokeStyle = T.line;
    g.beginPath(); g.arc(HALF, HALF, R, 0, 2 * Math.PI); g.stroke();
    drawPointer(g, T, HALF + S.u[0] * R, HALF - S.u[1] * R);
  }

  // press and move sets the point (clamped to the circle); ignored while Auto is on
  let diskId = null;
  dc.addEventListener('pointerdown', (e) => { if (e.button !== 0 || S.prior) return; dc.setPointerCapture(e.pointerId); diskId = e.pointerId; });
  dc.addEventListener('pointermove', (e) => {
    if (diskId === null || e.pointerId !== diskId || S.prior) return;
    S.u = clampD(diskRaw(e)); draw(); ctx.live.request();
  });
  const end = (e) => { if (e.pointerId === diskId) diskId = null; };
  dc.addEventListener('pointerup', end); dc.addEventListener('pointercancel', end);

  // --- Auto (the prior of the atlas): one server sample per tick, then a straight move to it by the next tick ---
  let token = 0, hist = null, tickNo = 0;
  function priorStop() { token += 1; S.prior = false; priorBtn.classList.remove('on'); }
  function priorToggle() {
    if (S.prior) { priorStop(); return; }
    hist = Array(10).fill(0).map(() => S.u.slice());          // ten copies of the disk point, newest first
    S.prior = true; priorBtn.classList.add('on'); priorStart();
  }
  function priorStart() { token += 1; priorRun(token); }
  async function priorRun(tk) {
    let due = performance.now();
    while (tk === token) {
      if (due > performance.now()) await sleep(due - performance.now());
      if (tk !== token) return;
      const period = 1000 / S.hz, endAt = due + period;
      await priorTick(tk, endAt);
      due = endAt;
      if (performance.now() > due + period) due = performance.now();   // far behind: start now
    }
  }
  async function priorTick(tk, endAt) {
    const live = S.lastLive;
    if (!live || live.cluster === null || live.cluster === undefined) return;
    let r = null;
    try { r = await ctx.api.priorStep({hist, cluster: live.cluster, tick: tickNo++}); } catch (e) { return; }
    if (tk !== token || !r || !r.u) return;
    hist = [r.u, ...hist.slice(0, 9)];
    await moveDisk(tk, r.u, endAt);
  }
  // move the point in a straight line to target, arriving at endAt; false if the loop stopped
  function moveDisk(tk, target, endAt) {
    return new Promise((resolve) => {
      const from = S.u.slice(), t0 = performance.now(), dur = Math.max(0, endAt - t0);
      const step = () => {
        if (tk !== token) { resolve(false); return; }
        const f = dur <= 0 ? 1 : Math.min(1, (performance.now() - t0) / dur);
        S.u = f >= 1 ? target.slice() : [from[0] + f * (target[0] - from[0]), from[1] + f * (target[1] - from[1])];
        draw(); ctx.live.request();
        if (f < 1) requestAnimationFrame(step); else resolve(true);
      };
      requestAnimationFrame(step);
    });
  }
  priorBtn.addEventListener('click', priorToggle);
  bus.on('live', draw); bus.on('dots', draw);
  bus.on('boot', () => {
    priorBtn.disabled = !S.hasPrior;
    if (!S.hasPrior) priorBtn.title = 'this atlas was saved without a prior';
    draw();
  });
  draw();
}

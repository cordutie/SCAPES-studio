// The timeline: the piece from left to right. A clip is a point of the playground (the sources around it and their weights) that lasts
// some seconds. Drop the playground's point on it to add a clip; drag a clip to move it, its right edge to change its length, double-click
// it to remove it. Clips never overlap: a clip stops at its neighbours. Nothing is generated here yet.
import {bus, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {linear} from '../../shared/core/maps.js';
import {header} from '../../shared/core/ui.js';

const DEFAULT_SECONDS = 4, MIN_SECONDS = 0.5, EDGE_PX = 8;
const STEPS = [0.5, 1, 2, 5, 10, 15, 30, 60, 120];          // seconds between the marks of the ruler

export function mount(root, ctx) {
  root.innerHTML = header('Timeline') + `<div class="tl-scroll" data-ref="scroll"><div class="tl-inner" data-ref="inner">
    <div class="ruler" data-ref="ruler"></div><div class="tl-track" data-ref="track"><div class="drop-mark" data-ref="mark" hidden></div></div></div></div>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<span class="readout" data-ref="readout"></span><button data-ref="clear" title="remove every clip">Clear</button>`;
  tools.prepend(createKnob({map: linear(8, 120), value: S.pps, def: S.pps, step: 1, size: 26, inline: true, label: 'Zoom',
    format: (v) => v.toFixed(0) + ' px/s', onChange: (v) => { S.pps = v; render(); }}).el);
  tools.prepend(createKnob({map: linear(10, 600), value: S.length, def: S.length, step: 5, size: 26, inline: true, label: 'Length',
    format: (v) => v.toFixed(0) + ' s', onChange: (v) => { S.length = Math.max(v, lastEnd()); render(); }}).el);
  const scroll = ref(root, 'scroll'), inner = ref(root, 'inner'), ruler = ref(root, 'ruler'), track = ref(root, 'track'), mark = ref(root, 'mark');
  const readout = ref(root, 'readout');
  let selected = null, seq = 0;

  const sorted = () => [...S.clips].sort((a, b) => a.start - b.start);
  const lastEnd = () => S.clips.reduce((m, c) => Math.max(m, c.start + c.dur), 0);
  const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
  const timeAt = (clientX) => (clientX - track.getBoundingClientRect().left) / S.pps;     // the track is scrolled with its scroller

  // where a clip of `dur` seconds that wants to start at `start` can go without overlapping the others (ignoring `skip`): {start, dur}, or null
  function fit(start, dur, skip) {
    const others = sorted().filter((c) => c !== skip);
    start = Math.max(0, start);
    for (const c of others) if (start < c.start + c.dur && start + dur > c.start) {
      if (start >= c.start) start = c.start + c.dur;                      // it begins inside c: after it
      else dur = c.start - start;                                          // it runs into c: shorter
    }
    const next = others.find((c) => c.start >= start);
    if (next) dur = Math.min(dur, next.start - start);
    return dur >= MIN_SECONDS - 1e-9 ? {start, dur} : null;
  }

  function gradient(clip) {
    const parts = clip.idx.map((i, k) => [ctx.palette[S.sources[i].cluster] || ctx.theme.line, clip.lam[k]]).filter((p) => p[1] > 0.001);
    if (parts.length < 2) return parts.length ? parts[0][0] : ctx.theme.line;
    const total = parts.reduce((s, p) => s + p[1], 0);
    let at = 0;
    const stops = parts.map(([colour, w]) => { const a = at / total * 100; at += w; return `${colour} ${a.toFixed(1)}% ${(at / total * 100).toFixed(1)}%`; });
    return `linear-gradient(90deg, ${stops.join(', ')})`;
  }

  const title = (clip) => `${fmt(clip.start)}–${fmt(clip.start + clip.dur)} · ` +
    clip.idx.map((i, k) => `${S.sources[i].name} ${(100 * clip.lam[k]).toFixed(0)}%`).join(' + ');

  function render() {
    S.length = Math.max(S.length, Math.ceil(lastEnd() + 1));
    inner.style.width = Math.round(S.length * S.pps) + 'px';
    // the ruler: a mark every STEP seconds, the step chosen so that marks are at least 70 px apart
    const step = STEPS.find((s) => s * S.pps >= 70) || STEPS[STEPS.length - 1];
    ruler.innerHTML = '';
    for (let t = 0; t <= S.length + 1e-9; t += step) {
      const m = document.createElement('span');
      m.className = 'tick'; m.style.left = Math.round(t * S.pps) + 'px'; m.textContent = fmt(t);
      ruler.appendChild(m);
    }
    track.querySelectorAll('.clip').forEach((e) => e.remove());
    for (const clip of S.clips) {
      const e = document.createElement('div');
      e.className = 'clip' + (clip === selected ? ' sel' : '');
      e.style.left = Math.round(clip.start * S.pps) + 'px'; e.style.width = Math.max(6, Math.round(clip.dur * S.pps)) + 'px';
      e.style.background = gradient(clip); e.title = title(clip) + '\ndrag: move · edge: length · double-click: remove';
      e.innerHTML = `<span class="label">${clip.label}</span><span class="rs"></span>`;
      e.addEventListener('pointerdown', (ev) => down(ev, clip, e));
      e.addEventListener('dblclick', () => remove(clip));
      track.appendChild(e);
    }
    readout.textContent = S.clips.length ? `${S.clips.length} clip${S.clips.length > 1 ? 's' : ''} · ${fmt(lastEnd())}` : 'empty';
  }

  function remove(clip) { S.clips = S.clips.filter((c) => c !== clip); if (selected === clip) selected = null; render(); bus.emit('clips'); }

  // --- moving and resizing a clip: it keeps within its neighbours ---
  let drag = null;
  function down(ev, clip, e) {
    if (ev.button !== 0) return;
    selected = clip;
    const edge = e.getBoundingClientRect().right - ev.clientX <= EDGE_PX;
    e.setPointerCapture(ev.pointerId);
    drag = {clip, e, id: ev.pointerId, edge, x: ev.clientX, start: clip.start, dur: clip.dur, moved: false};
    track.querySelectorAll('.clip').forEach((n) => n.classList.toggle('sel', n === e));
    ev.preventDefault();
  }
  track.addEventListener('pointermove', (ev) => {
    const d = drag;
    if (!d || ev.pointerId !== d.id) return;
    if (!d.moved && Math.abs(ev.clientX - d.x) < 3) return;
    d.moved = true;
    const dt = (ev.clientX - d.x) / S.pps;
    const others = sorted().filter((c) => c !== d.clip);
    const prev = others.filter((c) => c.start < d.start).pop(), next = others.find((c) => c.start >= d.start + d.dur - 1e-9);
    const lo = prev ? prev.start + prev.dur : 0, hi = next ? next.start : Infinity;
    if (d.edge) d.clip.dur = Math.min(Math.max(MIN_SECONDS, d.dur + dt), hi - d.clip.start);
    else d.clip.start = Math.min(Math.max(lo, d.start + dt), hi - d.clip.dur);
    d.e.style.left = Math.round(d.clip.start * S.pps) + 'px'; d.e.style.width = Math.max(6, Math.round(d.clip.dur * S.pps)) + 'px';
    d.e.title = title(d.clip);
  });
  // the clip is drawn again only if it moved: a click that does not move leaves the element as it is, so that a double-click still reaches it
  const end = (ev) => { if (drag && ev.pointerId === drag.id) { const moved = drag.moved; drag = null; if (moved) { render(); bus.emit('clips'); } } };
  track.addEventListener('pointerup', end); track.addEventListener('pointercancel', end);
  window.addEventListener('keydown', (ev) => {
    if ((ev.key === 'Delete' || ev.key === 'Backspace') && selected && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) remove(selected);
  });

  ref(root, 'clear').addEventListener('click', () => { S.clips = []; selected = null; render(); bus.emit('clips'); });

  // --- what the playground uses ---
  const over = (x, y) => { const r = root.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; };
  const label = (snap) => {
    const best = snap.idx.reduce((b, i, k) => (snap.lam[k] > snap.lam[b] ? k : b), 0);
    const more = snap.idx.length - 1;
    return S.sources[snap.idx[best]].name + (more ? ` +${more}` : '');
  };
  // a clip for snap = {idx, lam, c}, starting at `t` seconds (or at the end of the piece); the clip, or null when there is no room
  function add(snap, t) {
    const spot = fit(t === undefined ? lastEnd() : t, DEFAULT_SECONDS, null);
    if (!spot) return null;
    const clip = {id: ++seq, start: spot.start, dur: spot.dur, idx: snap.idx.slice(), lam: snap.lam.slice(), c: snap.c.slice(), label: label(snap)};
    S.clips.push(clip); selected = clip;
    render(); bus.emit('clips');
    return clip;
  }
  ctx.timeline = {
    over,
    // while the playground's point is carried: a mark where it would land
    hover(x, y) {
      mark.hidden = !over(x, y);
      if (!mark.hidden) mark.style.left = Math.round(Math.max(0, timeAt(x)) * S.pps) + 'px';
    },
    leave() { mark.hidden = true; },
    // the point was released at (x, y): a clip there if that is on the timeline
    dropAt(x, y, snap) { mark.hidden = true; return over(x, y) && !!add(snap, Math.max(0, timeAt(x))); },
    append(snap) { return add(snap); },
    clips: () => S.clips,
  };
  render();
}

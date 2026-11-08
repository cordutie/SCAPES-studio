// The timeline: the piece from left to right. A clip is one embedding (a source, or a mix of sources: see core/mix.js) held for some
// seconds; drop a source or a dot of the playground on it to make one (3 s long), drag it to move it, its right edge to stretch or shrink
// it, double-click to remove it. Clips never overlap. Between two consecutive clips there is an interpolation: the embedding goes from the
// one to the other across the gap (slerp for now; with no gap it is a cut), marked with a symbol. The scale is automatic: the piece is
// always fitted to the width, with 10 seconds of room after the last clip. Generating renders from the start of the first clip to the end of the last one.
import {bus, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {labelOf, clusterOf} from '../core/mix.js';
import {isDefault} from '../core/curve.js';
import {header} from '../../shared/core/ui.js';

const CLIP_SECONDS = 3, GAP_SECONDS = 1.5, MIN_SECONDS = 0.5, EDGE_PX = 8;
const ROOM_SECONDS = 10;                                   // always free after the last clip
const MIN_SPAN = 12, MAX_PPS = 100, MIN_PPS = 1.5;      // the shortest stretch shown (s), and the limits of the scale (px per s)
const STEPS = [0.5, 1, 2, 5, 10, 15, 30, 60, 120];          // seconds between the marks of the ruler
const INTERPOLATE = '↝';                                     // between two clips: click it to open its interpolation

export function mount(root, ctx) {
  root.innerHTML = header('Timeline') + `<div class="tl-scroll" data-ref="scroll"><div class="tl-inner" data-ref="inner">
    <div class="ruler" data-ref="ruler"></div><div class="tl-track" data-ref="track"><div class="drop-mark" data-ref="mark" hidden></div></div></div></div>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<span class="readout" data-ref="readout"></span><button data-ref="clear" title="remove every clip">Clear</button>`;
  const scroll = ref(root, 'scroll'), inner = ref(root, 'inner'), ruler = ref(root, 'ruler'), track = ref(root, 'track'), mark = ref(root, 'mark');
  const readout = ref(root, 'readout');
  let selected = null, seq = 0, pps = 30;                    // pps: the scale, set by render() so that the piece fits

  const sorted = () => [...S.clips].sort((a, b) => a.start - b.start);
  const lastEnd = () => S.clips.reduce((m, c) => Math.max(m, c.start + c.dur), 0);
  const firstStart = () => S.clips.reduce((m, c) => Math.min(m, c.start), Infinity);
  const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
  const timeAt = (clientX) => (clientX - track.getBoundingClientRect().left) / pps;

  // the scale: the piece (and ROOM_SECONDS after it) fills the width, within limits
  function fitScale() {
    const width = scroll.clientWidth || 1000, span = Math.max(MIN_SPAN, lastEnd() + ROOM_SECONDS);
    pps = Math.min(MAX_PPS, Math.max(MIN_PPS, width / span));
    return span;
  }

  // where a clip of `dur` seconds that wants to start at `start` can go without overlapping the others (ignoring `skip`): {start, dur}, or null.
  // Pushed behind a clip it begins inside, it leaves GAP_SECONDS after it, so that there is room for the interpolation.
  function fit(start, dur, skip) {
    const others = sorted().filter((c) => c !== skip);
    start = Math.max(0, start);
    for (const c of others) if (start < c.start + c.dur && start + dur > c.start) {
      if (start >= c.start) start = c.start + c.dur + GAP_SECONDS;        // it begins inside c: after it
      else dur = c.start - start;                                          // it runs into c: shorter
    }
    const next = others.find((c) => c.start >= start);
    if (next) dur = Math.min(dur, next.start - start);
    return dur >= MIN_SECONDS - 1e-9 ? {start, dur} : null;
  }

  function gradient(clip) {
    const parts = clip.comp.map(([i, w]) => [ctx.palette[S.sources[i].cluster] || ctx.theme.line, w]).filter((p) => p[1] > 0.001);
    if (parts.length < 2) return parts.length ? parts[0][0] : ctx.theme.line;
    const total = parts.reduce((s, p) => s + p[1], 0);
    let at = 0;
    const stops = parts.map(([colour, w]) => { const a = at / total * 100; at += w; return `${colour} ${a.toFixed(1)}% ${(at / total * 100).toFixed(1)}%`; });
    return `linear-gradient(90deg, ${stops.join(', ')})`;
  }

  const title = (clip) => `${fmt(clip.start)}–${fmt(clip.start + clip.dur)} · ` +
    clip.comp.map(([i, w]) => `${S.sources[i].name} ${(100 * w).toFixed(0)}%`).join(' + ');

  function render() {
    const span = fitScale();
    inner.style.width = Math.round(span * pps) + 'px';
    // the ruler: a mark every STEP seconds, the step chosen so that marks are at least 70 px apart
    const step = STEPS.find((s) => s * pps >= 70) || STEPS[STEPS.length - 1];
    ruler.innerHTML = '';
    for (let t = 0; t <= span + 1e-9; t += step) {
      const m = document.createElement('span');
      m.className = 'tick'; m.style.left = Math.round(t * pps) + 'px'; m.textContent = fmt(t);
      ruler.appendChild(m);
    }
    track.querySelectorAll('.clip, .interp').forEach((e) => e.remove());
    for (const clip of S.clips) {
      const e = document.createElement('div');
      e.className = 'clip' + (clip === selected ? ' sel' : '');
      e.style.left = Math.round(clip.start * pps) + 'px'; e.style.width = Math.max(6, Math.round(clip.dur * pps)) + 'px';
      e.style.background = gradient(clip); e.title = title(clip) + '\ndrag: move · edge: length · double-click: remove';
      e.innerHTML = `<span class="label">${clip.label}</span><span class="rs"></span>`;
      e.addEventListener('pointerdown', (ev) => down(ev, clip, e));
      e.addEventListener('dblclick', () => remove(clip));
      track.appendChild(e);
    }
    // between each pair of consecutive clips: the interpolation
    const list = sorted();
    list.slice(1).forEach((b, k) => {
      const a = list[k], gap = b.start - (a.start + a.dur);
      const e = document.createElement('div');
      e.className = 'interp' + (gap < 0.01 ? ' cut' : '') + (isDefault(a.curve) ? '' : ' custom') + (S.interp === a.id ? ' open' : '');
      e.style.left = Math.round(((a.start + a.dur + b.start) / 2) * pps) + 'px';
      e.textContent = INTERPOLATE;
      e.title = (gap < 0.01 ? 'no gap: a cut from the one to the other (leave a gap to interpolate)'
                            : `interpolation (slerp) from "${a.label}" to "${b.label}" across ${gap.toFixed(1)} s`) + '\nclick: its speed';
      e.addEventListener('click', () => open(a));
      track.appendChild(e);
    });
    readout.textContent = S.clips.length ? `${S.clips.length} clip${S.clips.length > 1 ? 's' : ''} · ${fmt(lastEnd() - firstStart())}` : 'empty';
  }

  // the interpolation after clip a, in the place of the playground (a second click closes it)
  function open(a) {
    S.interp = S.interp === a.id ? null : a.id; S.tab = 'sources';
    bus.emit('interp'); bus.emit('tab'); render();
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
    const dt = (ev.clientX - d.x) / pps;                        // the scale does not change while a clip is held: it refits on release
    const others = sorted().filter((c) => c !== d.clip);
    const prev = others.filter((c) => c.start < d.start).pop(), next = others.find((c) => c.start >= d.start + d.dur - 1e-9);
    const lo = prev ? prev.start + prev.dur : 0, hi = next ? next.start : Infinity;
    if (d.edge) d.clip.dur = Math.min(Math.max(MIN_SECONDS, d.dur + dt), hi - d.clip.start);
    else d.clip.start = Math.min(Math.max(lo, d.start + dt), hi - d.clip.dur);
    d.e.style.left = Math.round(d.clip.start * pps) + 'px'; d.e.style.width = Math.max(6, Math.round(d.clip.dur * pps)) + 'px';
    d.e.title = title(d.clip);
  });
  // the clip is drawn again only if it moved: a click that does not move leaves the element as it is, so that a double-click still reaches it
  const end = (ev) => { if (drag && ev.pointerId === drag.id) { const moved = drag.moved; drag = null; if (moved) { render(); bus.emit('clips'); } } };
  track.addEventListener('pointerup', end); track.addEventListener('pointercancel', end);
  window.addEventListener('keydown', (ev) => {
    if ((ev.key === 'Delete' || ev.key === 'Backspace') && selected && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) remove(selected);
  });
  window.addEventListener('resize', render);

  ref(root, 'clear').addEventListener('click', () => { S.clips = []; S.interp = null; bus.emit('interp'); selected = null; render(); bus.emit('clips'); });

  // --- what the playground and the sources use ---
  const over = (x, y) => { const r = root.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; };
  // a clip for item = {comp}, CLIP_SECONDS long, starting at `t` seconds (or after the end of the piece); the clip, or null when there is no room
  function add(item, t) {
    const spot = fit(t === undefined ? (S.clips.length ? lastEnd() + GAP_SECONDS : 0) : t, CLIP_SECONDS, null);
    if (!spot) return null;
    const clip = {id: ++seq, start: spot.start, dur: spot.dur, comp: item.comp.map((p) => p.slice()), label: labelOf(item.comp)};
    clip.colour = clusterOf(clip.comp);
    S.clips.push(clip); selected = clip;
    render(); bus.emit('clips');
    return clip;
  }
  ctx.timeline = {
    over,
    // while something is carried: a mark where it would land
    hover(x, y) {
      mark.hidden = !over(x, y);
      if (!mark.hidden) mark.style.left = Math.round(Math.max(0, timeAt(x)) * pps) + 'px';
    },
    leave() { mark.hidden = true; },
    // released at (x, y): a clip there if that is on the timeline
    dropAt(x, y, item) { mark.hidden = true; return over(x, y) && !!add(item, Math.max(0, timeAt(x))); },
    append(item) { return add(item); },
    clips: () => S.clips,
    scale: () => pps,
    span: () => inner.getBoundingClientRect().width / pps,                  // seconds on show
    // the clip after `clip` in time, or null
    next: (clip) => sorted().find((c) => c.start >= clip.start + clip.dur - 1e-9 && c !== clip) || null,
    // the speed of the interpolation after `clip` was edited (curve = [[t, y], ...], or null for the default)
    setCurve(clip, curve) { if (curve === null) delete clip.curve; else clip.curve = curve; render(); bus.emit('clips'); },
    refresh: render,
  };
  bus.on('boot', render);
  bus.on('clips', () => {                                        // the open interpolation goes when its clip, or the next one, does
    const a = S.clips.find((c) => c.id === S.interp);
    if (S.interp !== null && !(a && ctx.timeline.next(a))) { S.interp = null; bus.emit('interp'); render(); }
  });
  render();
}

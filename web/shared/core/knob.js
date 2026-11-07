// A knob, in the way of a synth: drag up or down to turn it (Shift: finer), double-click to put it back to its default, and
// click its number to type a value. The number sits under the knob (or at its right in the inline form of the panel headers).
//
//   const k = createKnob({label, map, value, def, format, parse, step, onChange, size, inline});
//   parent.append(k.el);  k.set(v) (no onChange)  k.get()
// map: {toPos, fromPos, min, max} (core/maps.js). format(v) -> text. parse(text) -> v (NaN: the typing is ignored).
// onChange(v) is called at every change; onCommit(v) only when the change is over: a drag released, a typed value, a double-click, or
// 250 ms after the last turn of the wheel (for what is heavy to apply, like NFE).
// step: the value is rounded to a multiple of it. The look is in theme.css (.knob) and the sizes below.
import {linear} from './maps.js';

const SWEEP = 270;                  // degrees of travel
const PER_PX = 1 / 180;             // position per pixel of drag; Shift: a fifth of it

const NS = 'http://www.w3.org/2000/svg';
const point = (cx, cy, r, deg) => [cx + r * Math.sin(deg * Math.PI / 180), cy - r * Math.cos(deg * Math.PI / 180)];
function arc(cx, cy, r, a0, a1) {
  const [x0, y0] = point(cx, cy, r, a0), [x1, y1] = point(cx, cy, r, a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

export function createKnob(o) {
  const map = o.map || linear(o.min ?? 0, o.max ?? 1), size = o.size || 52;
  const format = o.format || ((v) => String(+v.toFixed(2))), parse = o.parse || parseFloat;
  const clampV = (v) => Math.min(map.max, Math.max(map.min, v));
  const snap = (v) => clampV(o.step ? Math.round(v / o.step) * o.step : v);
  const def = o.def ?? o.value;
  let value = snap(o.value), dragging = null, pending = false, timer = null;
  function fireCommit() { timer = null; if (pending && o.onCommit) { pending = false; o.onCommit(value); } }

  const el = document.createElement('div');
  el.className = 'knob' + (o.inline ? ' inline' : '');
  el.innerHTML = `<svg class="dial" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"></svg>
    <span class="num" title="click to type a value"></span>${o.label && !o.inline ? `<span class="lab">${o.label}</span>` : ''}`;
  const svg = el.querySelector('svg'), num = el.querySelector('.num');
  const mk = (cls, attrs) => { const e = document.createElementNS(NS, cls.tag); e.setAttribute('class', cls.cls); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); svg.appendChild(e); return e; };
  const c = size / 2, r = size / 2 - 5, a0 = -SWEEP / 2;
  mk({tag: 'path', cls: 'track'}, {d: arc(c, c, r, a0, -a0), 'stroke-width': 3});
  const fill = mk({tag: 'path', cls: 'fill'}, {'stroke-width': 3});
  const [dx, dy] = point(c, c, r + 0.5, a0 + SWEEP * map.toPos(def));
  mk({tag: 'circle', cls: 'defmark'}, {cx: dx, cy: dy, r: 1.4});
  const needle = mk({tag: 'line', cls: 'needle'}, {'stroke-width': 2.2});
  el.title = (o.label || '') + ' (double-click: reset)';

  function paint() {
    const t = Math.min(1, Math.max(0, map.toPos(value))), a = a0 + SWEEP * t;
    fill.setAttribute('d', t > 0.002 ? arc(c, c, r, a0, a) : '');
    const [x1, y1] = point(c, c, r - 8, a), [x2, y2] = point(c, c, r + 1, a);
    needle.setAttribute('x1', x1); needle.setAttribute('y1', y1); needle.setAttribute('x2', x2); needle.setAttribute('y2', y2);
    num.textContent = format(value);
  }
  function setValue(v, notify, slow) {
    v = snap(v);
    if (v === value && notify) return;
    value = v; paint();
    if (!notify) return;
    if (o.onChange) o.onChange(value);
    if (o.onCommit) {
      pending = true;
      if (slow) { clearTimeout(timer); timer = setTimeout(fireCommit, 250); } else if (!dragging) fireCommit();
    }
  }

  svg.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    svg.setPointerCapture(e.pointerId);
    dragging = {id: e.pointerId, y: e.clientY, x: e.clientX, t: map.toPos(Number.isFinite(value) ? value : map.min === -Infinity ? map.fromPos(0) : map.min)};
    dragging.t = Math.min(1, Math.max(0, map.toPos(value)));
    el.classList.add('active');
  });
  svg.addEventListener('pointermove', (e) => {
    if (!dragging || e.pointerId !== dragging.id) return;
    const gain = e.shiftKey ? PER_PX / 5 : PER_PX;
    const t = Math.min(1, Math.max(0, dragging.t + ((dragging.y - e.clientY) + (e.clientX - dragging.x)) * gain));
    setValue(map.fromPos(t), true);
  });
  const end = (e) => { if (dragging && e.pointerId === dragging.id) { dragging = null; el.classList.remove('active'); fireCommit(); } };
  svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
  svg.addEventListener('dblclick', () => setValue(def, true));
  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const t = Math.min(1, Math.max(0, map.toPos(value) - Math.sign(e.deltaY) * (e.shiftKey ? 0.004 : 0.02)));
    setValue(map.fromPos(t), true, true);
  }, {passive: false});

  // click the number: type a value (Enter keeps it, Escape or a click away leaves it)
  num.addEventListener('click', () => {
    const input = document.createElement('input');
    input.className = 'num-edit'; input.value = format(value);
    num.replaceWith(input); input.focus(); input.select();
    let done = false;
    const finish = (keep) => {
      if (done) return; done = true;
      if (keep) { const v = parse(input.value); if (!Number.isNaN(v)) setValue(v, true); }
      input.replaceWith(num); paint();
    };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') finish(true); else if (e.key === 'Escape') finish(false); });
    input.addEventListener('blur', () => finish(true));
  });

  paint();
  return {el, get: () => value, set: (v) => setValue(v, false)};
}

// The FX panel. It draws whatever the chain holds (audio/fx/chain.js), so a new effect needs no change here: four cells in the
// order of the chain (the number at the top left of each), each with a power switch, a grip, and its knobs (the EQ has faders).
// Drag a cell by its head (the grip at the right only hints at it: hide it with --grip-display in theme.css) onto another place.
import {ref} from '../../shared/core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {header} from '../../shared/core/ui.js';

export function mount(root, ctx) {
  root.innerHTML = header('FX') + `<div class="cells" data-ref="cells"></div>`;
  const cells = ref(root, 'cells');
  if (!ctx.player) { cells.textContent = 'audio is not available in this browser'; return; }
  const chain = ctx.player.chain;

  // one fader of the EQ; double-click puts it back to 0
  function fader(fx, p) {
    const input = document.createElement('input');
    input.type = 'range'; input.min = p.min; input.max = p.max; input.step = p.step; input.value = fx.values[p.id];
    input.title = p.label;
    input.addEventListener('input', () => chain.setParam(fx.id, p.id, parseFloat(input.value)));
    input.addEventListener('dblclick', () => { input.value = p.value; chain.setParam(fx.id, p.id, p.value); });
    return input;
  }

  function cell(fx, index) {
    const el = document.createElement('div');
    el.className = 'fx' + (fx.enabled ? '' : ' off');
    el.dataset.id = fx.id;
    el.innerHTML = `<div class="fx-head"><span class="order">${index + 1}</span><span class="title">${fx.name}</span>
      <button data-act="power" class="${fx.enabled ? 'on' : ''}" title="${fx.enabled ? 'on' : 'off'}">⏻</button><span class="grip" title="drag to reorder"></span></div>`;
    el.querySelector('[data-act=power]').addEventListener('click', () => chain.setEnabled(fx.id, !fx.enabled));
    const body = document.createElement('div');
    if (fx.layout === 'bars') {
      body.className = 'bars';
      fx.params.forEach((p) => {
        const band = document.createElement('div');
        band.className = 'band';
        const name = document.createElement('span');
        name.textContent = p.label;
        band.append(fader(fx, p), name);
        body.appendChild(band);
      });
    } else {
      body.className = 'knobs';
      fx.params.forEach((p) => {
        const k = createKnob({label: p.label, map: p.map, value: fx.values[p.id], def: p.value, format: p.format, parse: p.parse,
                              step: p.step, size: 64, onChange: (v) => chain.setParam(fx.id, p.id, v)});
        body.appendChild(k.el);
      });
    }
    el.appendChild(body);
    el.querySelector('.fx-head').addEventListener('pointerdown', (e) => startDrag(e, el, fx.id));
    return el;
  }

  // --- reorder: the cell follows the pointer; the cell under it is the new place ---
  let drag = null;
  function startDrag(e, el, id) {
    if (e.button !== 0 || e.target.closest('button')) return;
    drag = {el, id, x: e.clientX, y: e.clientY, moved: false, rects: [...cells.children].map((c) => c.getBoundingClientRect()), to: null,
            from: [...cells.children].indexOf(el)};
    el.setPointerCapture(e.pointerId); drag.pid = e.pointerId;
  }
  cells.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.pid) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true;
    drag.el.classList.add('dragging');
    drag.el.style.transform = `translate(${dx}px, ${dy}px)`;
    const at = drag.rects.findIndex((r) => e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom);
    drag.to = at;
    [...cells.children].forEach((c, i) => c.classList.toggle('target', i === at && at !== drag.from));
  });
  function endDrag(e) {
    if (!drag || e.pointerId !== drag.pid) return;
    const d = drag; drag = null;
    d.el.classList.remove('dragging'); d.el.style.transform = '';
    [...cells.children].forEach((c) => c.classList.remove('target'));
    if (d.moved && d.to >= 0 && d.to !== d.from) chain.place(d.id, d.to);
  }
  cells.addEventListener('pointerup', endDrag); cells.addEventListener('pointercancel', endDrag);

  function render(state) {
    cells.innerHTML = '';
    state.effects.forEach((fx, i) => cells.appendChild(cell(fx, i)));
  }
  chain.onChange(render);
  render(chain.state());
}

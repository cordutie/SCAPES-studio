// The model panel of the Score page: the model, NFE, CFG and the seed of the next generation, and the Generate button (which cannot do
// anything yet: generating the piece is the next step). The same knobs as the model panel of Live, minus what is only for playing in real time.
import {ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {linear, log} from '../../shared/core/maps.js';
import {header} from '../../shared/core/ui.js';

export function mount(root, ctx) {
  const g = ctx.generation;
  root.innerHTML = header('Model', 'Score model') + `<div class="set">
    <button class="model-btn" data-ref="modelbtn" title="choose another model"></button>
    <div class="set-knobs" data-ref="knobs"></div>
    <div class="set-go"><input type="number" data-ref="seed" min="0" max="999999" step="1" value="${S.gen.seed}" title="the seed: the same score with the same seed makes the same piece">
      <button data-ref="dice" title="a new seed">⚄</button><button class="go" data-ref="generate" disabled title="generating the piece is the next step">Generate</button></div></div>`;
  const modelBtn = ref(root, 'modelbtn'), seed = ref(root, 'seed');
  modelBtn.textContent = S.model + ' ▾';
  ref(root, 'knobs').append(
    createKnob({label: 'NFE', map: log(g.nfe_range[0], g.nfe_range[1]), value: S.gen.nfe, def: g.nfe, step: 1, size: 44,
                format: (v) => String(Math.round(v)), onChange: (v) => { S.gen.nfe = Math.round(v); }}).el,
    createKnob({label: 'CFG', map: linear(g.cfg_range[0], g.cfg_range[1]), value: S.gen.cfg, def: g.cfg, step: g.cfg_step, size: 44,
                format: (v) => v.toFixed(1), onChange: (v) => { S.gen.cfg = v; }}).el);
  seed.addEventListener('change', () => { S.gen.seed = Math.max(0, Math.min(999999, Math.round(+seed.value || 0))); seed.value = S.gen.seed; });
  ref(root, 'dice').addEventListener('click', () => { S.gen.seed = Math.floor(Math.random() * 1000000); seed.value = S.gen.seed; });

  // the model menu: a list above the button (outside the panel, which clips what overflows it); a model reloads the page on its sources
  let menu = null;
  const close = () => { if (menu) { menu.remove(); menu = null; } };
  modelBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (menu) { close(); return; }
    menu = document.createElement('div');
    menu.className = 'menu';
    for (const m of ctx.models) {
      const item = document.createElement('button');
      item.className = m.name === S.model ? 'current' : '';
      item.innerHTML = `${m.name}<small>${m.codec} · ${m.rate.toFixed(1)} Hz${m.name === S.model ? ' · shown' : ''}</small>`;
      item.addEventListener('click', () => { if (m.name !== S.model) location.search = '?model=' + encodeURIComponent(m.name); close(); });
      menu.appendChild(item);
    }
    ctx.root.appendChild(menu);
    const b = modelBtn.getBoundingClientRect(), r = ctx.root.getBoundingClientRect();
    menu.style.left = (b.left - r.left) + 'px'; menu.style.bottom = (r.bottom - b.top + 4) + 'px'; menu.style.top = 'auto';
  });
  document.addEventListener('click', close);
}

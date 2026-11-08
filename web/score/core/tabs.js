// The two tabs at the top left of the Score page, Sources and Takes: both blocks share the same place and each draws the pair in its header.
import {bus} from '../../shared/core/state.js';
import {S} from './state.js';

export function addTabs(root, tools) {
  const box = document.createElement('span');
  box.className = 'tabs';
  box.innerHTML = `<button data-tab="sources">Sources</button><button data-tab="takes">Takes</button>`;
  tools.prepend(box);
  const sync = () => {
    root.hidden = root.dataset.block !== S.tab;
    box.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.tab === S.tab));
    box.querySelector('[data-tab=takes]').textContent = S.takes.length ? `Takes (${S.takes.length})` : 'Takes';
  };
  box.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { S.tab = b.dataset.tab; bus.emit('tab'); }));
  bus.on('tab', sync); bus.on('takes', sync); bus.on('boot', sync);
  sync();
}

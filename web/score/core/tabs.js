// The two views of the Score page. Sources + playground is the first; Takes + atlas the second. The two tabs sit in the header of the
// left block of each view (sources, takes), and the right block (playground, atlas) follows.
import {bus} from '../../shared/core/state.js';
import {S} from './state.js';

const VIEW = {sources: 'sources', playground: 'sources', interpolation: 'sources', takes: 'takes', atlas: 'takes'};

// hides a block when it is not of the view on show; call it for every block that has a view
export function followTab(root) {
  const block = root.dataset.block;
  // the interpolation panel takes the place of the playground while a symbol of the timeline is open
  const sync = () => { root.hidden = VIEW[block] !== S.tab || (block === 'playground' && S.interp !== null) || (block === 'interpolation' && S.interp === null); };
  bus.on('tab', sync); bus.on('boot', sync); bus.on('interp', sync);
  sync();
}

export function addTabs(root, tools) {
  const box = document.createElement('span');
  box.className = 'tabs';
  box.innerHTML = `<button data-tab="sources">Sources</button><button data-tab="takes">Takes</button>`;
  tools.prepend(box);
  const sync = () => {
    box.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.tab === S.tab));
    box.querySelector('[data-tab=takes]').textContent = S.takes.length ? `Takes (${S.takes.length})` : 'Takes';
  };
  box.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { S.tab = b.dataset.tab; bus.emit('tab'); }));
  bus.on('tab', sync); bus.on('takes', sync); bus.on('boot', sync);
  followTab(root);
  sync();
}

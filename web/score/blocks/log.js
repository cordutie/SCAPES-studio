// The log of the Score page: what the page does and, once there is a generation, its report. The top line says where the piece stands.
// ctx.log(text, warn) writes a line.
import {bus, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {header} from '../../shared/core/ui.js';

const MAX_LINES = 200;
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

export function mount(root, ctx) {
  root.innerHTML = header('Log') + `<div class="m-log"><div class="live" data-ref="live"></div><div class="lines" data-ref="lines"></div></div>`;
  const live = ref(root, 'live'), lines = ref(root, 'lines');
  const stamp = () => new Date().toTimeString().slice(0, 8);
  ctx.log = (text, warn) => {
    const row = document.createElement('div');
    if (warn) row.className = 'warn';
    row.textContent = stamp() + '  ' + text;
    lines.appendChild(row);
    while (lines.children.length > MAX_LINES) lines.firstChild.remove();
    lines.scrollTop = lines.scrollHeight;
  };
  const status = () => {
    const clips = S.clips.length, end = S.clips.reduce((m, c) => Math.max(m, c.start + c.dur), 0);
    live.textContent = clips ? `${clips} clip${clips > 1 ? 's' : ''} · the piece lasts ${fmt(end)}` : 'no clips yet · drag the point of the playground onto the timeline';
  };
  bus.on('clips', status); bus.on('boot', () => {
    status();
    ctx.log(`model ${S.model}`);
    ctx.log(`${S.sources.length} sources from ${new Set(S.sources.map((s) => s.cluster)).size} clusters · ${S.takes.length} take${S.takes.length === 1 ? '' : 's'}`);
  });
  status();
}

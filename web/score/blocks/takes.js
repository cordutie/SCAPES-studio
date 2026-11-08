// The takes: what Score generated, newest first. Play one, download it as a wav, or remove it. It shares its place with the sources (a tab).
import {bus, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {addTabs} from '../core/tabs.js';
import {header} from '../../shared/core/ui.js';

const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

export function mount(root, ctx) {
  root.innerHTML = header('Takes') + `<div class="takes" data-ref="list"></div>`;
  addTabs(root, ref(root, 'tools'));
  const list = ref(root, 'list');
  let audio = null, playing = null;

  function stop() { if (audio) { audio.pause(); audio = null; } playing = null; ctx.atlas.stop(); }
  // play: the atlas shows the path of the take and follows the sound along it
  async function play(take) {
    const same = playing === take.id;
    stop();
    if (!same) {
      playing = take.id;
      const a = audio = new Audio(ctx.takesUrl + take.id + '.wav');
      a.addEventListener('ended', () => { if (audio === a) { playing = null; audio = null; ctx.atlas.stop(); render(); } });
      a.play().catch(() => {});
      let trace = null;
      try { trace = await ctx.api.trace({id: take.id}); } catch (e) { trace = null; }
      if (audio === a) ctx.atlas.follow(a, trace);
    }
    render();
  }

  function render() {
    list.innerHTML = '';
    if (!S.takes.length) {
      list.innerHTML = `<div class="empty">Nothing generated yet. Arrange clips on the timeline and press Generate: the pieces you make are kept here.</div>`;
      return;
    }
    for (const take of S.takes) {
      const row = document.createElement('div');
      row.className = 'take' + (playing === take.id ? ' playing' : '');
      row.dataset.id = take.id;
      row.innerHTML = `<button class="tplay" title="play · stop">${playing === take.id ? '■' : '▶'}</button>
        <span class="tname"></span><span class="tmeta"></span>
        <a class="tdown" title="download this sound as a wav" download>↓</a><button class="tdel" title="remove it for good">✕</button>`;
      row.querySelector('.tname').textContent = take.name;
      row.querySelector('.tmeta').textContent = `${fmt(take.seconds)} · NFE ${take.nfe} · CFG ${Number(take.cfg).toFixed(1)} · seed ${take.seed} · ${take.model} · ${take.created}`;
      const a = row.querySelector('a');
      a.href = ctx.takesUrl + take.id + '.wav'; a.download = take.id + '.wav';
      row.querySelector('.tplay').addEventListener('click', () => play(take));
      row.querySelector('.tdel').addEventListener('click', async () => {
        if (playing === take.id) stop();
        try { S.takes = await ctx.api.deleteTake({id: take.id}); } catch (e) { ctx.log('could not remove the take: ' + e, true); return; }
        bus.emit('takes');
      });
      list.appendChild(row);
    }
  }

  // what the generator calls when it has made a take
  ctx.takesBlock = {
    async refresh() { S.takes = await ctx.api.takes(); bus.emit('takes'); },
    stop,
  };
  bus.on('takes', render); bus.on('boot', render);
  render();
}

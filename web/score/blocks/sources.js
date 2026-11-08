// The semantic sources of the Score page: the representatives of the clusters of the model, grouped by cluster in the colour of the cluster.
// Click one to hear the audio it comes from; drag one onto the semantic playground to place it there.
import {bus, ref} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {addTabs} from '../core/tabs.js';
import {header} from '../../shared/core/ui.js';

export function mount(root, ctx) {
  root.innerHTML = header('Semantic sources', 'Score sources') + `<div class="sources" data-ref="list"></div>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<span class="readout" data-ref="model" title="the model whose sources these are"></span>`;
  addTabs(root, tools);
  const list = ref(root, 'list'), modelName = ref(root, 'model');

  // --- the audio of a source: one at a time ---
  let audio = null, playing = null;
  function preview(i) {
    if (audio) { audio.pause(); audio = null; }
    list.querySelectorAll('.src.playing').forEach((b) => b.classList.remove('playing'));
    playing = i;
    audio = new Audio(S.sources[i].url);
    audio.addEventListener('ended', () => { list.querySelector(`[data-i="${i}"]`)?.classList.remove('playing'); });
    audio.play().catch(() => {});
    list.querySelector(`[data-i="${i}"]`)?.classList.add('playing');
    return audio;
  }
  ctx.preview = preview;

  function build() {
    modelName.textContent = S.model;
    list.innerHTML = '';
    const byCluster = new Map();
    S.sources.forEach((s, i) => { if (!byCluster.has(s.cluster)) byCluster.set(s.cluster, []); byCluster.get(s.cluster).push(i); });
    for (const [k, ids] of [...byCluster].sort((a, b) => a[0] - b[0])) {
      const group = document.createElement('div');
      group.className = 'group';
      group.innerHTML = `<div class="gname" style="color:${ctx.palette[k] || ctx.theme.line}"></div>`;
      group.firstChild.textContent = S.names[k] || `cluster ${k}`;
      for (const i of ids) {
        const b = document.createElement('button');
        b.className = 'src'; b.dataset.i = i; b.textContent = S.sources[i].name;
        b.style.background = ctx.palette[k] || ctx.theme.line;
        b.title = 'click: hear it · drag onto the playground to place it';
        b.addEventListener('pointerdown', (e) => down(e, i, b));
        b.addEventListener('pointermove', move); b.addEventListener('pointerup', up); b.addEventListener('pointercancel', cancel);
        group.appendChild(b);
      }
      list.appendChild(group);
    }
    mark();
  }
  const mark = () => list.querySelectorAll('.src').forEach((b) => b.classList.toggle('placed', S.dots[+b.dataset.i] !== null));

  // --- drag onto the playground (a press that does not move is a click: it plays) ---
  let bg = null;
  function down(e, i, b) {
    if (e.button !== 0) return;
    b.setPointerCapture(e.pointerId);
    bg = {i, id: e.pointerId, x: e.clientX, y: e.clientY, ghost: null, moved: false};
  }
  function move(e) {
    if (!bg || e.pointerId !== bg.id) return;
    if (!bg.moved && Math.hypot(e.clientX - bg.x, e.clientY - bg.y) < 5) return;
    bg.moved = true;
    if (!bg.ghost) {
      bg.ghost = document.createElement('div');
      bg.ghost.className = 'ghost';
      bg.ghost.style.borderColor = ctx.palette[S.sources[bg.i].cluster] || ctx.theme.line;
      ctx.root.appendChild(bg.ghost);
    }
    const a = ctx.root.getBoundingClientRect();
    bg.ghost.style.left = (e.clientX - a.left) + 'px'; bg.ghost.style.top = (e.clientY - a.top) + 'px';
  }
  function up(e) {
    if (!bg || e.pointerId !== bg.id) return;
    const g = bg; bg = null;
    if (g.ghost) g.ghost.remove();
    if (!g.moved) { preview(g.i); return; }
    const r = ctx.playground.canvas.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
    ctx.playground.place(g.i, ctx.playground.planeRaw(e));
  }
  function cancel(e) { if (bg && e.pointerId === bg.id) { if (bg.ghost) bg.ghost.remove(); bg = null; } }

  bus.on('boot', build); bus.on('dots', mark);
}

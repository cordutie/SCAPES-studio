// The semantic sources panel: the cluster blocks, named after the sounds they hold. Drag a block onto the semantic playground to
// place its dot. Double-click a block to rename it: the name is kept in the model's folder for the next sessions.
import {S, bus, clampP, ref} from '../../shared/core/state.js';
import {header} from '../../shared/core/ui.js';

export function mount(root, ctx) {
  root.innerHTML = header('Semantic sources') + `<div class="blocks" data-ref="blocks"></div>`;
  ref(root, 'tools').innerHTML = `<button data-ref="clear">Clear</button>`;
  const box = ref(root, 'blocks');

  function mark() { box.querySelectorAll('button').forEach((b, i) => b.classList.toggle('cur', i === S.cur)); }

  function build() {
    box.innerHTML = '';
    S.names.forEach((name, i) => {
      const b = document.createElement('button');
      b.textContent = name;
      b.title = 'drag onto the playground · double-click to rename';
      b.style.background = ctx.palette[i] || ctx.theme.line;
      b.addEventListener('click', () => { S.cur = i; mark(); });
      b.addEventListener('dblclick', () => rename(i, b));
      b.addEventListener('pointerdown', (e) => down(e, i, b));
      b.addEventListener('pointermove', move);
      b.addEventListener('pointerup', up);
      b.addEventListener('pointercancel', cancel);
      box.appendChild(b);
    });
    mark();
  }

  // the block becomes a text box; Enter keeps the new name (empty: the original one), Escape leaves it
  function rename(i, b) {
    cancel({pointerId: bg ? bg.id : -1});
    const input = document.createElement('input');
    input.className = 'rename'; input.value = S.names[i]; input.maxLength = 40;
    input.style.background = b.style.background;
    b.replaceWith(input); input.focus(); input.select();
    let done = false;
    const finish = async (keep) => {
      if (done) return; done = true;
      if (keep) {
        try { S.names[i] = (await ctx.api.rename({index: i, name: input.value})).name; } catch (e) { /* keeps the old name */ }
      }
      build(); bus.emit('dots');                         // the plane writes the names next to the dots
    };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') finish(true); else if (e.key === 'Escape') finish(false); });
    input.addEventListener('blur', () => finish(true));
  }

  // the drag in progress: the block, the pointer and the ghost ring that follows it (null until it moves)
  let bg = null;
  function down(e, i, b) {
    if (e.button !== 0) return;
    S.cur = i; mark();
    b.setPointerCapture(e.pointerId);
    bg = {i, id: e.pointerId, ghost: null};
  }
  function move(e) {
    if (!bg || e.pointerId !== bg.id) return;
    if (!bg.ghost) {
      bg.ghost = document.createElement('div');
      bg.ghost.className = 'ghost';
      bg.ghost.style.borderColor = ctx.palette[bg.i] || ctx.theme.line;
      ctx.root.appendChild(bg.ghost);
    }
    const a = ctx.root.getBoundingClientRect();
    bg.ghost.style.left = (e.clientX - a.left) + 'px';
    bg.ghost.style.top = (e.clientY - a.top) + 'px';
  }
  function dropGhost() { if (bg && bg.ghost) bg.ghost.remove(); }
  // released inside the plane: the block's dot goes there. A drop never moves the control point.
  function up(e) {
    if (!bg || e.pointerId !== bg.id) return;
    const i = bg.i;
    dropGhost(); bg = null;
    const r = ctx.plane.canvas.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
    S.dots[i] = clampP(ctx.plane.planeRaw(e));
    bus.emit('dots'); ctx.live.request();
  }
  function cancel(e) { if (bg && e.pointerId === bg.id) { dropGhost(); bg = null; } }

  ref(root, 'clear').addEventListener('click', () => {
    S.dots = Array(S.K).fill(null);
    S.sel = null; S.lastLive = null;
    bus.emit('dots'); ctx.live.request();
  });

  bus.on('boot', build);
}

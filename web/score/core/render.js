// Generating the piece: sends the timeline to the server, follows the job (a progress and the lines of its report, which go to the log) and,
// when it ends, brings the new take. ctx.render.run() starts it; S.rendering is set while it goes (event 'render').
import {bus} from '../../shared/core/state.js';
import {S} from './state.js';

const POLL_MS = 400;

export function createRender(ctx) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function run() {
    if (S.rendering || !S.clips.length) return;
    S.rendering = {progress: 0}; bus.emit('render');
    ctx.log(`generating ${S.clips.length} clip${S.clips.length > 1 ? 's' : ''} with ${S.model}`);
    try {
      const clips = S.clips.map((c) => ({start: c.start, dur: c.dur, comp: c.comp, curve: c.curve || null}));
      const r = await ctx.api.render({model: S.model, clips, nfe: S.gen.nfe, cfg: S.gen.cfg, seed: S.gen.seed});
      if (!r.ok) { ctx.log(r.error || 'could not start', true); return; }
      let seen = 0, st;
      do {
        await sleep(POLL_MS);
        st = await ctx.api.renderStatus();
        for (; seen < st.lines.length; seen++) ctx.log(st.lines[seen].text, st.lines[seen].warn);
        S.rendering.progress = st.progress; bus.emit('render');
      } while (st.running);
      if (st.take) await ctx.takesBlock.refresh();
    } catch (e) {
      ctx.log('generation failed: ' + e, true);
    } finally {
      S.rendering = null; bus.emit('render');
    }
  }
  return {run};
}

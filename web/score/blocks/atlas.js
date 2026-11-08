// The atlas of the Score page, in the place of the playground while the takes are on show: the shared 3-D view with the path a take
// followed through it (a line) and, while the take plays, where the sound is on that path (an orange dot, as in Live).
import {bus} from '../../shared/core/state.js';
import {S} from '../core/state.js';
import {mountGlobe} from '../../shared/core/globe.js';
import {followTab} from '../core/tabs.js';

export function mount(root, ctx) {
  let trace = null, audio = null, raf = 0;               // trace: {rate, path3}; audio: the element that is playing it
  const at = () => {                                      // the point of the path at the time of the audio (between two rows)
    const x = Math.max(0, Math.min(trace.path3.length - 1, audio.currentTime * trace.rate)), i = Math.floor(x), f = x - i;
    const a = trace.path3[i], b = trace.path3[Math.min(i + 1, trace.path3.length - 1)];
    return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])];
  };
  const globe = mountGlobe(root, ctx, {
    title: 'Atlas', key: 'Score atlas', cloud: () => S.cloud, labels: () => S.labels,
    overlay(g, project, T) {
      if (!trace) return;
      g.strokeStyle = T.textStrong || T.text; g.lineWidth = 2; g.globalAlpha = 0.8; g.beginPath();
      trace.path3.forEach((p, k) => { const q = project(p); if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]); });
      g.stroke(); g.lineWidth = 1; g.globalAlpha = 1;
      if (audio) {
        const d = project(at());
        g.beginPath(); g.arc(d[0], d[1], 6, 0, 2 * Math.PI); g.fillStyle = T.accent; g.fill();
      }
    },
  });
  followTab(root);

  const tick = () => { globe.draw(); raf = audio && !audio.paused ? requestAnimationFrame(tick) : 0; };
  ctx.atlas = {
    // shows the path of a take (trace = {rate, path3}, or null for a take without one) and follows the audio that plays it
    follow(a, t) {
      trace = t && t.path3 && t.path3.length ? t : null; audio = trace ? a : null;
      cancelAnimationFrame(raf); raf = 0;
      if (audio) { audio.addEventListener('play', () => { if (!raf) tick(); }); if (!audio.paused) tick(); }
      globe.draw();
    },
    // the take stopped: the path stays, the dot goes
    stop() { audio = null; cancelAnimationFrame(raf); raf = 0; globe.draw(); },
    draw: globe.draw,
    state: () => ({trace: !!trace, playing: !!audio, points: trace ? trace.path3.length : 0}),     // for the tests
  };
  bus.on('boot', globe.draw); bus.on('tab', globe.draw);
  globe.draw();
}

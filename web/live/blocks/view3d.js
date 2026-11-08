// The atlas panel of Live: the shared 3-D view (web/shared/core/globe.js) with the mean of the selection (a ring) and the embedding being
// made (orange) on top.
import {S, bus} from '../../shared/core/state.js';
import {mountGlobe} from '../../shared/core/globe.js';

export function mount(root, ctx) {
  const globe = mountGlobe(root, ctx, {
    title: 'Atlas', cloud: () => S.cloud, labels: () => S.labels,
    overlay(g, project, T) {
      const live = S.lastLive;
      if (!(live && live.dec3 && live.mean3)) return;
      const d = project(live.dec3), m = project(live.mean3);
      g.strokeStyle = T.line; g.lineWidth = 1.5;
      g.beginPath(); g.moveTo(m[0], m[1]); g.lineTo(d[0], d[1]); g.stroke(); g.lineWidth = 1;
      g.beginPath(); g.arc(m[0], m[1], 5, 0, 2 * Math.PI); g.stroke();
      g.beginPath(); g.arc(d[0], d[1], 6, 0, 2 * Math.PI); g.fillStyle = T.accent; g.fill();
    },
  });
  bus.on('live', globe.draw); bus.on('boot', globe.draw);
}

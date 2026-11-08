// What a dot or a clip stands for: a mix of sources, `comp` = [[source, weight], ...] (the weights add up to 1). A source on its own is
// [[i, 1]]; a dot made by a double-click on the playground is the mix that was under it. The server turns a comp into the CLAP embedding.
import {S} from './state.js';

// the dots are the sources first (one slot each, null while not on the plane) and then the free dots made on the plane
export const comp = (dot) => (dot < S.sources.length ? [[dot, 1]] : S.free[dot - S.sources.length].comp);

// the comp of a selection of the playground, idx = indices of dots, lam = their weights
export function mixOf(idx, lam) {
  const w = new Map();
  idx.forEach((d, k) => comp(d).forEach(([s, x]) => w.set(s, (w.get(s) || 0) + lam[k] * x)));
  const total = [...w.values()].reduce((a, b) => a + b, 0) || 1;
  return [...w].map(([s, x]) => [s, x / total]).sort((a, b) => a[0] - b[0]);
}

// the source with the largest weight
export const mainSource = (c) => c.reduce((best, p) => (p[1] > best[1] ? p : best), c[0])[0];

// "name" or "name +2" (the sources besides the main one)
export function labelOf(c) {
  const main = mainSource(c);
  return S.sources[main].name + (c.length > 1 ? ` +${c.length - 1}` : '');
}

export const clusterOf = (c) => S.sources[mainSource(c)].cluster;

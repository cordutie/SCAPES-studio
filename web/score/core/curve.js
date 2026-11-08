// The speed of an interpolation: a curve through some dots of the unit square, x = time (0 .. 1 across the gap between two clips),
// y = position (0 = the first clip, 1 = the next one). The curve is the Lagrange polynomial through the dots. The server does the same
// sum (studio/score/path.py); what it uses is the value limited to [0, 1].
export const DEFAULT_CURVE = [[0, 0], [0.2, 0.4], [0.5, 0.5], [0.8, 0.6], [1, 1]];     // a cubic shifted to be centred at (0.5, 0.5)
export const MAX_POINTS = 12, MIN_DX = 0.02;                                            // dots at least this far apart in x

export const copy = (pts) => pts.map((p) => p.slice());
export const isDefault = (pts) => !pts || (pts.length === DEFAULT_CURVE.length && pts.every((p, i) => p[0] === DEFAULT_CURVE[i][0] && p[1] === DEFAULT_CURVE[i][1]));

// the value of the polynomial through pts at x
export function lagrange(pts, x) {
  let sum = 0;
  for (let i = 0; i < pts.length; i++) {
    let term = pts[i][1];
    for (let j = 0; j < pts.length; j++) if (j !== i) term *= (x - pts[j][0]) / (pts[i][0] - pts[j][0]);
    sum += term;
  }
  return sum;
}
export const position = (pts, x) => Math.min(1, Math.max(0, lagrange(pts, x)));

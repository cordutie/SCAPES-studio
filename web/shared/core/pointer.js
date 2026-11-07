// The point you move, drawn the same in the semantic and in the structure playground: a glowing orange dot with a ring.
const R = 6;                                      // px
export function drawPointer(g, T, x, y) {
  g.save();
  g.shadowColor = T.accent; g.shadowBlur = 16;
  g.beginPath(); g.arc(x, y, R, 0, 2 * Math.PI); g.fillStyle = T.accent; g.fill(); g.fill();
  g.restore();
  g.beginPath(); g.arc(x, y, R + 4, 0, 2 * Math.PI); g.strokeStyle = T.accentSoft; g.lineWidth = 1.5; g.stroke(); g.lineWidth = 1;
}

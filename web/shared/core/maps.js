// How a knob's position (0..1) maps to a value, and how a value is written and read back. A map is
// {toPos(v), fromPos(t), min, max}. A param may bring its own `format(v)` and `parse(text)`.
export const linear = (min, max) => ({min, max, toPos: (v) => (v - min) / (max - min), fromPos: (t) => min + t * (max - min)});
export const log = (min, max) => ({min, max, toPos: (v) => Math.log(v / min) / Math.log(max / min),
                                   fromPos: (t) => min * Math.pow(max / min, t)});
// A level in dB from -infinity to maxDb, like a fader: the gain grows with the cube of the position, so the bottom of the
// knob is silence and the resolution is finest near 0 dB. The value is in dB (-Infinity at the bottom).
export const fader = (maxDb, k = 3) => ({
  min: -Infinity, max: maxDb,
  toPos: (v) => (v === -Infinity ? 0 : Math.pow(Math.pow(10, (v - maxDb) / 20), 1 / k)),
  fromPos: (t) => (t <= 0.003 ? -Infinity : maxDb + 20 * k * Math.log10(t)),
});

export const fmtDb = (v) => (v === -Infinity || v < -90 ? '-∞ dB' : (v >= 0 ? '+' : '') + v.toFixed(1) + ' dB');
export const parseDb = (text) => (/inf|∞/i.test(text) ? -Infinity : parseFloat(text));
export const fmtPct = (v) => Math.round(v * 100) + ' %';
export const parsePct = (text) => parseFloat(text) / 100;

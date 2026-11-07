// Saturator: the signal goes through a Gain knob (dB), then the soft clip arctan, then a Level knob (dB).
// At Gain 0 dB the signal enters the arctan as it is (and a quiet signal comes out unchanged: the arctan has slope 1 at 0).
//
// An effect definition: {id, name, params: [{id, label, map, value, format, parse?, step?}], layout?: 'rows' | 'bars',
// create(actx) -> {input, output, set(paramId, value)}}. `map` is a core/maps.js map (a knob's position <-> value).
import {glide} from './glide.js';
import {linear, fader, fmtDb, parseDb} from '../../core/maps.js';

const RANGE = 8;                                    // the WaveShaper sees the signal / RANGE, so a peak up to RANGE x is not cut
const curve = () => {
  const n = 4096, c = new Float32Array(n);
  for (let i = 0; i < n; i++) c[i] = Math.atan(RANGE * (i / (n - 1) * 2 - 1));
  return c;
};
const db = (v) => Math.pow(10, v / 20);

export default {
  id: 'saturator', name: 'Saturator',
  params: [
    {id: 'gain', label: 'Gain', map: linear(-12, 12), step: 0.1, value: 0, format: fmtDb, parse: parseDb},
    {id: 'level', label: 'Level', map: fader(12), value: 0, format: fmtDb, parse: parseDb},
  ],
  create(actx) {
    const pre = actx.createGain(), shaper = actx.createWaveShaper(), out = actx.createGain();
    shaper.curve = curve(); shaper.oversample = '2x';
    pre.connect(shaper); shaper.connect(out);
    return {
      input: pre, output: out,
      set(id, v) {
        if (id === 'gain') glide(actx, pre.gain, db(v) / RANGE);
        else glide(actx, out.gain, db(v));          // -Infinity dB is a gain of 0
      },
    };
  },
};

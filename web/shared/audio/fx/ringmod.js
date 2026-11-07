import {glide} from './glide.js';
import {linear, log, fmtPct, parsePct} from '../../core/maps.js';

// Ring modulator: the sound times a sine. The sine drives the gain of a Gain node, so it is one oscillator and one multiply.
export default {
  id: 'ringmod', name: 'Ring mod',
  params: [
    {id: 'freq', label: 'Freq', map: log(1, 2000), value: 200, format: (v) => Math.round(v) + ' Hz', parse: parseFloat},
    {id: 'mix', label: 'Mix', map: linear(0, 1), step: 0.01, value: 0.5, format: fmtPct, parse: parsePct},
  ],
  create(actx) {
    const input = actx.createGain(), output = actx.createGain();
    const ring = actx.createGain(), wet = actx.createGain(), dry = actx.createGain(), osc = actx.createOscillator();
    ring.gain.value = 0;                               // the oscillator is the whole gain: out = in * sin
    osc.connect(ring.gain); osc.start();
    input.connect(ring); ring.connect(wet); wet.connect(output);
    input.connect(dry); dry.connect(output);
    return {
      input, output,
      set(id, v) {
        if (id === 'freq') glide(actx, osc.frequency, v);
        else {
          glide(actx, wet.gain, v);
          glide(actx, dry.gain, 1 - v);
        }
      },
    };
  },
};

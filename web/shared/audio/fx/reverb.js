// Reverb: a convolution with a made-up room, like LushReverb of SCAPES (noise with a decaying envelope) but cheaper: one
// decay time, with the highs dying faster than the lows (a low-pass that closes along the tail). A new decay builds a new room
// on the second convolver and crossfades to it, so turning the knob does not click.
import {glide} from './glide.js';
import {linear, fmtPct, parsePct} from '../../core/maps.js';

function roomIR(actx, seconds) {
  const sr = actx.sampleRate, n = Math.floor(sr * seconds), pre = Math.floor(sr * 0.01);
  const buf = actx.createBuffer(2, n, sr);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    let lp = 0;
    for (let i = pre; i < n; i++) {
      const t = (i - pre) / (n - pre);
      lp += (Math.random() * 2 - 1 - lp) * (0.05 + 0.85 * Math.exp(-4 * t));   // bright at first, dark at the end
      d[i] = lp * Math.exp(-6.9 * t);                                           // -60 dB at the end of the tail
    }
  }
  return buf;
}

export default {
  id: 'reverb', name: 'Reverb',
  params: [
    {id: 'mix', label: 'Mix', map: linear(0, 1), step: 0.01, value: 0.3, format: fmtPct, parse: parsePct},
    {id: 'decay', label: 'Decay', map: linear(0.3, 6), step: 0.1, value: 2, format: (v) => v.toFixed(1) + ' s', parse: parseFloat},
  ],
  create(actx) {
    const input = actx.createGain(), output = actx.createGain();
    const wet = actx.createGain(), dry = actx.createGain();
    const rooms = [0, 1].map(() => ({conv: actx.createConvolver(), gain: actx.createGain()}));
    input.connect(dry); dry.connect(output); wet.connect(output);
    rooms.forEach((r, i) => { input.connect(r.conv); r.conv.connect(r.gain); r.gain.connect(wet); r.gain.gain.value = i === 0 ? 1 : 0; });
    let live = 0, timer = null, built = false;
    function newRoom(seconds) {                          // build on the idle convolver, then crossfade
      const next = 1 - live;
      rooms[next].conv.buffer = roomIR(actx, seconds);
      glide(actx, rooms[live].gain.gain, 0); glide(actx, rooms[next].gain.gain, 1);
      live = next;
    }
    return {
      input, output,
      set(id, v) {
        if (id === 'mix') { glide(actx, wet.gain, v); glide(actx, dry.gain, 1 - v); }
        else if (!built) { built = true; rooms[0].conv.buffer = roomIR(actx, v); }   // the first room, at once
        else { clearTimeout(timer); timer = setTimeout(() => newRoom(v), 120); }       // a new room, once the knob rests
      },
    };
  },
};

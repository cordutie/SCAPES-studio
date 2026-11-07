import {glide} from './glide.js';
// 8-band equaliser: a low shelf, six peaking bands and a high shelf, one octave apart. +-12 dB each.
const BANDS = [['63', 62.5], ['125', 125], ['250', 250], ['500', 500], ['1k', 1000], ['2k', 2000], ['4k', 4000], ['8k', 8000]];

export default {
  id: 'eq', name: 'EQ', layout: 'bars',
  params: BANDS.map(([label, hz], i) => ({id: 'b' + i, label, min: -12, max: 12, step: 0.5, value: 0,
                                           format: (v) => v.toFixed(1) + ' dB', hz})),
  create(actx) {
    const filters = BANDS.map(([, hz], i) => {
      const f = actx.createBiquadFilter();
      f.type = i === 0 ? 'lowshelf' : i === BANDS.length - 1 ? 'highshelf' : 'peaking';
      f.frequency.value = hz; f.Q.value = 1.0;
      return f;
    });
    filters.forEach((f, i) => { if (i) filters[i - 1].connect(f); });
    return {input: filters[0], output: filters[filters.length - 1],
            set: (id, v) => { glide(actx, filters[parseInt(id.slice(1), 10)].gain, v); }};
  },
};

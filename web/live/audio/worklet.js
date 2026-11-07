// The player in the audio thread. The server streams 16-bit PCM; this keeps it in a ring buffer and plays it.
//
// What happens when the next audio is not here in time (an "underrun"), as in any streaming player:
//   - the audio that is left is faded out (no click), the player goes back to "buffering" and tells the page;
//   - it plays again, with a short fade-in, when PREBUFFER seconds have arrived;
//   - the page tells the server, which then keeps more audio ahead (a bigger buffer) from then on.
// messages in:  {type: 'config', channels, prebuffer}  {type: 'reset'}  {type: 'chunk', pcm: ArrayBuffer}  {type: 'end'}
// messages out: {type: 'pos', played, queued}  {type: 'underrun'}  {type: 'drained'}
const CAPACITY_S = 10;       // ring buffer size
const RAMP = 256;            // fade-in length in samples
const REPORT_EVERY = 17;     // process() calls between position reports (about 50 ms)

class ScapesPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.channels = 2;
    this.prebuffer = Math.round(0.3 * sampleRate);
    this.reset();
    this.port.onmessage = ({data}) => this.onMessage(data);
  }

  reset() {
    this.cap = Math.round(CAPACITY_S * sampleRate);
    this.buf = Array.from({length: this.channels}, () => new Float32Array(this.cap));
    this.r = 0; this.w = 0; this.n = 0;
    this.state = 'buffering';
    this.played = 0; this.gain = 0; this.calls = 0;
    this.ending = false; this.drainedSent = false;
  }

  onMessage(m) {
    if (m.type === 'config') { this.channels = m.channels; this.prebuffer = Math.round(m.prebuffer * sampleRate); this.reset(); }
    else if (m.type === 'reset') this.reset();
    else if (m.type === 'chunk') this.write(new Int16Array(m.pcm));
    else if (m.type === 'end') this.ending = true;
  }

  write(pcm) {
    const ch = this.channels, frames = pcm.length / ch;
    if (this.n + frames > this.cap) return;                      // the server is paced; this should not happen
    for (let i = 0; i < frames; i++) {
      for (let c = 0; c < ch; c++) this.buf[c][this.w] = pcm[i * ch + c] / 32768;
      this.w = (this.w + 1) % this.cap;
    }
    this.n += frames;
  }

  drained() {
    this.state = 'buffering'; this.gain = 0;
    if (!this.drainedSent) { this.drainedSent = true; this.port.postMessage({type: 'drained'}); }
  }

  process(inputs, outputs) {
    const out = outputs[0], N = out[0].length;
    if (this.state === 'buffering') {
      if (this.n >= this.prebuffer || (this.ending && this.n > 0)) { this.state = 'playing'; this.gain = 0; }
      else if (this.ending) this.drained();
    }
    if (this.state === 'playing') {
      const take = Math.min(N, this.n);
      const dying = take < N && !this.ending;                    // not a whole block left: fade it out and rebuffer
      for (let i = 0; i < take; i++) {
        if (this.gain < 1) this.gain = Math.min(1, this.gain + 1 / RAMP);
        const g = this.gain * (dying ? (take - i) / take : 1);
        for (let c = 0; c < out.length; c++) out[c][i] = this.buf[c % this.channels][this.r] * g;
        this.r = (this.r + 1) % this.cap;
      }
      this.n -= take; this.played += take;
      if (dying) { this.state = 'buffering'; this.gain = 0; this.port.postMessage({type: 'underrun'}); }
      else if (this.ending && this.n === 0) this.drained();
    }
    if (++this.calls % REPORT_EVERY === 0) this.port.postMessage({type: 'pos', played: this.played, queued: this.n});
    return true;
  }
}
registerProcessor('scapes-player', ScapesPlayer);

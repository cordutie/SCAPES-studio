// Takes the sound that goes by (2 channels) and sends it to the page in blocks, to be saved as a WAV file (audio/recorder.js).
class Recorder extends AudioWorkletProcessor {
  constructor() { super(); this.on = false; this.port.onmessage = ({data}) => { this.on = data.on; }; }
  process(inputs) {
    const inp = inputs[0];
    if (this.on && inp.length) {
      const l = inp[0], r = inp[1] || inp[0];
      this.port.postMessage({l: l.slice(), r: r.slice()});
    }
    return true;
  }
}
registerProcessor('scapes-recorder', Recorder);

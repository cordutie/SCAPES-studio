// Records what you hear (after the effects and the volume) to a 16-bit WAV file that the browser downloads.
//   const rec = await createRecorder(actx, sourceNode);  rec.start();  rec.stop(name) -> downloads name.wav
export async function createRecorder(actx, source) {
  await actx.audioWorklet.addModule('/web/live/audio/recorder.worklet.js?v=' + Date.now());
  const node = new AudioWorkletNode(actx, 'scapes-recorder', {numberOfOutputs: 1, outputChannelCount: [2]});
  const mute = actx.createGain(); mute.gain.value = 0;                 // the worklet must reach the output to be run
  source.connect(node); node.connect(mute); mute.connect(actx.destination);
  let left = [], right = [], on = false;
  node.port.onmessage = ({data}) => { left.push(data.l); right.push(data.r); };

  const concat = (parts) => { const out = new Float32Array(parts.reduce((n, p) => n + p.length, 0)); let o = 0; parts.forEach((p) => { out.set(p, o); o += p.length; }); return out; };
  function wav(l, r, sr) {
    const n = l.length, buf = new DataView(new ArrayBuffer(44 + n * 4));
    const str = (o, s) => [...s].forEach((c, i) => buf.setUint8(o + i, c.charCodeAt(0)));
    str(0, 'RIFF'); buf.setUint32(4, 36 + n * 4, true); str(8, 'WAVEfmt '); buf.setUint32(16, 16, true); buf.setUint16(20, 1, true);
    buf.setUint16(22, 2, true); buf.setUint32(24, sr, true); buf.setUint32(28, sr * 4, true); buf.setUint16(32, 4, true); buf.setUint16(34, 16, true);
    str(36, 'data'); buf.setUint32(40, n * 4, true);
    for (let i = 0; i < n; i++) {
      buf.setInt16(44 + i * 4, Math.max(-1, Math.min(1, l[i])) * 32767, true);
      buf.setInt16(46 + i * 4, Math.max(-1, Math.min(1, r[i])) * 32767, true);
    }
    return new Blob([buf], {type: 'audio/wav'});
  }
  return {
    recording: () => on,
    start() { left = []; right = []; on = true; node.port.postMessage({on: true}); },
    // returns the length in seconds
    stop(name) {
      on = false; node.port.postMessage({on: false});
      const l = concat(left), r = concat(right);
      left = []; right = [];
      if (!l.length) return 0;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(wav(l, r, actx.sampleRate)); a.download = name + '.wav';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
      return l.length / actx.sampleRate;
    },
  };
}

// The player in the page: the WebSocket to the server (demo/transport.py), the audio thread (worklet.js), the effects
// chain (fx/chain.js) and the level meter. Blocks use this object and nothing deeper.
//
//   const player = createPlayer(info);   // info: what the server said about the model (sample rate, buffer, ...)
//   await player.init();                 // loads the worklet, builds the chain, opens the socket
//   await player.play();  player.stop();  player.setParams({nfe, cfg});
//   player.on('status' | 'run' | 'underrun' | 'drained' | 'ended' | 'error' | 'open' | 'close', fn)
//   player.chain  (see fx/chain.js)       player.levels() -> {l, r} peaks in dB
//   player.setVolume(gain)  the master volume (linear gain, after the effects)   player.recorder (see recorder.js)
import {createChain} from '../../shared/audio/fx/chain.js';
import {createRecorder} from './recorder.js';
import {EFFECTS} from '../../shared/audio/fx/index.js';

export function createPlayer(info) {
  const listeners = {};
  const emit = (name, data) => (listeners[name] || []).forEach((fn) => fn(data));
  const on = (name, fn) => { (listeners[name] = listeners[name] || []).push(fn); };

  const actx = new AudioContext({sampleRate: info.sample_rate, latencyHint: 'interactive'});
  const chain = createChain(actx, EFFECTS);
  const master = actx.createGain();
  let node = null, ws = null, run = 0, drained = true, recorder = null;

  // the meter: peak of each channel, after the chain and the limiter (what you hear)
  const splitter = actx.createChannelSplitter(2);
  const analysers = [0, 1].map(() => { const a = actx.createAnalyser(); a.fftSize = 1024; return a; });
  const scratch = new Float32Array(1024);
  function levels() {
    const db = analysers.map((a) => {
      a.getFloatTimeDomainData(scratch);
      let peak = 0;
      for (let i = 0; i < scratch.length; i++) peak = Math.max(peak, Math.abs(scratch[i]));
      return peak > 1e-5 ? 20 * Math.log10(peak) : -100;
    });
    return {l: db[0], r: db[1]};
  }

  async function init() {
    await actx.audioWorklet.addModule('/web/live/audio/worklet.js?v=' + Date.now());
    node = new AudioWorkletNode(actx, 'scapes-player', {outputChannelCount: [2]});
    node.port.postMessage({type: 'config', channels: info.channels, prebuffer: info.prebuffer_s});
    // a limiter at the end keeps a loud effect setting from blasting
    const limiter = actx.createDynamicsCompressor();
    limiter.threshold.value = -1; limiter.knee.value = 0; limiter.ratio.value = 20;
    limiter.attack.value = 0.003; limiter.release.value = 0.1;
    node.connect(chain.input);
    chain.output.connect(master);
    master.connect(limiter);
    limiter.connect(actx.destination);
    limiter.connect(splitter);
    recorder = await createRecorder(actx, limiter);
    analysers.forEach((a, i) => splitter.connect(a, i));

    let lastAck = 0;
    node.port.onmessage = ({data}) => {
      if (data.type === 'pos') {
        const now = performance.now();
        if (now - lastAck > 90 && ws && ws.readyState === 1) {
          lastAck = now;
          ws.send(JSON.stringify({op: 'played', run, frames: data.played}));
        }
      } else if (data.type === 'underrun') {
        if (ws && ws.readyState === 1) ws.send(JSON.stringify({op: 'underrun', run}));
        emit('underrun');
      } else if (data.type === 'drained') {
        drained = true; emit('drained');
      }
    };
    await connect();
  }

  function connect() {
    return new Promise((resolve) => {
      ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + location.pathname.replace(/\/$/, '') + '/ws/audio');
      ws.binaryType = 'arraybuffer';
      ws.onopen = () => { emit('open'); resolve(); };
      ws.onclose = () => emit('close');
      ws.onmessage = (e) => {
        if (typeof e.data !== 'string') { node.port.postMessage({type: 'chunk', pcm: e.data}, [e.data]); return; }
        const m = JSON.parse(e.data);
        if (m.type === 'run') { run = m.id; emit('run', m); }
        else if (m.type === 'ended') { node.port.postMessage({type: 'end'}); emit('ended'); }
        else emit(m.type, m);                          // info, status, error
      };
    });
  }

  // Must be called from a click: browsers only start audio after one.
  async function play() {
    await actx.resume();
    node.port.postMessage({type: 'reset'});
    drained = false;
    ws.send(JSON.stringify({op: 'play'}));
  }

  return {
    init, play, on, levels, chain,
    stop: () => ws && ws.readyState === 1 && ws.send(JSON.stringify({op: 'stop'})),
    setParams: (p) => ws && ws.readyState === 1 && ws.send(JSON.stringify(Object.assign({op: 'params'}, p))),
    setVolume: (g) => master.gain.setTargetAtTime(g, actx.currentTime, 0.012),
    get recorder() { return recorder; },
    isDrained: () => drained,
    connected: () => !!ws && ws.readyState === 1,
  };
}

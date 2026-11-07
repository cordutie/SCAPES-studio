// The Model panel. Top half: the model menu with the NFE and CFG knobs (left) and the log (right, a black box). Bottom half: the
// level meter with the volume knob, and ▶ ■ ● (play, stop, record). The light at the top right is green when the generation is
// faster than real time, orange near the limit, red when the sound ran dry. Stop ends the sound with the fade-out of the last unit.
// The model menu lists the folders of models/ and switches the model on the server; the page then reloads.
import {S, ref} from '../../shared/core/state.js';
import {createKnob} from '../../shared/core/knob.js';
import {linear, log, fader, fmtDb, parseDb} from '../../shared/core/maps.js';
import {header} from '../../shared/core/ui.js';

const FLOOR_DB = -60;                                // the bottom of the meter
const TICKS = [-60, -48, -36, -24, -12, -6, 0];
const MAX_LOG_LINES = 200;

export function mount(root, ctx) {
  const T = ctx.theme, info = S.info;
  root.innerHTML = header('Model') + `
    <div class="m-top">
      <div class="m-left"><button class="model-btn" data-ref="modelbtn" title="choose another model"></button>
        <div class="m-knobs" data-ref="knobs"></div></div>
      <div class="m-log"><div class="live" data-ref="live"></div><div class="lines" data-ref="lines"></div></div>
    </div>
    <div class="m-bottom">
      <div class="m-meter"><canvas class="meter" data-ref="meter" width="360" height="130"></canvas>
        <div class="transport"><button data-ref="play" title="play">▶</button><button data-ref="stop" title="stop">■</button><button data-ref="rec" title="record what you hear to a WAV file">●</button></div></div>
      <div class="m-volume" data-ref="volume"></div>
    </div>
    <div class="menu" data-ref="menu" hidden></div>`;
  const tools = ref(root, 'tools');
  tools.innerHTML = `<span class="light" data-ref="light" data-state="off" title="green: faster than real time. orange: close to the limit. red: the sound ran dry, a frame was late. Lower NFE if it is not green."></span>`;
  const modelBtn = ref(root, 'modelbtn'), menu = ref(root, 'menu'), liveEl = ref(root, 'live'), lines = ref(root, 'lines');
  const playBtn = ref(root, 'play'), stopBtn = ref(root, 'stop'), recBtn = ref(root, 'rec');
  modelBtn.textContent = info.model + ' ▾';
  const player = ctx.player;

  // --- the log ---
  const stamp = () => new Date().toTimeString().slice(0, 8);
  function logLine(text, warn) {
    const row = document.createElement('div');
    if (warn) row.className = 'warn';
    row.textContent = stamp() + '  ' + text;
    lines.appendChild(row);
    while (lines.children.length > MAX_LOG_LINES) lines.firstChild.remove();
    lines.scrollTop = lines.scrollHeight;
  }
  logLine('model ' + info.model);
  logLine(`${info.codec_mode === 'atoms' ? 'atoms' : 'blocks'}: ${info.rate_hz.toFixed(2)} Hz conditioning · memory ${info.memory_s.toFixed(2)} s · ${info.sample_rate} Hz audio`);
  if (!player) { logLine('audio is not available in this browser', true); playBtn.disabled = stopBtn.disabled = recBtn.disabled = true; return; }

  // --- the knobs: NFE and CFG (applied from the next step, when the knob is released) and the volume ---
  const knobs = ref(root, 'knobs');
  knobs.append(
    createKnob({label: 'NFE', map: log(info.nfe_range[0], info.nfe_range[1]), value: info.nfe, def: info.nfe, step: 1, size: 64,
                format: (v) => String(Math.round(v)), onCommit: (v) => { player.setParams({nfe: Math.round(v)}); logLine('NFE ' + Math.round(v)); }}).el,
    createKnob({label: 'CFG', map: linear(info.cfg_range[0], info.cfg_range[1]), value: info.cfg, def: info.cfg, step: info.cfg_step, size: 64,
                format: (v) => v.toFixed(1), onCommit: (v) => { player.setParams({cfg: v}); logLine('CFG ' + v.toFixed(1)); }}).el);
  ref(root, 'volume').append(
    createKnob({label: 'Volume', map: fader(6), value: 0, def: 0, size: 64, format: fmtDb, parse: parseDb,
                onChange: (v) => player.setVolume(Math.pow(10, v / 20))}).el);

  // --- the model menu ---
  async function openMenu() {
    let list = [];
    try { list = await ctx.api.models(); } catch (e) { list = []; }
    menu.innerHTML = '';
    list.forEach((m) => {
      const item = document.createElement('button');
      item.className = m.current ? 'current' : '';
      item.innerHTML = `${m.name}<small>${m.codec} · ${m.rate.toFixed(1)} Hz${m.current ? ' · loaded' : ''}</small>`;
      item.addEventListener('click', () => { menu.hidden = true; if (!m.current) switchTo(m.name); });
      menu.appendChild(item);
    });
    menu.hidden = false;
  }
  modelBtn.addEventListener('click', (e) => { e.stopPropagation(); if (menu.hidden) openMenu(); else menu.hidden = true; });
  document.addEventListener('click', () => { menu.hidden = true; });
  async function switchTo(name) {
    player.stop();
    playBtn.disabled = stopBtn.disabled = modelBtn.disabled = true;
    logLine(`loading ${name} …`);
    let r = null;
    try { r = await ctx.api.loadModel(name); } catch (e) { r = {ok: false, error: String(e)}; }
    if (r.ok) { location.reload(); return; }
    logLine(r.error, true); modelBtn.disabled = false; buttons();
  }

  // --- play, stop, record ---
  let server = {state: 'idle'}, starting = false, lastError = '', lastUnder = 0, nearLimit = false;
  const WARN_EVERY_MS = 5000;                           // the same warning is written at most this often
  const lastWarn = {};
  const warnOnce = (kind, text) => { const now = performance.now(); if (now - (lastWarn[kind] ?? -1e9) >= WARN_EVERY_MS) { lastWarn[kind] = now; logLine(text, true); } };
  function buttons() {
    playBtn.disabled = !(player.connected() && server.state === 'idle' && player.isDrained()) || starting;
    stopBtn.disabled = server.state !== 'running';
    playBtn.classList.toggle('on', server.state === 'running');
  }
  playBtn.addEventListener('click', async () => {
    if (!S.dots.some((d) => d !== null)) { logLine('place a dot on the semantic playground first', true); return; }
    starting = true; buttons();
    await player.play();
  });
  stopBtn.addEventListener('click', () => player.stop());
  recBtn.addEventListener('click', () => {
    const rec = player.recorder;
    if (!rec) return;
    if (!rec.recording()) { rec.start(); recBtn.classList.add('rec'); logLine('recording …'); return; }
    const name = `scapes_${info.model}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`;
    const secs = rec.stop(name);
    recBtn.classList.remove('rec');
    logLine(secs ? `saved ${name}.wav (${secs.toFixed(1)} s)` : 'nothing was recorded', !secs);
  });
  player.on('run', () => { starting = false; buttons(); });
  player.on('error', (m) => { starting = false; logLine(m.message, true); buttons(); });
  player.on('status', (m) => {
    if (m.state !== server.state) logLine({idle: 'stopped', running: 'running', stopping: 'stopping'}[m.state] || m.state);
    server = m; if (m.state !== 'idle') starting = false;
    if (m.error && m.error !== lastError) logLine(m.error, true);
    lastError = m.error || '';
    if ((m.underruns || 0) > lastUnder) warnOnce('under', `underruns: ${m.underruns} so far (the sound ran dry)`);
    lastUnder = m.underruns || 0;
    const near = m.state === 'running' && m.load > info.load_warn;
    if (near && !nearLimit) warnOnce('near', `load ${Math.round(100 * m.load)} %: near the limit, lower NFE`);
    nearLimit = near;
    buttons(); text(); updateLight(m);
  });
  player.on('drained', buttons);
  player.on('open', () => { logLine('connected'); buttons(); });
  player.on('close', () => { logLine('the connection to the server was lost', true); buttons(); });

  // the light: red when the sound ran dry (a frame was not there in time), orange when a step took more than load_warn of its hop
  // (close to the limit, or over it but absorbed by the buffer), else green; stopped: off. A colour that has been seen stays
  // for a moment, so that a short event can be seen.
  const light = ref(root, 'light'), seen = {warn: -1e9, late: -1e9};
  const mark = (kind) => { seen[kind] = performance.now(); };
  player.on('underrun', () => mark('late'));
  function updateLight(s) {
    const now = performance.now();
    if (s && s.state === 'running' && s.worst >= info.load_warn) mark('warn');
    const running = server.state === 'running';
    light.dataset.state = !running ? 'off' : now - seen.late < info.late_hold_s * 1000 ? 'late' : now - seen.warn < 500 ? 'warn' : 'ok';
  }
  setInterval(() => updateLight(null), 100);

  function text() {
    const s = server, load = Math.round(100 * (s.load || 0));
    const state = {idle: 'Stopped', running: 'Running', stopping: 'Stopping'}[s.state] || s.state;
    liveEl.textContent = `${state}  ·  load ${load} %  ·  ahead ${(s.lead || 0).toFixed(2)} s (target ${(s.target || 0).toFixed(2)})  ·  underruns ${s.underruns || 0}`;
  }

  // --- the meter: peak of each channel after the effects, with a peak hold ---
  const mc = ref(root, 'meter'), W = 360, H = 130, left = 22, right = 6;
  const bar = {l: FLOOR_DB, r: FLOOR_DB}, hold = {l: FLOOR_DB, r: FLOOR_DB, tl: 0, tr: 0};
  const x = (db) => left + (W - left - right) * (Math.max(FLOOR_DB, Math.min(0, db)) - FLOOR_DB) / -FLOOR_DB;
  let last = performance.now();
  function meter(now) {
    const dt = (now - last) / 1000; last = now;
    const lv = player.levels(), g = mc.getContext('2d');
    g.fillStyle = T.bg; g.fillRect(0, 0, W, H);
    [['l', 8], ['r', 50]].forEach(([k, y]) => {
      bar[k] = Math.max(lv[k], bar[k] - 40 * dt);                           // falls 40 dB per second
      if (bar[k] >= hold[k]) { hold[k] = bar[k]; hold['t' + k] = now; } else if (now - hold['t' + k] > 1000) hold[k] -= 30 * dt;
      g.fillStyle = T.panel; g.fillRect(left, y, W - left - right, 34);
      g.fillStyle = T.accent; g.fillRect(left, y, x(bar[k]) - left, 34);
      g.fillStyle = T.text; g.fillRect(x(hold[k]) - 1, y, 2, 34);
      g.font = `600 13px ${T.font}`; g.fillText(k.toUpperCase(), 5, y + 22);
    });
    g.strokeStyle = T.line; g.fillStyle = T.text; g.textAlign = 'center'; g.font = `11px ${T.font}`;
    TICKS.forEach((db) => { g.beginPath(); g.moveTo(x(db), 92); g.lineTo(x(db), 98); g.stroke(); g.fillText(String(db), x(db), 114); });
    g.textAlign = 'left';
    requestAnimationFrame(meter);
  }
  requestAnimationFrame(meter);
  buttons(); text();
}

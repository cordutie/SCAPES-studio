// MIDI learn for the knobs, the faders and the x / y of the playgrounds. Web MIDI runs in the browser: the controller has to be plugged
// into the machine of the browser (over SSH, forward the port and open localhost: it is a secure page, which Web MIDI asks for).
//
//   midi.register({el, id, name, setNorm})  a control: setNorm(t) takes 0..1. Knobs register themselves (core/knob.js). The map belongs to
//                                        the id, not to the element, so it survives a panel that draws its controls again (an effect switched on).
//   midi.toggleLearn()                   the ⏣ button of the Model panel
//   midi.on(fn)                          fn({type: 'learn'|'map'|'info', ...}) for the button and the log
//
// Learn: the button turns on and listens to every port, remembering only the last CC (last_midi_cc: {ch, cc}, or null when none came).
// The next press on a control binds last_midi_cc to it over its whole range; with null, the control's map is deleted. Then learn turns off.
// A control has at most one CC; a CC may drive many controls. A CC is a pair (channel, number). Values 0..127 become 0..1.
const controls = new Set();              // {el, id, name, setNorm, key}   key: "ch:cc" or null
const maps = new Map();                  // id -> "ch:cc"
let access = null, learning = false, last = null;
const listeners = new Set();
const emit = (e) => listeners.forEach((fn) => fn(e));
const keyOf = (m) => `${m.ch}:${m.cc}`;
const label = (m) => `CC ${m.cc} (ch ${m.ch + 1})`;

export const midi = {
  supported: typeof navigator !== 'undefined' && !!navigator.requestMIDIAccess,
  get learning() { return learning; },
  on(fn) { listeners.add(fn); },

  register(c) {
    c.key = maps.get(c.id) || null; controls.add(c);
    if (c.key) c.el.classList.add('midi-mapped');
    // while learning, a press on the control binds it instead of acting on it
    const grab = (e) => {
      if (!learning) return;
      e.preventDefault(); e.stopPropagation();
      if (e.type === 'pointerdown' && e.button === 0) bind(c);
    };
    ['pointerdown', 'mousedown', 'click', 'dblclick', 'wheel'].forEach((t) => c.el.addEventListener(t, grab, true));
    return c;
  },

  // Two small pads, X and Y, at the bottom right of a playground (only shown while learning): the CC that is bound to one moves that coordinate.
  addXY(root, name, setX, setY) {
    const box = document.createElement('div');
    box.className = 'midi-xy';
    [['X', setX], ['Y', setY]].forEach(([axis, set]) => {
      const pad = document.createElement('span');
      pad.textContent = axis; pad.title = `MIDI: ${name} ${axis}`;
      box.appendChild(pad);
      midi.register({el: pad, id: `${name} ${axis}`, name: `${name} ${axis}`, setNorm: set});
    });
    root.appendChild(box);
  },

  async toggleLearn() {
    if (learning) { stopLearn(); return; }
    if (!access) {
      if (!midi.supported) { emit({type: 'info', text: 'MIDI is not available in this browser (use Chrome, Edge or Opera)', warn: true}); return; }
      try { access = await navigator.requestMIDIAccess(); } catch (e) {
        emit({type: 'info', text: 'MIDI access was refused: ' + (e.message || e), warn: true}); return;
      }
      const attach = () => access.inputs.forEach((p) => { p.onmidimessage = onMessage; });
      access.onstatechange = attach; attach();
    }
    learning = true; last = null;
    document.querySelector('#demo')?.classList.add('midi-learning');
    const n = access.inputs.size;
    emit({type: 'learn', on: true});
    emit({type: 'info', text: n ? `MIDI learn: move a controller (${n} port${n > 1 ? 's' : ''}), then press a control` : 'MIDI learn: no MIDI device found', warn: !n});
  },
};

function stopLearn() {
  learning = false; last = null;
  document.querySelector('#demo')?.classList.remove('midi-learning');
  emit({type: 'learn', on: false});
}

function bind(c) {
  if (c.key) c.el.classList.remove('midi-mapped');
  c.key = last ? keyOf(last) : null;
  if (c.key) maps.set(c.id, c.key); else maps.delete(c.id);
  controls.forEach((o) => { if (o !== c && o.id === c.id) { o.key = c.key; o.el.classList.toggle('midi-mapped', !!c.key); } });
  if (c.key) c.el.classList.add('midi-mapped');
  emit({type: 'map', text: last ? `${label(last)} → ${c.name}` : `${c.name}: MIDI map deleted`});
  stopLearn();
}

function onMessage(e) {
  const [status, d1, d2] = e.data;
  if ((status & 0xf0) !== 0xb0) return;                   // control change only
  const m = {ch: status & 0x0f, cc: d1};
  if (learning) {
    if (!last || keyOf(last) !== keyOf(m)) emit({type: 'info', text: `last CC: ${label(m)}`});    // a new CC, not each turn of the same one
    last = m; return;
  }
  const key = keyOf(m), t = d2 / 127;
  for (const c of [...controls]) {
    if (!c.el.isConnected) { controls.delete(c); continue; }   // a control that left the page
    if (c.key === key) c.setNorm(t);
  }
}

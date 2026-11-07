// The effects chain: the effects of fx/index.js in an order you can change, each one on or off. Nothing here knows what an
// effect is: an effect is a definition {id, name, params, create(actx)} (see saturator.js). The page (blocks/effects.js)
// draws the chain from state() and changes it with setEnabled, setParam and place.
//
// Each effect sits in a slot: in -> [effect] -> wet -> out, and in -> dry -> out. Switching an effect off fades the wet path
// down and the dry path up (20 ms), so there is no click. All the effects stay connected; an unused effect costs almost nothing.
export function createChain(actx, definitions) {
  const input = actx.createGain(), output = actx.createGain();
  const slots = {};
  let order = definitions.map((d) => d.id);
  const listeners = [];

  definitions.forEach((def) => {
    const fx = def.create(actx);
    const slot = {def, fx, enabled: false, values: {}, in: actx.createGain(), out: actx.createGain(),
                  wet: actx.createGain(), dry: actx.createGain()};
    slot.in.connect(fx.input); fx.output.connect(slot.wet); slot.wet.connect(slot.out);
    slot.in.connect(slot.dry); slot.dry.connect(slot.out);
    def.params.forEach((p) => { slot.values[p.id] = p.value; fx.set(p.id, p.value); });
    slots[def.id] = slot;
    applyEnabled(slot, true);
  });

  function applyEnabled(slot, instant) {
    const t = instant ? 0.001 : 0.02;   // a switch fades in 20 ms
    slot.wet.gain.setTargetAtTime(slot.enabled ? 1 : 0, actx.currentTime, t);
    slot.dry.gain.setTargetAtTime(slot.enabled ? 0 : 1, actx.currentTime, t);
  }

  function wire() {
    input.disconnect();
    Object.values(slots).forEach((s) => s.out.disconnect());
    let prev = input;
    order.forEach((id) => { prev.connect(slots[id].in); prev = slots[id].out; });
    prev.connect(output);
  }
  wire();

  const changed = () => listeners.forEach((fn) => fn(state()));
  const state = () => ({order: order.slice(),
    effects: order.map((id) => ({id, name: slots[id].def.name, enabled: slots[id].enabled, values: Object.assign({}, slots[id].values),
                                 params: slots[id].def.params, layout: slots[id].def.layout || 'rows'}))});

  return {
    input, output, state,
    onChange: (fn) => listeners.push(fn),
    setEnabled(id, on) { slots[id].enabled = !!on; applyEnabled(slots[id]); changed(); },
    setParam(id, param, value) { slots[id].values[param] = value; slots[id].fx.set(param, value); },
    // put an effect at a place of the chain (0 = first)
    place(id, index) {
      const i = order.indexOf(id);
      if (i < 0 || index === i || index < 0 || index >= order.length) return;
      order.splice(i, 1); order.splice(index, 0, id);
      wire(); changed();
    },
  };
}

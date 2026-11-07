// The state every block shares, and a small event bus. The browser keeps all of the state; the server functions get what
// they need with each call.
//
// events (bus.emit / bus.on):  'boot'  the data of the atlas has arrived
//                              'live'  the server answered a live call (S.lastLive is new)
//                              'dots'  a dot was placed, moved, removed or cleared
//                              'cluster'  the current cluster block changed
export const S = {
  K: 16, cur: 0, dots: [], names: [], labels: [], cloud: [], hasPrior: false, info: null,
  aim: [0, 0],        // the point asked for on the plane (the server projects it on the zone of the dots)
  ctrl: [0, 0],       // the control point the server answered
  u: [0, 0],          // the point on the disk
  sel: null,          // the selection of the last answer: {idx, lam}
  lastLive: null,     // the last answer of the live call
  needLocate: false,  // true when the control point moved since the last call: the server recomputes the selection
  draggingDot: false, // a dot is being dragged: the control point follows the gesture, not the server
  glide: false, glideT: 10, prior: false, hz: 10, nreq: 0,   // glide seconds, prior ticks per second
  editDots: false,    // the semantic playground: true = a press moves dots, false = a press controls the sound (see blocks/plane.js)
};

class Bus extends EventTarget {
  emit(name, detail) { this.dispatchEvent(new CustomEvent(name, {detail})); }
  on(name, fn) { this.addEventListener(name, (e) => fn(e.detail)); }
}
export const bus = new Bus();

// small helpers
export const clampP = (p) => [Math.min(1, Math.max(-1, p[0])), Math.min(1, Math.max(-1, p[1]))];
export const clampD = (u) => { const n = Math.hypot(u[0], u[1]); return n <= 1 ? [u[0], u[1]] : [u[0] / n, u[1] / n]; };
export const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
// the element of a block with data-ref="name"
export const ref = (root, name) => root.querySelector(`[data-ref="${name}"]`);

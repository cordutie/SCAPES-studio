// The live call: send the dots, the control point and the disk point; get the selection, the decoded point and the outline.
// One call in flight at a time; a change made meanwhile is sent next, with the latest state. The server hands the
// embedding to the generator, so every call is a change of the sound.
import {S, bus} from '../../shared/core/state.js';

export function createLive(api) {
  let busy = false, again = false;
  async function request() {
    if (busy) { again = true; return; }
    busy = true;
    try {
      do {
        again = false;
        // the point sent: the point asked for when the control point moved, else the one the server returned
        const st = {dots: S.dots, c: S.needLocate ? S.aim.slice() : S.ctrl.slice(), sel: S.sel, u: S.u, locate: S.needLocate};
        S.needLocate = false;
        S.nreq += 1;
        let r = null;
        try { r = await api.live(st); } catch (e) { r = null; }
        if (!r) S.needLocate = S.needLocate || st.locate;
        if (r) {
          S.lastLive = r;
          S.sel = r.sel;
          if (r.c && !S.draggingDot) S.ctrl = r.c.slice();
          bus.emit('live', r);
        }
      } while (again);
    } finally {
      busy = false;
    }
  }
  return {request, busy: () => busy};
}

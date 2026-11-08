// The state the blocks of the Score page share (the bus is the one of the other page: web/shared/core/state.js).
//
// events (bus.emit / bus.on):  'boot'   the sources have arrived
//                              'dots'   a dot was placed, moved or removed in the playground
//                              'point'  the point of the playground moved (S.point is new)
//                              'clips'  a clip was added, moved, resized or removed
export const S = {
  model: '', names: [], sources: [],      // sources: [{cluster, name, file, start, url}], one per representative of the model
  dots: [],                                // one entry per source: [x, y] on the playground, or null
  c: null,                                 // the point asked for on the playground (the server answers the one in the zone of the dots)
  point: null,                             // the server's answer: {sel: {idx, lam}, c, outline}, or null without dots
  clips: [], length: 60, pps: 30,          // the timeline: its clips, its length in seconds and its zoom in pixels per second
};

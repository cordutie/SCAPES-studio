// The state the blocks of the Score page share (the bus is the one of the other page: web/shared/core/state.js).
//
// events (bus.emit / bus.on):  'boot'    the sources have arrived
//                              'dots'    a dot was placed, moved or removed in the playground
//                              'point'   the point of the playground moved (S.point is new)
//                              'clips'   a clip was added, moved, resized or removed
//                              'tab'     the page changed between its two views (sources + playground, or takes + atlas)
//                              'takes'   the list of takes changed
//                              'render'  the generation started, advanced (S.rendering.progress) or ended
export const S = {
  model: '', names: [], sources: [],      // sources: [{cluster, name, file, start, url}], one per representative of the model
  cloud: [], labels: [],                   // the atlas in 3-D (a thin sample of the real embeddings) and the cluster of each point
  dots: [],                                // one entry per dot: [x, y] on the playground, or null. The sources come first (one slot each);
                                           // the free dots (double-click on the plane) follow, one per entry of S.free
  free: [],                                // [{comp}]: what each free dot stands for (see core/mix.js)
  c: null,                                 // the point asked for on the playground (the server answers the one in the zone of the dots)
  point: null,                             // the server's answer: {sel: {idx, lam}, c, outline}, or null without dots
  tab: 'sources',                          // the view: 'sources' (sources + playground) or 'takes' (takes + atlas)
  takes: [],                               // what was generated: [{id, name, created, seconds, model, nfe, cfg, seed}], newest first
  gen: {nfe: 8, cfg: 1.0, seed: 0},        // the settings of the next generation
  rendering: null,                         // while a piece is being generated: {progress}
  clips: [],                               // the timeline: [{id, start, dur, comp, label}], seconds
};

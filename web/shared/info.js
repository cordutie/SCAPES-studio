// The texts of the (i) buttons next to each panel's name: what the panel shows and everything you can do in it. They are shown as
// they are (a line is a paragraph); to change one, change it here. The key is the title of the panel.
export const INFO = {
  'Semantic sources': [
    'The sounds the atlas knows, one block per cluster of the data, in its own colour.',
    'Drag a block onto the Semantic playground to place its dot. Click a block to make it the one a click on the playground places.',
    'Double-click a block to rename it (Enter keeps the name, empty brings the original back); it is remembered for the next sessions.',
    'Clear removes every dot from the playground.',
  ],
  'Atlas': [
    'The data of the model seen in 3D: each point is a real sound, in the colour of its source. The ring is the mean of the sources you selected; the orange point is the embedding being made now.',
    'Drag to rotate the view. Rotate turns it slowly by itself.',
  ],
  'FX': [
    'Four effects on the sound you hear, after the model: Saturator, EQ, Reverb and Ring mod.',
    'The power button at the top of each effect switches it on and off. Drag an effect by its head to another place to change the order of the chain.',
    'Turn a knob by dragging up or down (hold Shift for fine control), or with the wheel. Double-click puts it back to its default; click its number to type a value.',
  ],
  'Semantic playground': [
    'Place sources as dots and move the control point: the embedding is the mean of the sources around it, so the sound goes from one to the other as you move.',
    'Press and move to steer the point; a click puts it there. With Glide on, a click makes the point travel to it in a straight line, in the time of the knob next to it.',
    'Edit (or hold Ctrl) lets you drag the dots instead of steering. Double-click a dot to remove it.',
    'The gray area is the zone you can move in: the polygon of the sources.',
  ],
  'Structure playground': [
    'The part of the sound that the sources do not describe: its details, as a point on a disk. Drag the point to change them.',
    'Auto moves the point by itself, following how the data tends to change, with a new target every 1 / rate seconds (the knob next to it). While it is on, the point cannot be dragged.',
  ],
  'Model': [
    'The generator. The menu at the top changes the model (it stops the sound first).',
    'NFE is the number of steps the model takes for each piece of sound: more is better and slower. CFG is how strongly it follows the embedding. Both apply when you release the knob.',
    'The log shows the load (green is faster than real time), the audio ahead of the player and the underruns. Volume sets the loudness; the meter shows the level of each channel.',
    'Play starts the sound, Stop ends it, and the red button records what you hear to a WAV file.',
  ],
  // Score mode
  'Score sources': [
    'The sounds of the model that you can use, grouped by cluster, in the colour of the cluster. Each one is a real moment of the data, with its audio.',
    'Click one to hear it. Drag one onto the Semantic playground to place it there, or straight onto the Timeline to make a clip of it.',
  ],
  'Score playground': [
    'Place several sources as dots, then move the point between them: it stands for the mix of the sources around it, and the lines show how much of each. It works as in Live.',
    'Press and move on the empty area to steer the point. Edit (or hold Ctrl) lets you drag the dots. Double-click a dot to remove it; double-click an empty place to make a new dot there: it stands for the mix that was under it.',
    'Score (or hold Shift) makes every dot, and the point, glow: now you can drag any of them onto the Timeline to make a clip.',
  ],
  'Timeline': [
    'The piece, from left to right. Each clip is one embedding (a source, or a mix of sources) held for its length; a new clip lasts 3 seconds.',
    'Drag a source, a dot or the point onto the timeline to add a clip. Drag a clip to move it, drag its right edge to change its length, double-click it to remove it.',
    'Between two clips the embedding goes from the one to the other across the gap, marked with the symbol (slerp for now; with no gap it is a cut). The scale fits the piece by itself, and generating renders from the first clip to the last.',
  ],
  'Score model': [
    'The model that makes the piece, and what you choose for it. NFE is the number of steps the generator takes for each part of the sound: more steps, better and slower. CFG is how strongly the sound follows the semantics.',
    'The seed makes a piece repeatable: the same score with the same seed makes the same sound. The dice picks a new one.',
    'Generate makes the whole piece in one pass and keeps it in Takes.',
  ],
  'Score atlas': [
    'The atlas in 3-D, as in Live. When a take plays, the line is the path it followed through the atlas and the orange dot is where the sound is now.',
  ],
  'Takes': [
    'What you generated, newest first, each with the settings that made it. They are kept on disk, so they are here the next time too.',
    'Play one (a second press stops it; the atlas shows its path), download it as a wav, or remove it for good.',
  ],
  'Log': [
    'What the page is doing: the model that loaded and, when you generate, the report of the render. The top line says where the piece stands.',
  ],
};

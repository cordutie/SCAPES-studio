// The Score page. Loads the theme, asks the server for the sources of the model and mounts the blocks. Each block is one file in blocks/
// that exports mount(root, ctx); the list below and web/score/layout.html are all there is to add, remove or reorder one.
// ctx: {size (canvas side), root, S, bus, api, theme, palette, preview, playground, timeline}
import {bus} from '../shared/core/state.js';
import {S} from './core/state.js';
import {makeApi} from './core/api.js';
import {PALETTE, readTheme, loadCss} from '../shared/theme.js';

const BLOCKS = ['timeline', 'playground', 'sources'];     // the sources and the playground use the timeline: it goes first

export async function start({element, server}) {
  await loadCss('/web/shared/theme.css');
  const root = element.querySelector('#demo');
  const api = makeApi(server);
  const boot = await api.boot();
  if (boot.no_models) {                           // no model with snippets yet: say where to put one
    root.innerHTML = `<div class="notice"><h2>No models yet</h2>
      <p>Score mode needs at least one model with its snippets (the audio of its sources), and <code>${boot.dir}</code> has none.</p>
      <p>The models are in the Hugging Face repository <a href="https://huggingface.co/${boot.repo}" target="_blank">${boot.repo}</a>: download a folder from there into the models folder (or start the app with <code>--fetch</code>), then reload this page.</p>
      <p>To make a model of your own, see <a href="${boot.github}" target="_blank">the README</a>.</p>
      <p><a href="/">Back to the start</a></p></div>`;
    return;
  }
  Object.assign(S, {model: boot.model, names: boot.names, sources: boot.sources});
  S.dots = Array(S.sources.length).fill(null);
  const theme = readTheme(root);
  const size = parseInt(getComputedStyle(root).getPropertyValue('--canvas'), 10);
  const ctx = {size, root, S, bus, api, theme, palette: PALETTE, models: boot.models};
  for (const name of BLOCKS) {
    const module = await import(`./blocks/${name}.js?v=${Date.now()}`);
    module.mount(root.querySelector(`[data-block=${name}]`), ctx);
  }
  bus.emit('boot');
  window.__score = ctx;            // for tests and the console
}

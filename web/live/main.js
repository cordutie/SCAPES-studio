// The page. Loads the theme, asks the server for the atlas, makes the player, and mounts the blocks. Each block is one file in
// blocks/ that exports mount(root, ctx); the list below and web/layout.html are all there is to add, remove or reorder one.
// ctx: {size (canvas side), root, S (state), bus, api (server functions), theme, palette, live, player, plane}
import {S, bus} from '../shared/core/state.js';
import {makeApi} from './core/api.js';
import {createLive} from './core/live.js';
import {PALETTE, CANVAS, readTheme, loadCss} from '../shared/theme.js';

const BLOCKS = ['plane', 'disk', 'view3d', 'clusters', 'effects', 'generation'];   // clusters needs the plane: after it

export async function start({element, server}) {
  await loadCss('/web/shared/theme.css');
  const root = element.querySelector('#demo');
  const api = makeApi(server);
  root.style.setProperty('--canvas', CANVAS + 'px');
  const ctx = {size: CANVAS, root, S, bus, api, theme: readTheme(root), palette: PALETTE, live: createLive(api), player: null};

  const boot = await api.boot();
  if (boot.no_models) {                           // no model folder yet: say where to put one
    root.innerHTML = `<div class="notice"><h2>No models yet</h2>
      <p>Live mode needs at least one model, and <code>${boot.dir}</code> has none.</p>
      <p>The models are in the Hugging Face repository <a href="https://huggingface.co/${boot.repo}" target="_blank">${boot.repo}</a>: download a folder from there into the models folder (or start the app with <code>--fetch</code>), then reload this page.</p>
      <p>To make a model of your own, see <a href="${boot.github}" target="_blank">the README</a>.</p>
      <p><a href="/">Back to the start</a></p></div>`;
    return;
  }
  Object.assign(S, {K: boot.K, names: boot.names, labels: boot.labels, cloud: boot.cloud, hasPrior: boot.has_prior, info: boot.info});
  S.dots = Array(S.K).fill(null);

  try {
    const {createPlayer} = await import('./audio/player.js?v=' + Date.now());
    ctx.player = createPlayer(S.info);
  } catch (e) { console.error('no audio', e); }

  for (const name of BLOCKS) {
    const module = await import(`./blocks/${name}.js?v=${Date.now()}`);
    module.mount(root.querySelector(`[data-block=${name}]`), ctx);
  }
  bus.emit('boot');
  if (ctx.player) await ctx.player.init().catch((e) => console.error('audio init', e));
  window.__demo = ctx;            // for tests and the console
}

// The functions of the server (demo/live_api.py), as the page calls them. `server` is Gradio's object.
export function makeApi(server) {
  return {
    boot: () => server.boot(0),
    models: () => server.models(0),
    loadModel: (name) => server.load_model({name}),
    live: (state) => server.live(state),
    project: (state) => server.project(state),
    priorStep: (state) => server.prior_step(state),
    rename: (state) => server.rename(state),
  };
}

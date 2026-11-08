// The functions of the server (studio/score/score_api.py), as the page calls them. `server` is Gradio's object.
export function makeApi(server) {
  return {
    boot: (name) => server.boot(name ? {name} : {}),
    locate: (state) => server.locate(state),
  };
}

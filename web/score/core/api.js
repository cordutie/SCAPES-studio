// The functions of the server (studio/score/score_api.py), as the page calls them. `server` is Gradio's object.
export function makeApi(server) {
  return {
    boot: (name) => server.boot(name ? {name} : {}),
    locate: (state) => server.locate(state),
    takes: () => server.list_takes(0),
    deleteTake: (state) => server.delete_take(state),
    render: (state) => server.render(state),
    renderStatus: () => server.render_status(0),
    trace: (state) => server.take_trace(state),
  };
}

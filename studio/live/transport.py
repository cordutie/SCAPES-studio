"""The audio line to the browser: one WebSocket, /ws/audio.

browser -> server (JSON)   {"op": "play"} | {"op": "stop"} | {"op": "params", "nfe": n, "cfg": c}
                           {"op": "played", "run": id, "frames": n}   (what the player has played: paces the generator)
                           {"op": "underrun", "run": id}              (the player ran dry: the buffer grows)
server -> browser          JSON {"type": "info" | "run" | "status" | "ended" | "error", ...}
                           binary: 16-bit little-endian PCM, interleaved channels, one chunk per generated hop
The browser side is web/live/audio/player.js. In the combined app it is at /live/ws/audio (the page builds the address from its own)."""
import asyncio

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from studio import config


# What the engine thread talks to. Calls come from that thread; the queue is read on the event loop.
class _Sink:
    def __init__(self, loop, queue):
        self.loop, self.queue = loop, queue

    def audio(self, samples):                      # float32 [ch, n] -> int16 interleaved bytes (always 2 channels: a mono codec is doubled)
        if samples.shape[0] == 1:
            samples = np.repeat(samples, 2, axis=0)
        pcm = (np.clip(samples, -1.0, 1.0).T * 32767.0).astype("<i2").tobytes()
        self.loop.call_soon_threadsafe(self.queue.put_nowait, pcm)

    def ended(self):
        self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "ended"})


def add_audio_route(app, manager, prefix=""):
    @app.websocket(prefix + "/ws/audio")
    async def audio(ws: WebSocket):
        await ws.accept()
        session = manager.session
        if session is None:                        # no model loaded: nothing to play
            await ws.close()
            return
        queue = asyncio.Queue()
        sink = _Sink(asyncio.get_running_loop(), queue)
        session.attach(sink)
        await ws.send_json(dict(session.info(), type="info"))

        async def sender():                         # audio and "ended", in the order the engine produced them
            while True:
                item = await queue.get()
                await (ws.send_bytes(item) if isinstance(item, bytes) else ws.send_json(item))

        async def reporter():
            while True:
                await asyncio.sleep(config.STATUS_PERIOD_S)
                await ws.send_json(dict(session.status(), type="status"))

        tasks = [asyncio.create_task(sender()), asyncio.create_task(reporter())]
        try:
            while True:
                msg = await ws.receive_json()
                op = msg.get("op")
                if op == "play":
                    run, why = session.play()
                    await ws.send_json({"type": "run", "id": run} if run else {"type": "error", "message": why})
                elif op == "stop":
                    session.stop()
                elif op == "params":
                    session.set_params(msg.get("nfe"), msg.get("cfg"))
                elif op == "played":
                    session.acked(msg["run"], msg["frames"])
                elif op == "underrun":
                    session.underrun(msg["run"])
        except WebSocketDisconnect:
            pass
        finally:
            for task in tasks:
                task.cancel()
            session.detach(sink)

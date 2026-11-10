"""Runs a function with a GPU when the app is on ZeroGPU (a Hugging Face Space): the GPU exists only inside such a call. Anywhere else
(and where the spaces package is missing) the function is used as it is, so the GPU is whatever torch sees."""
from studio import config

try:
    import spaces
except ImportError:
    spaces = None


def on_gpu(fn):
    if spaces is None or not config.ON_HUGGING_FACE:
        return fn
    return spaces.GPU(duration=config.GPU_SECONDS)(fn)

"""Thread-scoped system wake requests; the display can sleep normally."""

import ctypes
import os


class Awake:
    def __init__(self, call=None):
        self.call = call
        if call is None and os.name == "nt":
            self.call = ctypes.windll.kernel32.SetThreadExecutionState

    def __enter__(self):
        if self.call:
            self.call(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        return self

    def __exit__(self, *_):
        if self.call:
            self.call(0x80000000)

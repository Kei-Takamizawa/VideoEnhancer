"""In-process gateway adapter; no requests to the token-authenticated desktop API."""

import threading
from pathlib import Path


class EngineAdapter:
    def __init__(self, engine, home: Path, settings: dict):
        self.engine = engine
        self.home = home
        self.settings = settings
        self._library = None
        self._library_lock = threading.Lock()

    @property
    def library(self):
        from videoenhancer.remote.library import Library, resolve_library_folder

        with self._library_lock:
            if self._library is None:
                folder = resolve_library_folder(self.settings.get("library_folder", ""))
                self._library = Library(self.home, folder)
            return self._library

"""Direct process-scoped Windows PDH memory counters, without a shell."""

import ctypes
import os
from ctypes import wintypes


class ProcessMemoryCounters:
    api: ctypes.CDLL
    query: ctypes.c_void_p
    counters: list[ctypes.c_void_p]

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows GPU process counters are unavailable.")
        self.api = ctypes.WinDLL("pdh")
        self.query = ctypes.c_void_p()
        self.api.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.c_void_p]
        self.api.PdhAddEnglishCounterW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        self.api.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        self.api.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        self.api.PdhGetFormattedCounterArrayW.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        if self.api.PdhOpenQueryW(None, 0, ctypes.byref(self.query)):
            raise OSError("Could not open GPU process memory counters.")
        self.counters = []
        try:
            for name in ("Dedicated Usage", "Shared Usage"):
                counter = ctypes.c_void_p()
                if self.api.PdhAddEnglishCounterW(
                    self.query, f"\\GPU Process Memory(*)\\{name}", 0, ctypes.byref(counter)
                ):
                    raise OSError("GPU process memory counters are unavailable.")
                self.counters.append(counter)
        except BaseException:
            self.close()
            raise

    def read(self, pid: int) -> tuple[int | None, int | None]:
        class Value(ctypes.Structure):
            _fields_ = [("status", wintypes.DWORD), ("number", ctypes.c_longlong)]

        class Item(ctypes.Structure):
            _fields_ = [("name", wintypes.LPWSTR), ("value", Value)]

        if self.api.PdhCollectQueryData(self.query):
            raise OSError("Could not sample GPU process memory counters.")
        numbers = []
        for counter in self.counters:
            size, count = wintypes.DWORD(), wintypes.DWORD()
            self.api.PdhGetFormattedCounterArrayW(
                counter, 0x400, ctypes.byref(size), ctypes.byref(count), None
            )
            if not size.value:
                raise OSError("GPU process memory counters have no instances.")
            buffer = ctypes.create_string_buffer(size.value)
            if self.api.PdhGetFormattedCounterArrayW(
                counter, 0x400, ctypes.byref(size), ctypes.byref(count), buffer
            ):
                raise OSError("Could not read GPU process memory counters.")
            items = ctypes.cast(buffer, ctypes.POINTER(Item))
            values = [
                items[i].value.number
                for i in range(count.value)
                if items[i].name.lower().startswith(f"pid_{pid}_")
                and items[i].value.status in (0, 1)
            ]
            numbers.append(sum(values) if values else None)
        return numbers[0], numbers[1]

    def close(self) -> None:
        if self.query.value:
            self.api.PdhCloseQuery(self.query)
            self.query = ctypes.c_void_p()

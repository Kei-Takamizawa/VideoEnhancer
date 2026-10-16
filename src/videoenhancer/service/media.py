"""Single byte ranges for recorded History media."""

import re


def byte_range(value: str | None, size: int) -> tuple[int, int]:
    if value is None:
        return 0, size - 1
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip(), re.IGNORECASE)
    if not match or size <= 0:
        raise ValueError("Invalid media byte range.")
    first, last = match.groups()
    if not first:
        if not last or int(last) <= 0:
            raise ValueError("Invalid media byte range.")
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(size - 1, int(last)) if last else size - 1
    if start >= size or end < start:
        raise ValueError("Media byte range is outside this file.")
    return start, end

"""Bound early-error bodies before closing an HTTP connection."""


def drain_error_body(handler, status):
    if getattr(handler, "_body_consumed", False) or not hasattr(handler, "headers"):
        return status
    handler._body_consumed = True
    lengths = handler.headers.get_all("Content-Length", [])
    text = handler.headers.get("Content-Length", "0")
    if handler.headers.get("Transfer-Encoding") or len(lengths) > 1 or not text.isdecimal():
        return status
    length = int(text)
    if length > 65536:
        return 413
    if length:
        handler.connection.settimeout(15)
        handler.rfile.read(length)
    return status

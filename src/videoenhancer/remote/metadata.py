"""Read optional remote ownership without assuming a source schema."""


def remote_info(job):
    source = job.get("source")
    remote = source.get("remote") if isinstance(source, dict) else None
    return remote if isinstance(remote, dict) else None

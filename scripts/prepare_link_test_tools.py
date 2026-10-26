"""Explicit CI setup; media tests use only local synthetic servers."""

import argparse
import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from videoenhancer.service.link_tools import ReleaseRedirect, ToolManager


class GitHubApiToken(urllib.request.BaseHandler):
    """CI-only credentials; unredirected headers cannot leak to release assets."""

    def __init__(self, token: str):
        self.token = token

    def https_request(self, request):
        url = urlsplit(request.full_url)
        if self.token and url.hostname == "api.github.com" and url.port in (None, 443):
            request.add_unredirected_header("Authorization", f"Bearer {self.token}")
        return request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("home", type=Path)
    args = parser.parse_args()
    manager = ToolManager(args.home)
    manager.opener = urllib.request.build_opener(
        ReleaseRedirect(), GitHubApiToken(os.environ.get("GITHUB_TOKEN", ""))
    )
    plan = manager.check("stable")
    manager.install("stable", plan["id"], lambda _: None, lambda: False)
    for tool in ("yt-dlp", "deno"):
        manager.executable(tool)
    print(json.dumps(manager.status()))


if __name__ == "__main__":
    main()

"""CI authentication stays on the GitHub API and out of the product path."""

import importlib.util
import io
import urllib.request
from pathlib import Path

import pytest

from videoenhancer.service.link_tools import ReleaseRedirect, ToolManager

spec = importlib.util.spec_from_file_location(
    "prepare_link_test_tools",
    Path(__file__).resolve().parents[1] / "scripts" / "prepare_link_test_tools.py",
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


@pytest.mark.parametrize("token", ["", "synthetic-ci-token"])
@pytest.mark.parametrize(
    "host", ["api.github.com", "github.com", "release-assets.githubusercontent.com"]
)
def test_ci_authentication_is_api_only(token, host):
    request = urllib.request.Request(f"https://{host}/synthetic")
    setup.GitHubApiToken(token).https_request(request)
    assert request.get_header("Authorization") == (
        f"Bearer {token}" if token and host == "api.github.com" else None
    )
    if token and host == "api.github.com":
        redirected = ReleaseRedirect().redirect_request(
            request, None, 302, "Found", {}, "https://github.com/synthetic"
        )
        setup.GitHubApiToken(token).https_request(redirected)
        assert redirected.get_header("Authorization") is None


def test_product_request_ignores_ci_token(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-ci-token")
    calls = []

    class Response(io.BytesIO):
        url = "https://api.github.com/repos/synthetic/releases/latest"

    class Publisher:
        def open(self, request, timeout):
            calls.append(request)
            return Response(b"{}")

    manager = ToolManager(tmp_path)
    manager.opener = Publisher()
    assert manager._read(Response.url) == b"{}"
    assert calls[0].get_header("Authorization") is None

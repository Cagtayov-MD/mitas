from __future__ import annotations

from core.api.tedial.router import (
    rewrite_login_proxy_text,
    _is_authenticated_default_page,
    _rewrite_login_location,
    _should_return_to_poc_ui,
)


def test_rewrite_login_proxy_text_keeps_itclient_inside_local_proxy() -> None:
    html = """
    <base href="https://evo.int.trt.net.tr:8885/iTClient/" />
    <form action="/iTClient/j_security_check">
      <script src="/iTClient/js/app.js"></script>
      <a href="https://evo.int.trt.net.tr:8885/iTClient/tarsys/search/loadDefaultSearch.html">search</a>
      <img src="https://evo.int.trt.net.tr:8181/MamService/KeyframeService/repo/asset/0">
    </form>
    """

    rewritten = rewrite_login_proxy_text(html, "https://evo.int.trt.net.tr:8885")

    assert 'action="/api/tedial/login/iTClient/j_security_check"' in rewritten
    assert 'src="/api/tedial/login/iTClient/js/app.js"' in rewritten
    assert 'href="/api/tedial/login/iTClient/tarsys/search/loadDefaultSearch.html"' in rewritten
    assert "https://evo.int.trt.net.tr:8181/MamService/KeyframeService" in rewritten


def test_rewrite_login_location_maps_upstream_redirects_to_local_proxy() -> None:
    base_url = "https://evo.int.trt.net.tr:8885"

    assert (
        _rewrite_login_location(
            "https://evo.int.trt.net.tr:8885/iTClient/tarsys/search/loadDefaultSearch.html",
            base_url,
        )
        == "/api/tedial/login/iTClient/tarsys/search/loadDefaultSearch.html"
    )
    assert _rewrite_login_location("/iTClient/login.html", base_url) == "/api/tedial/login/iTClient/login.html"


def test_successful_default_login_returns_to_poc_ui() -> None:
    path = "/iTClient/tarsys/search/loadDefaultSearch.html"

    assert _should_return_to_poc_ui("GET", path, path, "connected")
    assert not _should_return_to_poc_ui("GET", path, path, "connecting")
    assert not _should_return_to_poc_ui("POST", path, path, "connected")


def test_default_page_auth_check_rejects_login_html() -> None:
    class Resp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = '<form><input name="j_password"></form>'

    path = "/iTClient/tarsys/search/loadDefaultSearch.html"

    assert not _is_authenticated_default_page("GET", path, path, Resp())

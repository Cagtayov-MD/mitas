from __future__ import annotations

import importlib.util

import pytest


def test_tedial_router_module_imports_without_fastapi_dependency() -> None:
    from core.api.tedial import create_tedial_router
    import core.api.tedial.app as tedial_app

    assert callable(create_tedial_router)
    assert callable(tedial_app.create_app)
    assert "/api/tedial/session/start" in tedial_app.TEDIAL_POC_HTML
    assert "/api/tedial/search" in tedial_app.TEDIAL_POC_HTML
    assert "/api/tedial/assets/" in tedial_app.TEDIAL_POC_HTML
    assert "import-plan" in tedial_app.TEDIAL_POC_HTML
    assert "/enqueue" in tedial_app.TEDIAL_POC_HTML
    assert "Kuyru" in tedial_app.TEDIAL_POC_HTML
    assert "ASR+OCR" in tedial_app.TEDIAL_POC_HTML
    assert "/run" in tedial_app.TEDIAL_POC_HTML


def test_create_router_has_clear_error_without_runtime_dependencies() -> None:
    from core.api.tedial import create_tedial_router

    if importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"):
        router = create_tedial_router()
        assert router.prefix == "/api/tedial"
    else:
        with pytest.raises(RuntimeError, match="requires fastapi"):
            create_tedial_router()

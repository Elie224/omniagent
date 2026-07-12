"""Tests unitaires du BrowserService."""
from browser_service.service import BrowserService, BrowserConfig


def test_config_defaults():
    svc = BrowserService()
    assert svc.config.headless is True
    assert svc.config.locale == "fr-FR"


def test_backend_selection():
    svc = BrowserService()
    svc.use_backend("playwright")
    assert svc._backend == "playwright"
    try:
        svc.use_backend("nope")
    except ValueError:
        return
    raise AssertionError("Aurait du lever ValueError")
import pytest

from vymcp.config import ServerConfig, writes_enabled


def test_requires_base_url(monkeypatch):
    monkeypatch.delenv("VYMANAGER_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="VYMANAGER_BASE_URL"):
        ServerConfig.from_env()


def test_stdio_requires_token(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h")
    monkeypatch.delenv("VYMANAGER_API_TOKEN", raising=False)
    monkeypatch.delenv("VYMCP_TRANSPORT", raising=False)  # default stdio
    with pytest.raises(RuntimeError, match="VYMANAGER_API_TOKEN"):
        ServerConfig.from_env()


def test_http_does_not_require_token(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h:8000/")
    monkeypatch.setenv("VYMCP_TRANSPORT", "http")
    monkeypatch.delenv("VYMANAGER_API_TOKEN", raising=False)
    cfg = ServerConfig.from_env()
    assert cfg.transport == "http"
    assert cfg.base_url == "http://h:8000"  # trailing slash stripped
    assert cfg.api_token is None


def test_http_public_url_default(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h")
    monkeypatch.setenv("VYMCP_TRANSPORT", "http")
    monkeypatch.setenv("VYMCP_HOST", "0.0.0.0")
    monkeypatch.setenv("VYMCP_PORT", "9000")
    monkeypatch.delenv("VYMCP_PUBLIC_URL", raising=False)
    cfg = ServerConfig.from_env()
    assert cfg.public_url == "http://0.0.0.0:9000"


def test_client_config_carries_token(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h")
    monkeypatch.setenv("VYMANAGER_API_TOKEN", "vym_x")
    monkeypatch.setenv("VYMANAGER_VERIFY_SSL", "false")
    cfg = ServerConfig.from_env()
    cc = cfg.client_config("vym_abc")
    assert cc.api_token == "vym_abc"
    assert cc.base_url == "http://h"
    assert cc.verify_ssl is False


def test_bad_transport(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h")
    monkeypatch.setenv("VYMCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(RuntimeError, match="stdio.*http|http.*stdio"):
        ServerConfig.from_env()


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("1", True), ("on", True),
    ("false", False), ("", False), ("nope", False),
])
def test_writes_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("VYMANAGER_ENABLE_WRITES", value)
    assert writes_enabled() is expected


def test_writes_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VYMANAGER_ENABLE_WRITES", raising=False)
    assert writes_enabled() is False

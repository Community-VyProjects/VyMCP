import pytest

from vymcp.config import Config, writes_enabled


def test_from_env_requires_url_and_token(monkeypatch):
    monkeypatch.delenv("VYMANAGER_BASE_URL", raising=False)
    monkeypatch.delenv("VYMANAGER_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError) as exc:
        Config.from_env()
    assert "VYMANAGER_BASE_URL" in str(exc.value)
    assert "VYMANAGER_API_TOKEN" in str(exc.value)


def test_from_env_parses_values(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://host:8000/")
    monkeypatch.setenv("VYMANAGER_API_TOKEN", "vym_abc")
    monkeypatch.setenv("VYMANAGER_VERIFY_SSL", "false")
    monkeypatch.setenv("VYMANAGER_TIMEOUT", "12")
    cfg = Config.from_env()
    assert cfg.base_url == "http://host:8000"  # trailing slash stripped
    assert cfg.api_token == "vym_abc"
    assert cfg.verify_ssl is False
    assert cfg.timeout == 12.0


def test_verify_ssl_defaults_true(monkeypatch):
    monkeypatch.setenv("VYMANAGER_BASE_URL", "http://h")
    monkeypatch.setenv("VYMANAGER_API_TOKEN", "vym_x")
    monkeypatch.delenv("VYMANAGER_VERIFY_SSL", raising=False)
    assert Config.from_env().verify_ssl is True


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("", False), ("nope", False),
])
def test_writes_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("VYMANAGER_ENABLE_WRITES", value)
    assert writes_enabled() is expected


def test_writes_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VYMANAGER_ENABLE_WRITES", raising=False)
    assert writes_enabled() is False

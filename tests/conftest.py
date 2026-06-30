"""Shared test fixtures. No network or live device — VyManager is faked with
httpx.MockTransport, so the whole suite is deterministic.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from vymcp import client as client_module
from vymcp.client import VyManagerClient
from vymcp.config import Config


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> VyManagerClient:
    """Build a VyManagerClient backed by a mock transport using `handler`."""
    config = Config(base_url="http://vymanager.test", api_token="vym_test", verify_ssl=False)
    return VyManagerClient(config, transport=httpx.MockTransport(handler))


@pytest.fixture
def make_mock_client():
    """Factory fixture: call with a handler to get a mock-backed VyManagerClient."""
    return make_client


@pytest.fixture
def install_client():
    """Install a mock-backed shared client; restore afterwards."""
    installed: list[VyManagerClient] = []

    def _install(handler: Callable[[httpx.Request], httpx.Response]) -> VyManagerClient:
        c = make_client(handler)
        client_module.set_client(c)
        installed.append(c)
        return c

    yield _install
    client_module.set_client(None)


@pytest.fixture
def collect_write_tools():
    """Register the write tools into a stub and return {name: fn}."""
    from vymcp.writes import register_write_tools

    def _collect() -> dict:
        fns: dict = {}

        class _Stub:
            def tool(self):
                def deco(fn):
                    fns[fn.__name__] = fn
                    return fn

                return deco

        register_write_tools(_Stub())
        return fns

    return _collect

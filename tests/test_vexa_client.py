import sys
from types import SimpleNamespace

import pytest

from src.integrations.vexa_client import VexaClient, VexaConfig


@pytest.mark.asyncio
async def test_vexa_connect_uses_extra_headers_for_websockets_10(monkeypatch):
    calls = {}

    class FakeWebSocket:
        async def close(self):
            pass

    async def connect(url, extra_headers=None, ping_interval=None):
        calls["url"] = url
        calls["extra_headers"] = extra_headers
        calls["ping_interval"] = ping_interval
        return FakeWebSocket()

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))

    client = VexaClient(VexaConfig(host="vexa.local", port=8080, api_key="secret"))
    await client.connect()

    assert calls["url"] == "ws://vexa.local:8080/ws/transcripts"
    assert calls["extra_headers"] == {"Authorization": "Bearer secret"}
    assert calls["ping_interval"] == 30.0


@pytest.mark.asyncio
async def test_vexa_connect_supports_additional_headers_when_available(monkeypatch):
    calls = {}

    class FakeWebSocket:
        async def close(self):
            pass

    async def connect(url, additional_headers=None, ping_interval=None):
        calls["additional_headers"] = additional_headers
        return FakeWebSocket()

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))

    client = VexaClient(VexaConfig(host="vexa.local", port=8080, api_key="secret"))
    await client.connect()

    assert calls["additional_headers"] == {"Authorization": "Bearer secret"}

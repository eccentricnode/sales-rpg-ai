import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.vexa_client import TranscriptEvent


def test_home_page_exposes_vexa_join_controls():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")

    from src.web.app import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="vexaJoinForm"' in response.text
    assert 'id="meetingUrlInput"' in response.text
    assert 'id="joinMeetingBtn"' in response.text
    assert "/static/js/audio-client.js" in response.text


def test_audio_client_posts_vexa_join_payload():
    js = "src/web/static/js/audio-client.js"
    with open(js) as f:
        content = f.read()

    assert "meetingUrlInput" in content
    assert "fetch('/api/vexa/join'" in content
    assert "meeting_url: meetingUrl" in content
    assert "connectMonitorWebSocket" in content


def test_vexa_join_route_dispatches_bot_and_exposes_status():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")

    from src.web import app as app_module

    class FakeVexaClient:
        instance = None

        def __init__(self, config):
            self.config = config
            self.callbacks = []
            self.connected = False
            self.streaming = False
            FakeVexaClient.instance = self

        def on_transcript(self, callback):
            self.callbacks.append(callback)

        async def connect(self):
            self.connected = True

        async def create_meeting_bot(self, meeting_url, bot_name="Sales RPG AI"):
            self.meeting_url = meeting_url
            self.bot_name = bot_name
            return "meeting-123"

        async def start_streaming(self):
            self.streaming = True

        async def stop_streaming(self):
            self.streaming = False

        async def disconnect(self):
            self.connected = False

    fake_analyzer = MagicMock()
    fake_analyzer.client = MagicMock()
    fake_analyzer.model = "fake-model"

    with (
        patch.object(app_module, "VexaClient", FakeVexaClient),
        patch.object(app_module, "VexaConfig", lambda: SimpleNamespace()),
        patch.object(app_module, "StreamingAnalyzer", return_value=fake_analyzer),
        patch.object(app_module, "AnalysisOrchestrator") as orchestrator_cls,
        patch.object(app_module, "SummaryEngine") as summary_cls,
        patch.object(app_module, "get_llm_config", return_value=SimpleNamespace(api_key="k", base_url="u", model="m")),
    ):
        orchestrator = MagicMock()
        orchestrator.submit_analysis = MagicMock()
        orchestrator_cls.return_value = orchestrator

        summary_engine = MagicMock()
        summary_engine.add_transcript = MagicMock()
        summary_cls.return_value = summary_engine

        client = TestClient(app_module.app)
        response = client.post(
            "/api/vexa/join",
            json={"meeting_url": "https://meet.google.com/abc-defg-hij", "bot_name": "Sales Coach"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "joined", "meeting_id": "meeting-123"}

        status = client.get("/api/vexa/status")
        assert status.status_code == 200
        assert status.json()["active"] is True
        assert status.json()["meeting_id"] == "meeting-123"

        fake_client = FakeVexaClient.instance
        assert fake_client.connected is True
        assert fake_client.streaming is True
        assert fake_client.meeting_url == "https://meet.google.com/abc-defg-hij"
        assert fake_client.bot_name == "Sales Coach"

        stop = client.post("/api/vexa/stop")
        assert stop.status_code == 200
        assert stop.json() == {"status": "stopped"}


@pytest.mark.asyncio
async def test_vexa_transcript_bridge_feeds_summary_and_buffer(monkeypatch):
    from src.web import app as app_module

    class FakeClient:
        def __init__(self):
            self.callbacks = []

        def on_transcript(self, callback):
            self.callbacks.append(callback)

    class FakeBuffer:
        def __init__(self):
            self.calls = []

        def on_transcript_chunk(self, text, segments):
            self.calls.append((text, segments))

    async def fake_broadcast(message):
        broadcasts.append(message)

    scheduled = []

    def fake_run_coroutine_threadsafe(coro, loop):
        task = loop.create_task(coro)
        scheduled.append(task)
        return task

    broadcasts = []
    client = FakeClient()
    buffer_manager = FakeBuffer()
    summary_engine = MagicMock()
    monkeypatch.setattr(app_module.manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(app_module.asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    app_module._create_vexa_transcript_bridge(
        client=client,
        buffer_manager=buffer_manager,
        summary_engine=summary_engine,
        loop=asyncio.get_running_loop(),
    )

    event = TranscriptEvent(
        text="We need to reduce deployment risk.",
        speaker="prospect",
        start=1.0,
        end=2.0,
        is_final=True,
        meeting_id="meeting-123",
    )
    client.callbacks[0](event)
    await asyncio.gather(*scheduled)

    summary_engine.add_transcript.assert_called_with("prospect: We need to reduce deployment risk.")
    assert buffer_manager.calls == [
        (
            "We need to reduce deployment risk.",
            [{"text": "We need to reduce deployment risk.", "start": 1.0, "end": 2.0, "completed": True}],
        )
    ]
    assert broadcasts[-1]["source"] == "vexa"
    assert broadcasts[-1]["speaker"] == "prospect"


def test_vexa_join_route_rejects_unsupported_meeting_url():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")

    from src.web.app import app

    client = TestClient(app)
    response = client.post("/api/vexa/join", json={"meeting_url": "https://example.com/not-a-meeting"})

    assert response.status_code == 400
    assert "Zoom, Google Meet, or Microsoft Teams" in response.json()["error"]

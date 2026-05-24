"""
Vexa WebSocket client for real-time meeting transcript streaming.

Connects to a self-hosted Vexa instance to receive real-time transcripts
from Zoom, Google Meet, or Microsoft Teams calls. Feeds transcripts into
the Sales RPG AI coaching pipeline via DualBufferManager.

Vexa is Apache 2.0 licensed, self-hostable, and GDPR-compliant when
self-hosted (data never leaves your infrastructure).

Environment variables:
    VEXA_HOST: Vexa server hostname (default: localhost)
    VEXA_PORT: Vexa server port (default: 8080)
    VEXA_API_KEY: API key for Vexa authentication
    VEXA_WS_PATH: WebSocket endpoint path (default: /ws/transcripts)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class VexaConfig:
    """Configuration for Vexa WebSocket client.

    Loads from environment variables by default. All settings can be
    overridden via constructor arguments.
    """

    host: str = ""
    port: int = 8080
    api_key: str = ""
    ws_path: str = "/ws/transcripts"
    reconnect_delay_seconds: float = 2.0
    max_reconnect_attempts: int = 10
    ping_interval_seconds: float = 30.0

    def __post_init__(self):
        if not self.host:
            self.host = os.environ.get("VEXA_HOST", "localhost")
        if self.port == 8080:
            env_port = os.environ.get("VEXA_PORT", "")
            if env_port:
                self.port = int(env_port)
        if not self.api_key:
            self.api_key = os.environ.get("VEXA_API_KEY", "")
        if self.ws_path == "/ws/transcripts":
            self.ws_path = os.environ.get("VEXA_WS_PATH", "/ws/transcripts")

    @property
    def ws_url(self) -> str:
        """Full WebSocket URL for the Vexa transcript stream."""
        return f"ws://{self.host}:{self.port}{self.ws_path}"


@dataclass
class TranscriptEvent:
    """A single transcript event received from Vexa."""

    text: str
    speaker: str
    start: float
    end: float
    is_final: bool
    meeting_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_segment_dict(self) -> dict:
        """Convert to the segment dict format expected by DualBufferManager."""
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "completed": self.is_final,
        }


class VexaClient:
    """WebSocket client for a self-hosted Vexa instance.

    Connects to Vexa's real-time transcript WebSocket endpoint and
    forwards transcript events to registered callbacks. Designed to
    feed the Sales RPG AI DualBufferManager or SummaryEngine.

    Usage:
        config = VexaConfig()
        client = VexaClient(config)

        # Register a callback for transcript events
        client.on_transcript(my_handler)

        # Connect and start streaming
        await client.connect()

        # Create a meeting bot for a specific call
        await client.create_meeting_bot("https://zoom.us/j/123456")

        # Start real-time transcript streaming
        await client.start_streaming()

        # When done
        await client.stop_streaming()
        await client.disconnect()
    """

    def __init__(
        self,
        config: Optional[VexaConfig] = None,
        on_transcript_callback: Optional[Callable[[TranscriptEvent], None]] = None,
    ):
        self.config = config or VexaConfig()
        self._ws = None
        self._connected = False
        self._streaming = False
        self._reconnect_count = 0
        self._callbacks: list[Callable[[TranscriptEvent], None]] = []
        self._receive_task: Optional[asyncio.Task] = None
        self._meeting_id: Optional[str] = None

        if on_transcript_callback:
            self._callbacks.append(on_transcript_callback)

    @property
    def connected(self) -> bool:
        """Whether the client is currently connected to Vexa."""
        return self._connected

    @property
    def streaming(self) -> bool:
        """Whether the client is actively receiving transcripts."""
        return self._streaming

    def on_transcript(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Register a callback for incoming transcript events.

        Args:
            callback: Function called with each TranscriptEvent.
                      Signature: (event: TranscriptEvent) -> None
        """
        self._callbacks.append(callback)

    async def connect(self) -> None:
        """Connect to the Vexa WebSocket endpoint.

        Raises:
            ConnectionError: If connection fails after max retries.
            ImportError: If websockets library is not installed.
        """
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets library required for Vexa integration. "
                "Install with: pip install websockets"
            )

        url = self.config.ws_url
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        logger.info("Connecting to Vexa at %s", url)

        try:
            self._ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=self.config.ping_interval_seconds,
            )
            self._connected = True
            self._reconnect_count = 0
            logger.info("Connected to Vexa successfully")
        except Exception as exc:
            logger.error("Failed to connect to Vexa: %s", exc)
            raise ConnectionError(f"Cannot connect to Vexa at {url}: {exc}") from exc

    async def disconnect(self) -> None:
        """Disconnect from Vexa and clean up resources."""
        self._streaming = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._connected = False
        logger.info("Disconnected from Vexa")

    async def create_meeting_bot(self, meeting_url: str, bot_name: str = "Sales RPG AI") -> str:
        """Create a Vexa meeting bot that joins the specified call.

        The bot appears as a named participant in the meeting and captures
        audio from all participants for real-time transcription.

        Args:
            meeting_url: URL of the meeting to join (Zoom, Meet, or Teams).
            bot_name: Display name for the bot in the meeting participant list.

        Returns:
            Meeting ID assigned by Vexa for this session.

        Raises:
            ConnectionError: If not connected to Vexa.
            RuntimeError: If bot creation fails.
        """
        if not self._connected or not self._ws:
            raise ConnectionError("Not connected to Vexa. Call connect() first.")

        create_msg = json.dumps({
            "type": "create_bot",
            "meeting_url": meeting_url,
            "bot_name": bot_name,
        })

        await self._ws.send(create_msg)
        response = await self._ws.recv()
        data = json.loads(response)

        if data.get("type") == "error":
            raise RuntimeError(f"Failed to create meeting bot: {data.get('message', 'Unknown error')}")

        self._meeting_id = data.get("meeting_id", "")
        logger.info("Meeting bot created for %s (meeting_id=%s)", meeting_url, self._meeting_id)
        return self._meeting_id

    async def start_streaming(self) -> None:
        """Start receiving real-time transcript events.

        Launches a background task that continuously reads from the
        WebSocket and dispatches events to registered callbacks.

        Raises:
            ConnectionError: If not connected to Vexa.
        """
        if not self._connected or not self._ws:
            raise ConnectionError("Not connected to Vexa. Call connect() first.")

        self._streaming = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("Started transcript streaming")

    async def stop_streaming(self) -> None:
        """Stop receiving transcript events.

        The WebSocket connection remains open. Call disconnect() to
        fully close the connection.
        """
        self._streaming = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped transcript streaming")

    async def _receive_loop(self) -> None:
        """Internal loop that reads WebSocket messages and dispatches events."""
        try:
            while self._streaming and self._ws:
                try:
                    raw = await asyncio.wait_for(self._ws.recv(), timeout=60.0)
                    data = json.loads(raw)
                    msg_type = data.get("type", "")

                    if msg_type == "transcript":
                        event = TranscriptEvent(
                            text=data.get("text", ""),
                            speaker=data.get("speaker", "unknown"),
                            start=float(data.get("start", 0)),
                            end=float(data.get("end", 0)),
                            is_final=data.get("is_final", False),
                            meeting_id=data.get("meeting_id", self._meeting_id or ""),
                        )
                        self._dispatch_transcript(event)

                    elif msg_type == "meeting_ended":
                        logger.info("Meeting ended (meeting_id=%s)", data.get("meeting_id"))
                        self._streaming = False

                    elif msg_type == "error":
                        logger.error("Vexa error: %s", data.get("message"))

                    elif msg_type == "bot_joined":
                        logger.info("Bot joined meeting successfully")

                except asyncio.TimeoutError:
                    # No message in 60s — send a ping to check connection
                    try:
                        await self._ws.ping()
                    except Exception:
                        logger.warning("Ping failed, connection may be lost")
                        await self._attempt_reconnect()

        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as exc:
            logger.error("Receive loop error: %s", exc)
            if self._streaming:
                await self._attempt_reconnect()

    def _dispatch_transcript(self, event: TranscriptEvent) -> None:
        """Send a transcript event to all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as exc:
                logger.error("Transcript callback error: %s", exc)

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to Vexa after a connection loss."""
        if self._reconnect_count >= self.config.max_reconnect_attempts:
            logger.error(
                "Max reconnect attempts (%d) reached. Giving up.",
                self.config.max_reconnect_attempts,
            )
            self._streaming = False
            self._connected = False
            return

        self._reconnect_count += 1
        delay = self.config.reconnect_delay_seconds * self._reconnect_count
        logger.info(
            "Reconnecting to Vexa (attempt %d/%d) in %.1fs",
            self._reconnect_count,
            self.config.max_reconnect_attempts,
            delay,
        )
        await asyncio.sleep(delay)

        try:
            await self.connect()
            if self._meeting_id:
                # Re-subscribe to the existing meeting
                resubscribe_msg = json.dumps({
                    "type": "subscribe",
                    "meeting_id": self._meeting_id,
                })
                await self._ws.send(resubscribe_msg)
            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as exc:
            logger.error("Reconnection failed: %s", exc)
            await self._attempt_reconnect()


def create_vexa_pipeline_bridge(
    vexa_client: VexaClient,
    buffer_manager,
) -> Callable[[TranscriptEvent], None]:
    """Create a bridge function that feeds Vexa transcripts into the Sales RPG AI pipeline.

    This connects the VexaClient to the DualBufferManager, translating
    Vexa transcript events into the segment format expected by the
    existing coaching pipeline.

    Args:
        vexa_client: Connected VexaClient instance.
        buffer_manager: DualBufferManager instance from src.realtime.buffer_manager.

    Returns:
        Callback function registered with the VexaClient.

    Usage:
        from src.realtime.buffer_manager import DualBufferManager
        from src.integrations.vexa_client import VexaClient, create_vexa_pipeline_bridge

        buffer_mgr = DualBufferManager(on_analysis_ready=my_analyzer)
        client = VexaClient()
        bridge = create_vexa_pipeline_bridge(client, buffer_mgr)
        # bridge is auto-registered; transcripts now flow into the pipeline
    """

    def on_vexa_transcript(event: TranscriptEvent) -> None:
        """Forward Vexa transcript events to the DualBufferManager."""
        segment_dict = event.to_segment_dict()
        text = event.text
        buffer_manager.on_transcript_chunk(text, [segment_dict])

    vexa_client.on_transcript(on_vexa_transcript)
    return on_vexa_transcript

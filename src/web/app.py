"""
FastAPI Web Application for Sales AI.

Serves the web UI and handles WebSocket connections for real-time audio streaming.
"""
# ruff: noqa: E402

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add project root to path to import src modules
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Load env vars
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from src.rag.integrity import verify_knowledge_base
from src.realtime.analysis_orchestrator import (
    AnalysisOrchestrator,
    AnalysisResult,
    AnalysisStreamChunk,
    StreamingAnalyzer,
)
from src.realtime.buffer_manager import DualBufferManager
from src.realtime.llm_provider import get_llm_config
from src.realtime.summary_engine import SummaryEngine, SummaryResult
from src.realtime.vad_transcriber import VadTranscriber

try:
    from src.integrations.vexa_client import TranscriptEvent, VexaClient, VexaConfig

    VEXA_AVAILABLE = True
except ImportError:
    TranscriptEvent = None
    VexaClient = None
    VexaConfig = None
    VEXA_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dual capture requires PyAudio (not available in Docker)
# Only needed for /ws/dual-audio endpoint
try:
    from src.audio import DualCaptureManager
    from src.transcription import DualStreamTranscriber

    DUAL_CAPTURE_AVAILABLE = True
except ImportError:
    DUAL_CAPTURE_AVAILABLE = False
    logger.info("Dual capture not available (PyAudio not installed). /ws/dual-audio disabled.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_integrity_check()
    try:
        yield
    finally:
        await shutdown_connection_cleanup()


app = FastAPI(title="Sales AI Web UI", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

WHISPER_HOST = os.getenv("WHISPER_HOST", "localhost")
WHISPER_PORT = int(os.getenv("WHISPER_PORT", "9090"))

# WebSocket origin validation
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:8080,http://127.0.0.1:8000,http://127.0.0.1:8080"
).split(",")


def validate_origin(websocket: WebSocket) -> bool:
    """Validate the Origin header on WebSocket upgrade requests.

    Returns True if the origin is allowed or if no origin is present
    (e.g., same-origin requests from some browsers).
    """
    origin = None
    for header_name, header_value in websocket.scope.get("headers", []):
        if header_name == b"origin":
            origin = header_value.decode("utf-8")
            break

    # No origin header — same-origin or non-browser client
    if origin is None:
        return True

    # Check against allowed origins (strip whitespace for env var parsing)
    allowed = [o.strip() for o in ALLOWED_ORIGINS]
    return origin in allowed


# VadTranscriber configuration
VAD_WHISPER_MODEL = os.getenv("VAD_WHISPER_MODEL", "base")
VAD_DEVICE = os.getenv("VAD_DEVICE", "cuda")
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "400"))
TRANSCRIPTION_ENGINE = os.getenv("TRANSCRIPTION_ENGINE", "vad")  # "vad" or "whisperlivekit"

# LLM configuration — loaded from src.realtime.llm_provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")
knowledge_base_integrity_status: Optional[dict[str, Any]] = None


def run_startup_integrity_check() -> dict[str, Any]:
    """Verify RAG knowledge sources before runtime code can trust retrieval."""
    result = verify_knowledge_base()
    if not result.get("valid"):
        error_summary = "; ".join(result.get("errors", [])) or "unknown integrity failure"
        raise RuntimeError(f"Knowledge base integrity check failed: {error_summary}")
    return result


async def startup_integrity_check() -> None:
    """FastAPI startup hook for security and connection lifecycle gates."""
    global knowledge_base_integrity_status
    knowledge_base_integrity_status = run_startup_integrity_check()
    start_connection_cleanup_task()


async def shutdown_connection_cleanup() -> None:
    """Stop background cleanup tasks when the app lifecycle ends."""
    await stop_connection_cleanup_task()


# Global state for broadcasting
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.transcript_history: list[dict] = []
        self.coaching_history: list[dict] = []
        self.history_limit: int = 500
        self.connection_timeout: float = 5.0
        self.ping_interval: float = 2.0

    def get_session_state(self) -> dict:
        """Return session state for reconnection payload."""
        return {
            "transcript_history": list(self.transcript_history),
            "coaching_history": list(self.coaching_history),
            "active_connections": len(self.active_connections),
            "recorder_resume": {
                "supported": False,
                "reason": "Recorder WebSocket connections carry live audio streams; reconnecting starts a new session.",
            },
        }

    async def cleanup_stale_connections(self):
        """Remove half-open connections by attempting a ping."""
        stale = []
        for conn in self.active_connections:
            try:
                await conn.send_json({"type": "ping"})
            except Exception:
                stale.append(conn)
        for conn in stale:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await websocket.send_json({"type": "session_state", **self.get_session_state()})
        # Send history to new connection
        for segment in self.transcript_history:
            await websocket.send_json(segment)
        for message in self.coaching_history:
            await websocket.send_json(message)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def reset(self):
        self.transcript_history = []
        self.coaching_history = []
        for connection in self.active_connections:
            try:
                await connection.send_json({"type": "reset"})
            except Exception:
                pass

    async def broadcast(self, message: dict):
        # Store if it's a transcript segment
        if message.get("type") == "transcript":
            self.transcript_history.append(message)
            self.transcript_history = self.transcript_history[-self.history_limit :]
        elif message.get("type") in {"analysis", "summary", "recommendation", "coaching"}:
            self.coaching_history.append(message)
            self.coaching_history = self.coaching_history[-self.history_limit :]

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast failed, removing dead connection: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


manager = ConnectionManager()
connection_cleanup_task: Optional[asyncio.Task] = None


async def _connection_cleanup_loop() -> None:
    """Scheduled heartbeat loop that removes half-open monitor connections."""
    while True:
        await asyncio.sleep(manager.ping_interval)
        await manager.cleanup_stale_connections()


def start_connection_cleanup_task() -> asyncio.Task:
    """Start the background stale-connection cleanup loop if needed."""
    global connection_cleanup_task
    if connection_cleanup_task is None or connection_cleanup_task.done():
        connection_cleanup_task = asyncio.create_task(_connection_cleanup_loop())
    return connection_cleanup_task


async def stop_connection_cleanup_task() -> None:
    """Stop the background stale-connection cleanup loop."""
    global connection_cleanup_task
    task = connection_cleanup_task
    connection_cleanup_task = None
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@dataclass
class VexaMeetingSession:
    """Runtime resources for one active Vexa meeting bridge."""

    client: Any
    meeting_id: str
    meeting_url: str
    summary_engine: SummaryEngine
    orchestrator: Optional[AnalysisOrchestrator]
    started_at: float


active_vexa_session: Optional[VexaMeetingSession] = None


def _is_supported_meeting_url(meeting_url: str) -> bool:
    """Return True for meeting URLs Vexa is expected to join."""
    parsed = urlparse(meeting_url)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower()
    supported_hosts = (
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
    )
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in supported_hosts)


async def _stop_active_vexa_session() -> None:
    """Stop and clean up the current Vexa bridge, if one exists."""
    global active_vexa_session

    session = active_vexa_session
    active_vexa_session = None
    if not session:
        return

    session.summary_engine.stop()
    if session.orchestrator:
        session.orchestrator.shutdown()

    try:
        await session.client.stop_streaming()
    finally:
        await session.client.disconnect()


def _create_vexa_transcript_bridge(
    *,
    client: Any,
    buffer_manager: Optional[DualBufferManager],
    summary_engine: SummaryEngine,
    loop: asyncio.AbstractEventLoop,
):
    """Register a Vexa transcript callback that feeds the shared pipeline."""

    def on_transcript(event: TranscriptEvent) -> None:
        speaker = event.speaker or "unknown"
        text = event.text.strip()
        if not text:
            return

        msg_data = {
            "type": "transcript",
            "source": "vexa",
            "speaker": speaker,
            "meeting_id": event.meeting_id,
            "text": text,
            "start": event.start,
            "end": event.end,
            "is_final": event.is_final,
        }

        summary_engine.add_transcript(f"{speaker}: {text}")
        if buffer_manager:
            buffer_manager.on_transcript_chunk(text, [event.to_segment_dict()])

        asyncio.run_coroutine_threadsafe(manager.broadcast(msg_data), loop)

    client.on_transcript(on_transcript)
    return on_transcript


@app.get("/health")
async def health_check():
    """Health check endpoint for readiness probes."""
    return {
        "status": "ok",
        "whisper_host": WHISPER_HOST,
        "whisper_port": WHISPER_PORT,
        "llm_provider": LLM_PROVIDER,
        "active_connections": len(manager.active_connections),
        "knowledge_base_integrity": (
            {
                "valid": knowledge_base_integrity_status.get("valid"),
                "files_checked": knowledge_base_integrity_status.get("files_checked"),
            }
            if knowledge_base_integrity_status
            else {"valid": None, "files_checked": 0}
        ),
    }


@app.get("/api/vexa/status")
async def vexa_status():
    """Return the active Vexa meeting bridge status."""
    if not active_vexa_session:
        return {"active": False}
    return {
        "active": True,
        "meeting_id": active_vexa_session.meeting_id,
        "meeting_url": active_vexa_session.meeting_url,
        "started_at": active_vexa_session.started_at,
    }


@app.post("/api/vexa/join")
async def join_vexa_meeting(request: Request):
    """Dispatch a Vexa bot and bridge its transcripts into coaching."""
    global active_vexa_session

    if not VEXA_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": "Vexa integration is not available"},
        )

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"status": "error", "error": "Invalid JSON payload"})

    meeting_url = str(payload.get("meeting_url", "")).strip()
    bot_name = str(payload.get("bot_name", "Sales RPG AI")).strip() or "Sales RPG AI"

    if not meeting_url:
        return JSONResponse(status_code=400, content={"status": "error", "error": "meeting_url is required"})
    if not _is_supported_meeting_url(meeting_url):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "meeting_url must be a Zoom, Google Meet, or Microsoft Teams URL"},
        )

    await _stop_active_vexa_session()
    loop = asyncio.get_running_loop()

    try:
        llm_cfg = get_llm_config()
        analyzer = StreamingAnalyzer(
            api_key=llm_cfg.api_key,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model,
            fallback_model=getattr(llm_cfg, "fallback_model", None),
        )
    except ValueError as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": f"LLM configuration error: {e}"})

    def on_summary_result(result: SummaryResult):
        data = {
            "type": "summary",
            "source": "vexa",
            "summary": result.summary,
            "key_points": result.key_points,
            "pain_indicators": result.pain_indicators,
            "stage_hint": result.stage_hint,
            "archetype_hint": result.archetype_hint,
            "latency": result.latency_ms,
            "error": result.error,
        }
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    def on_analysis_result(result: AnalysisResult):
        data = {
            "type": "analysis",
            "source": "vexa",
            "script_location": result.state.script_location,
            "key_points": result.state.key_points,
            "suggestion": result.state.suggestion,
            "latency": result.latency_ms,
            "error": result.error,
        }
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    def on_analysis_partial(chunk: AnalysisStreamChunk):
        data = {
            "type": "analysis_delta",
            "source": "vexa",
            "delta": chunk.delta,
            "accumulated": chunk.accumulated,
            "latency": chunk.latency_ms,
            "sequence": chunk.sequence,
            "model": chunk.model,
        }
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    summary_engine = SummaryEngine(
        client=analyzer.client,
        model=llm_cfg.model,
        on_summary=on_summary_result,
        interval=300,
    )
    orchestrator = AnalysisOrchestrator(analyzer=analyzer, on_result=on_analysis_result, on_partial=on_analysis_partial)
    buffer_manager = DualBufferManager(on_analysis_ready=orchestrator.submit_analysis)

    client = VexaClient(VexaConfig())
    _create_vexa_transcript_bridge(
        client=client,
        buffer_manager=buffer_manager,
        summary_engine=summary_engine,
        loop=loop,
    )

    try:
        await client.connect()
        meeting_id = await client.create_meeting_bot(meeting_url, bot_name=bot_name)
        orchestrator.start()
        summary_engine.start()
        await client.start_streaming()
    except Exception as e:
        summary_engine.stop()
        orchestrator.shutdown()
        try:
            await client.disconnect()
        except Exception:
            logger.debug("Vexa disconnect after failed join also failed", exc_info=True)
        logger.error("Vexa join failed: %s", e, exc_info=True)
        return JSONResponse(status_code=502, content={"status": "error", "error": str(e)})

    active_vexa_session = VexaMeetingSession(
        client=client,
        meeting_id=meeting_id,
        meeting_url=meeting_url,
        summary_engine=summary_engine,
        orchestrator=orchestrator,
        started_at=time.time(),
    )
    await manager.broadcast({"type": "status", "source": "vexa", "message": "Vexa bot joining meeting"})
    return {"status": "joined", "meeting_id": meeting_id}


@app.post("/api/vexa/stop")
async def stop_vexa_meeting():
    """Stop the active Vexa meeting bridge."""
    await _stop_active_vexa_session()
    await manager.broadcast({"type": "status", "source": "vexa", "message": "Vexa meeting bridge stopped"})
    return {"status": "stopped"}


@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/transcript", response_class=HTMLResponse)
async def get_transcript(request: Request):
    """Serve the transcript page."""
    return templates.TemplateResponse("transcript.html", {"request": request})


@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket, role: str = "recorder"):
    """
    Handle WebSocket connection for audio streaming.
    """
    # Validate origin header before accepting the connection
    if not validate_origin(websocket):
        logger.warning("Rejected WebSocket connection from disallowed origin")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    if role == "monitor":
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()  # Keep connection alive
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        return

    # Recorder Logic (Main Dashboard)
    await websocket.accept()
    await manager.reset()

    loop = asyncio.get_running_loop()

    # Initialize LLM components
    try:
        llm_cfg = get_llm_config()
        analyzer = StreamingAnalyzer(
            api_key=llm_cfg.api_key,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model,
            fallback_model=getattr(llm_cfg, "fallback_model", None),
        )
    except ValueError as e:
        logger.error(f"LLM configuration error: {e}")
        await websocket.close(code=1011, reason=str(e))
        return

    # Initialize SummaryEngine for rolling conversation summaries
    def on_summary_result(result: SummaryResult):
        """Callback when summary is generated (runs in timer thread)."""
        data = {
            "type": "summary",
            "summary": result.summary,
            "key_points": result.key_points,
            "pain_indicators": result.pain_indicators,
            "stage_hint": result.stage_hint,
            "archetype_hint": result.archetype_hint,
            "latency": result.latency_ms,
            "error": result.error,
        }
        logger.info(
            f"Summary generated: stage={result.stage_hint}, "
            f"points={len(result.key_points)}, latency={result.latency_ms:.0f}ms"
        )

        async def _send():
            try:
                await websocket.send_json(data)
                await manager.broadcast(data)
            except Exception as e:
                logger.error(f"Failed to send summary: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), loop)
        except Exception as e:
            logger.error(f"Failed to schedule summary send: {e}")

    summary_engine = SummaryEngine(
        client=analyzer.client,
        model=llm_cfg.model,
        on_summary=on_summary_result,
        interval=300,  # 5 minutes
    )

    async def handle_command(cmd_data: dict):
        """Handle text commands from the frontend."""
        command = cmd_data.get("command")

        if command == "recommend":
            summary = summary_engine.current_summary
            if not summary or not summary.summary:
                await websocket.send_json(
                    {
                        "type": "recommendation",
                        "error": "No summary available yet. Click 'Refresh Summary' first.",
                    }
                )
                return

            try:
                result_json = await asyncio.to_thread(
                    analyzer.recommend,
                    summary.summary,
                    summary.key_points,
                    summary.stage_hint,
                    summary_engine.get_full_transcript(),
                )
                rec_data = json.loads(result_json)
                msg = {
                    "type": "recommendation",
                    "stage": rec_data.get("stage", summary.stage_hint),
                    "questions": rec_data.get("questions", []),
                    "reasoning": rec_data.get("reasoning", ""),
                }
                await websocket.send_json(msg)
                await manager.broadcast(msg)
            except json.JSONDecodeError as e:
                logger.error(f"Recommend JSON parse error: {e}")
                await websocket.send_json(
                    {
                        "type": "recommendation",
                        "error": f"Failed to parse recommendation: {e}",
                    }
                )
            except Exception as e:
                logger.error(f"Recommend error: {e}", exc_info=True)
                await websocket.send_json(
                    {
                        "type": "recommendation",
                        "error": str(e),
                    }
                )

        elif command == "refresh_summary":
            try:
                await asyncio.to_thread(summary_engine.refresh)
            except Exception as e:
                logger.error(f"Summary refresh error: {e}", exc_info=True)
                await websocket.send_json(
                    {
                        "type": "summary",
                        "error": str(e),
                    }
                )

    if TRANSCRIPTION_ENGINE == "vad":
        # ── VadTranscriber: Direct local VAD + Whisper ──────────────
        logger.info(
            f"Using VadTranscriber (model={VAD_WHISPER_MODEL}, device={VAD_DEVICE}, silence={VAD_SILENCE_MS}ms)"
        )
        try:
            vad = VadTranscriber(
                model=VAD_WHISPER_MODEL,
                device=VAD_DEVICE,
                silence_threshold_ms=VAD_SILENCE_MS,
                beam_size=1,
                condition_on_previous_text=False,
            )
        except Exception as e:
            logger.error(f"Failed to initialize VadTranscriber: {e}")
            await websocket.close(code=1011, reason=f"VadTranscriber init failed: {e}")
            return

        summary_engine.start()
        audio_chunks_received = 0
        total_bytes_received = 0
        try:
            while True:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    logger.info(
                        f"Client disconnected (code={message.get('code', 'unknown')}), processed {audio_chunks_received} chunks ({total_bytes_received} bytes)"
                    )
                    break

                if "bytes" in message:
                    chunk = message["bytes"]
                    audio_chunks_received += 1
                    total_bytes_received += len(chunk)

                    if audio_chunks_received % 50 == 1:
                        logger.info(
                            f"Audio received: {audio_chunks_received} chunks, {total_bytes_received} bytes total"
                        )

                    # Feed to VadTranscriber (may block briefly during transcription)
                    segments = await asyncio.to_thread(vad.feed, chunk)

                    for seg in segments:
                        logger.info(f"Transcript: '{seg['text'][:60]}' [{seg['start']:.1f}-{seg['end']:.1f}s]")
                        msg_data = {
                            "type": "transcript",
                            "text": seg["text"],
                            "start": seg["start"],
                            "end": seg["end"],
                            "is_final": True,
                        }
                        await websocket.send_json(msg_data)
                        await manager.broadcast(msg_data)

                        # Feed to summary engine
                        summary_engine.add_transcript(seg["text"])

                elif "text" in message:
                    # Handle text commands from frontend
                    try:
                        cmd_data = json.loads(message["text"])
                        await handle_command(cmd_data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON command received")

        except WebSocketDisconnect:
            logger.info(f"Client disconnected, processed {audio_chunks_received} chunks ({total_bytes_received} bytes)")
        except Exception as e:
            logger.error(f"VadTranscriber error: {e}", exc_info=True)
        finally:
            # Flush remaining audio
            try:
                final_segments = await asyncio.to_thread(vad.flush)
                for seg in final_segments:
                    logger.info(f"Final transcript: '{seg['text'][:60]}'")
                    msg_data = {
                        "type": "transcript",
                        "text": seg["text"],
                        "start": seg["start"],
                        "end": seg["end"],
                        "is_final": True,
                    }
                    try:
                        await websocket.send_json(msg_data)
                        await manager.broadcast(msg_data)
                        summary_engine.add_transcript(seg["text"])
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Flush error (non-fatal): {e}")
            summary_engine.stop()

    else:
        # ── WhisperLiveKit: WebSocket relay (legacy) ────────────────
        summary_engine.start()
        whisper_url = f"ws://{WHISPER_HOST}:{WHISPER_PORT}/asr"

        def parse_time_str(time_str: str) -> float:
            """Parse 'H:MM:SS' format to float seconds."""
            try:
                parts = time_str.split(":")
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                return 0.0
            except (ValueError, AttributeError):
                return 0.0

        max_retries = 5
        whisper_ws = None
        for attempt in range(max_retries):
            try:
                whisper_ws = await websockets.connect(whisper_url, ping_interval=20, ping_timeout=10, close_timeout=5)
                logger.info(f"Connected to WhisperLiveKit at {whisper_url} (attempt {attempt + 1})")
                break
            except (ConnectionRefusedError, OSError) as e:
                if attempt < max_retries - 1:
                    delay = min(2**attempt, 16)
                    logger.warning(
                        f"WhisperLiveKit not ready (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to connect to WhisperLiveKit after {max_retries} attempts: {e}")
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "error": f"Transcription service unavailable after {max_retries} attempts. Is WhisperLive running?",
                            }
                        )
                        await websocket.close(code=1011, reason="WhisperLive unavailable")
                    except RuntimeError:
                        pass
                    summary_engine.stop()
                    return

        try:
            async with whisper_ws:
                whisper_alive = True
                prev_line_texts: list[str] = []
                last_buffer_text = ""

                async def receive_transcripts():
                    nonlocal whisper_alive, prev_line_texts, last_buffer_text
                    try:
                        while True:
                            msg = await whisper_ws.recv()
                            data = json.loads(msg)

                            if data.get("type") == "config":
                                logger.info(f"WhisperLiveKit config: {data}")
                                continue
                            if data.get("type") == "ready_to_stop":
                                logger.info("WhisperLiveKit finished processing")
                                break
                            if data.get("status") == "error":
                                logger.error(f"WhisperLiveKit error: {data.get('error', 'unknown')}")
                                continue

                            lines = data.get("lines", [])
                            buffer_text = data.get("buffer_transcription", "").strip()
                            segments = []
                            current_texts = []

                            for i, line in enumerate(lines):
                                text = (line.get("text") or "").strip()
                                current_texts.append(text)
                                if not text:
                                    continue

                                start = parse_time_str(line.get("start", "0:00:00"))
                                end = parse_time_str(line.get("end", "0:00:00"))
                                prev_text = prev_line_texts[i] if i < len(prev_line_texts) else ""
                                is_new_line = i >= len(prev_line_texts)
                                is_updated = not is_new_line and text != prev_text

                                if is_new_line or is_updated:
                                    is_final = i < len(lines) - 1
                                    logger.info(f"Sending transcript to browser: '{text[:50]}' is_final={is_final}")
                                    msg_data = {
                                        "type": "transcript",
                                        "text": text,
                                        "start": start,
                                        "end": end,
                                        "is_final": is_final,
                                    }
                                    await websocket.send_json(msg_data)
                                    await manager.broadcast(msg_data)
                                    segments.append({"text": text, "start": start, "end": end, "completed": is_final})

                            prev_line_texts = current_texts

                            if buffer_text and buffer_text != last_buffer_text:
                                last_buffer_text = buffer_text
                                msg_data = {
                                    "type": "transcript",
                                    "text": buffer_text,
                                    "start": 0,
                                    "end": 0,
                                    "is_final": False,
                                }
                                await websocket.send_json(msg_data)
                                await manager.broadcast(msg_data)
                                segments.append({"text": buffer_text, "start": 0, "end": 0, "completed": False})

                            if segments:
                                full_text = " ".join(s["text"] for s in segments if s["text"])
                                summary_engine.add_transcript(full_text)

                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WhisperLiveKit connection closed")
                        whisper_alive = False
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(f"Error receiving from WhisperLiveKit: {e}")
                        whisper_alive = False

                receive_task = asyncio.create_task(receive_transcripts())

                audio_chunks_sent = 0
                total_bytes_sent = 0
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            logger.info(
                                f"Client disconnected (code={message.get('code', 'unknown')}), relayed {audio_chunks_sent} chunks ({total_bytes_sent} bytes)"
                            )
                            break
                        if "bytes" in message:
                            chunk = message["bytes"]
                            if whisper_alive:
                                try:
                                    await whisper_ws.send(chunk)
                                    audio_chunks_sent += 1
                                    total_bytes_sent += len(chunk)
                                    if audio_chunks_sent % 50 == 1:
                                        logger.info(
                                            f"Audio relay: {audio_chunks_sent} chunks, {total_bytes_sent} bytes total, last chunk {len(chunk)} bytes"
                                        )
                                except websockets.exceptions.ConnectionClosed:
                                    logger.warning("WhisperLiveKit gone, stopping audio relay")
                                    whisper_alive = False
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected, relayed {audio_chunks_sent} chunks ({total_bytes_sent} bytes)")
                finally:
                    receive_task.cancel()

        except Exception as e:
            logger.error(f"Connection error: {e}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except RuntimeError:
                pass
        finally:
            summary_engine.stop()


@app.websocket("/ws/dual-audio")
async def dual_audio_endpoint(websocket: WebSocket):
    """
    Handle WebSocket connection for dual audio capture and transcription.

    This endpoint captures both microphone and system audio, transcribes them
    separately with WhisperLive, and returns merged transcript with speaker labels.
    Requires PyAudio (not available in Docker containers).
    """
    # Validate origin header before accepting the connection
    if not validate_origin(websocket):
        logger.warning("Rejected dual-audio WebSocket from disallowed origin")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    if not DUAL_CAPTURE_AVAILABLE:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "message": "Dual capture not available. PyAudio not installed. Use /ws/audio instead."}
        )
        await websocket.close(code=1011, reason="Dual capture not available")
        return

    await websocket.accept()
    await manager.reset()

    loop = asyncio.get_running_loop()

    # Create output directory for this session
    output_dir = Path("/tmp/sales-rpg-ai/dual_capture")
    session_id = f"session_{int(time.time())}"

    # Initialize dual capture manager
    dual_capture = DualCaptureManager(output_dir)

    # Initialize dual stream transcriber
    transcriber = DualStreamTranscriber(
        whisper_host=WHISPER_HOST,
        whisper_port=WHISPER_PORT,
    )

    # Callback for transcription segments
    def on_segment(segment):
        """Send segment to browser in real-time."""
        msg_data = {
            "type": "transcript",
            "speaker": segment.speaker,
            "text": segment.text,
            "start": segment.start,
            "end": segment.end,
            "is_final": segment.is_final,
        }
        asyncio.run_coroutine_threadsafe(websocket.send_json(msg_data), loop)
        asyncio.run_coroutine_threadsafe(manager.broadcast(msg_data), loop)
        if buffer_manager:
            buffer_manager.on_transcript_chunk(
                segment.text,
                [
                    {
                        "text": segment.text,
                        "start": segment.start,
                        "end": segment.end,
                        "completed": segment.is_final,
                    }
                ],
            )

    transcriber.on_segment = on_segment

    # Initialize components for analysis (optional)
    try:
        llm_cfg = get_llm_config()
        analyzer = StreamingAnalyzer(
            api_key=llm_cfg.api_key,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model,
            fallback_model=getattr(llm_cfg, "fallback_model", None),
        )
    except ValueError as e:
        logger.warning(f"LLM not configured: {e}")
        analyzer = None

    orchestrator = None
    buffer_manager = None

    if analyzer:

        def on_analysis_result(result: AnalysisResult):
            data = {
                "type": "analysis",
                "script_location": result.state.script_location,
                "key_points": result.state.key_points,
                "suggestion": result.state.suggestion,
                "latency": result.latency_ms,
                "error": result.error,
            }
            asyncio.run_coroutine_threadsafe(websocket.send_json(data), loop)
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

        def on_analysis_partial(chunk: AnalysisStreamChunk):
            data = {
                "type": "analysis_delta",
                "delta": chunk.delta,
                "accumulated": chunk.accumulated,
                "latency": chunk.latency_ms,
                "sequence": chunk.sequence,
                "model": chunk.model,
            }
            asyncio.run_coroutine_threadsafe(websocket.send_json(data), loop)
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

        def on_analysis_ready(active_text: str, context_text: str):
            orchestrator.submit_analysis(active_text, context_text)

        orchestrator = AnalysisOrchestrator(
            analyzer=analyzer, on_result=on_analysis_result, on_partial=on_analysis_partial
        )
        buffer_manager = DualBufferManager(on_analysis_ready=on_analysis_ready, on_state_analysis_ready=lambda x: None)
        orchestrator.start()

    try:
        # Start dual capture
        logger.info(f"Starting dual capture session: {session_id}")
        mic_path, system_path = await dual_capture.start(session_id)

        # Send status to client
        await websocket.send_json(
            {
                "type": "status",
                "message": "Dual capture started",
                "mic_path": str(mic_path),
                "system_path": str(system_path),
            }
        )

        # Start transcription in background
        transcribe_task = asyncio.create_task(transcriber.transcribe_streams(mic_path, system_path))

        # Main loop: Wait for control messages from browser
        try:
            while True:
                message = await websocket.receive()

                if "text" in message:
                    data = json.loads(message["text"])

                    if data.get("command") == "stop":
                        logger.info("Stop command received")
                        break

        except WebSocketDisconnect:
            logger.info("Client disconnected")

        # Stop capture
        logger.info("Stopping dual capture")
        await dual_capture.stop()

        # Wait for transcription to complete
        logger.info("Waiting for transcription to complete")
        transcript = await transcribe_task

        # Send final transcript
        await websocket.send_json(
            {
                "type": "final_transcript",
                "text": transcript.to_text(),
                "json": json.loads(transcript.to_json()),
                "srt": transcript.to_srt(),
            }
        )

        logger.info(f"Dual capture session complete: {len(transcript.segments)} segments")

    except Exception as e:
        logger.error(f"Dual capture error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        if dual_capture.is_capturing:
            await dual_capture.stop()
        dual_capture.cleanup()

        if orchestrator:
            orchestrator.shutdown()

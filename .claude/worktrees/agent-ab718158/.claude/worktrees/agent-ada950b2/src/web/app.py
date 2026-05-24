"""
FastAPI Web Application for Sales AI.

Serves the web UI and handles WebSocket connections for real-time audio streaming.
"""

import os
import sys
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import websockets

# Add project root to path to import src modules
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Load env vars
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.realtime.buffer_manager import DualBufferManager, BufferConfig
from src.realtime.analysis_orchestrator import AnalysisOrchestrator, AnalysisResult, StreamingAnalyzer
from src.realtime.models import ConversationState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sales AI Web UI")

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

WHISPER_HOST = os.getenv("WHISPER_HOST", "localhost")
WHISPER_PORT = int(os.getenv("WHISPER_PORT", "9090"))

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")
LOCAL_AI_BASE_URL = os.getenv("LOCAL_AI_BASE_URL", "http://localhost:8080/v1")
LOCAL_AI_MODEL = os.getenv("LOCAL_AI_MODEL", "phi-3.5-mini")

# Global state for broadcasting
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.transcript_history: list[dict] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send history to new connection
        for segment in self.transcript_history:
            await websocket.send_json(segment)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def reset(self):
        self.transcript_history = []
        for connection in self.active_connections:
            try:
                await connection.send_json({"type": "reset"})
            except Exception:
                pass

    async def broadcast(self, message: dict):
        # Store if it's a transcript segment
        if message.get("type") == "transcript":
            self.transcript_history.append(message)
            
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

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
    if role == "monitor":
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text() # Keep connection alive
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        return

    # Recorder Logic (Main Dashboard)
    await websocket.accept()
    await manager.reset()
    
    loop = asyncio.get_running_loop()
    
    # Callback to send analysis results back to browser
    def on_analysis_result(result: AnalysisResult):
        # Send analysis result (which includes state)
        data = {
            "type": "analysis",
            "script_location": result.state.script_location,
            "key_points": result.state.key_points,
            "suggestion": result.state.suggestion,
            "latency": result.latency_ms,
            "error": result.error
        }
        # Send to recorder
        asyncio.run_coroutine_threadsafe(websocket.send_json(data), loop)
        # Broadcast to monitors
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    # Callback for buffer manager to trigger analysis
    def on_analysis_ready(active_text: str, context_text: str):
        orchestrator.submit_analysis(active_text, context_text)

    # Initialize components
    logger.info(f"Using LocalAI at {LOCAL_AI_BASE_URL} with model {LOCAL_AI_MODEL}")
    analyzer = StreamingAnalyzer(
        api_key="local", 
        base_url=LOCAL_AI_BASE_URL,
        model=LOCAL_AI_MODEL
    )
        
    orchestrator = AnalysisOrchestrator(
        analyzer=analyzer, 
        on_result=on_analysis_result
    )
    
    # Simplified buffer manager - no state analysis callback needed
    buffer_manager = DualBufferManager(
        on_analysis_ready=on_analysis_ready,
        on_state_analysis_ready=lambda x, y: None # No-op for state analysis
    )
    
    orchestrator.start()
    
    # Connect to WhisperLive
    whisper_url = f"ws://{WHISPER_HOST}:{WHISPER_PORT}"
    
    try:
        async with websockets.connect(whisper_url) as whisper_ws:
            logger.info(f"Connected to WhisperLive at {whisper_url}")
            
            # Send config to WhisperLive
            config = {
                "uid": "web-client",
                "language": "en",
                "task": "transcribe",
                "model": "base",
                "use_vad": False
            }
            await whisper_ws.send(json.dumps(config))
            
            # Task to receive transcripts from WhisperLive
            async def receive_transcripts():
                try:
                    while True:
                        msg = await whisper_ws.recv()
                        data = json.loads(msg)
                        
                        if "segments" in data:
                            for segment in data["segments"]:
                                text = segment.get("text", "")
                                if text:
                                    # Send transcript to browser
                                    msg_data = {
                                        "type": "transcript", 
                                        "text": text,
                                        "start": segment.get("start", 0),
                                        "end": segment.get("end", 0),
                                        "is_final": segment.get("is_last", False)
                                    }
                                    await websocket.send_json(msg_data)
                                    await manager.broadcast(msg_data)
                                    
                                    # Feed to buffer manager
                                    buffer_manager.on_transcript_chunk(text, [segment])
                                    
                except Exception as e:
                    logger.error(f"Error receiving from WhisperLive: {e}")

            receive_task = asyncio.create_task(receive_transcripts())
            
            # Main loop: Receive audio from Browser -> Send to WhisperLive
            try:
                while True:
                    message = await websocket.receive()
                    
                    if "bytes" in message:
                        audio_data = message["bytes"]
                        await whisper_ws.send(audio_data)
                    elif "text" in message:
                        pass
                        
            except WebSocketDisconnect:
                logger.info("Client disconnected")
            finally:
                receive_task.cancel()
                
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await websocket.close(code=1011, reason=str(e))
    finally:
        orchestrator.shutdown()

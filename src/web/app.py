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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not set! Analysis will fail.")


@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handle WebSocket connection for audio streaming.
    
    Acts as a proxy:
    Browser (Audio) -> FastAPI -> WhisperLive (Audio)
    WhisperLive (Text) -> FastAPI -> Buffer -> Analysis
    FastAPI (Text/Analysis) -> Browser
    """
    await websocket.accept()
    
    loop = asyncio.get_running_loop()
    
    # Callback to send analysis results back to browser
    def on_analysis_result(result: AnalysisResult):
        if result.has_objection or result.error:
            data = {
                "type": "objection" if result.has_objection else "error",
                "text": result.active_text,
                "response": result.raw_response,
                "latency": result.latency_ms
            }
            # Schedule sending on the main event loop
            asyncio.run_coroutine_threadsafe(websocket.send_json(data), loop)

    # Callback for buffer manager to trigger analysis
    def on_analysis_ready(active_text: str, context_text: str):
        orchestrator.submit_analysis(active_text, context_text)

    # Initialize components
    # Use a dummy key if not set to prevent crash on init, but it will fail on analyze
    api_key = OPENROUTER_API_KEY or "dummy"
    analyzer = StreamingAnalyzer(api_key=api_key)
    orchestrator = AnalysisOrchestrator(analyzer=analyzer, on_result=on_analysis_result)
    buffer_manager = DualBufferManager(on_analysis_ready=on_analysis_ready)
    
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
                "use_vad": True
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
                                    await websocket.send_json({
                                        "type": "transcript", 
                                        "text": text,
                                        "is_final": segment.get("is_last", False) # WhisperLive might send this
                                    })
                                    
                                    # Feed to buffer manager
                                    # We treat all incoming segments as potential updates
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
                        # Handle control messages if needed
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

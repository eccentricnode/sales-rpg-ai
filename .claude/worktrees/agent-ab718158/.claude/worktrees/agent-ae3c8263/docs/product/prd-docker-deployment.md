# PRD: Dockerized Deployment with Makefile

## Status
✅ **Implemented** (Phase 2)

## Problem

Currently, setting up Sales AI requires:

1. Installing Python dependencies (~3GB)
2. Starting WhisperLive server manually (Docker command)
3. Configuring environment variables
4. Running the application

This multi-step process creates friction for:

- **New users** trying to evaluate the product
- **Developers** setting up their environment
- **Deployment** to servers or cloud platforms

We need a **one-command setup** that handles everything.

---

## Solution

Create a fully Dockerized application with a Makefile interface:

```bash
# Clone and run
git clone <repo>
cd sales-rpg-ai
cp .env.example .env  # Add API key
make up               # Start everything
make demo             # Run demo with test audio
```

**Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│                    docker-compose                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐      ┌─────────────────────────┐  │
│  │  whisper-live   │      │     sales-ai-app        │  │
│  │  (transcription)│◄────►│  (objection detection)  │  │
│  │  Port: 9090     │ WS   │  Connects to whisper    │  │
│  └─────────────────┘      └─────────────────────────┘  │
│                                                         │
│  Network: sales-ai-network                              │
│  Volumes: model-cache (for Whisper models)              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Acceptance Criteria

- [ ] `make up` starts both WhisperLive server and app container
- [ ] `make down` stops all services cleanly
- [ ] `make demo` runs test with sample audio file
- [ ] `make test` runs the flow test (no WhisperLive needed)
- [ ] `make logs` shows logs from all services
- [ ] `.env.example` documents required environment variables
- [ ] Works on Linux (Arch/Ubuntu) with Docker installed
- [ ] GPU support available via `make up-gpu`
- [ ] First-time setup completes in < 5 minutes (excluding downloads)

---

## Technical Design

### File Structure

```
sales-rpg-ai/
├── Dockerfile                    # Sales AI application
├── docker-compose.yml            # Multi-service orchestration
├── docker-compose.gpu.yml        # GPU override
├── Makefile                      # Developer interface
├── .env.example                  # Environment template
├── .env                          # User's environment (gitignored)
└── ...
```

### Dockerfile (Sales AI App)

```dockerfile
FROM python:3.10-slim-bookworm

# System dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv sync

# Application code
COPY src/ ./src/

# Default command
CMD ["uv", "run", "python", "src/realtime_transcribe.py", "--help"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  whisper:
    image: ghcr.io/collabora/whisperlive-gpu:latest
    # Or for CPU: build from WhisperLive/docker/Dockerfile.cpu
    ports:
      - "9090:9090"
    volumes:
      - whisper-models:/root/.cache/huggingface
    networks:
      - sales-ai-network
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; s=socket.socket(); s.connect(('localhost', 9090)); s.close()"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - WHISPER_HOST=whisper
      - WHISPER_PORT=9090
    volumes:
      - ./samples:/app/samples:ro  # Mount sample audio files
      - ./output:/app/output       # Output directory
    networks:
      - sales-ai-network
    depends_on:
      whisper:
        condition: service_healthy
    stdin_open: true
    tty: true

volumes:
  whisper-models:

networks:
  sales-ai-network:
    driver: bridge
```

### Makefile

```makefile
.PHONY: help up down logs demo test clean build

# Default target
help:
	@echo "Sales AI - Real-Time Objection Detection"
	@echo ""
	@echo "Usage:"
	@echo "  make up        Start all services (CPU)"
	@echo "  make up-gpu    Start all services (GPU)"
	@echo "  make down      Stop all services"
	@echo "  make logs      View logs"
	@echo "  make demo      Run demo with sample audio"
	@echo "  make test      Run flow test (no WhisperLive)"
	@echo "  make shell     Open shell in app container"
	@echo "  make clean     Remove containers and volumes"
	@echo ""
	@echo "First time setup:"
	@echo "  1. cp .env.example .env"
	@echo "  2. Edit .env and add your OPENROUTER_API_KEY"
	@echo "  3. make up"
	@echo "  4. make demo"

# Check for .env file
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run: cp .env.example .env"; \
		echo "Then add your OPENROUTER_API_KEY"; \
		exit 1; \
	fi

# Build containers
build:
	docker-compose build

# Start services (CPU)
up: check-env
	docker-compose up -d
	@echo ""
	@echo "Services starting..."
	@echo "WhisperLive: http://localhost:9090"
	@echo ""
	@echo "Run 'make logs' to view logs"
	@echo "Run 'make demo' to test with sample audio"

# Start services (GPU)
up-gpu: check-env
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# Stop services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Run demo with sample audio
demo: check-env
	docker-compose exec app uv run python src/realtime_transcribe.py samples/test.mp4 --verbose

# Run flow test (no WhisperLive needed)
test: check-env
	docker-compose exec app uv run python src/test_realtime_flow.py

# Open shell in app container
shell:
	docker-compose exec app /bin/bash

# Run with microphone (requires audio passthrough)
mic: check-env
	docker-compose exec app uv run python src/realtime_transcribe.py --mic --verbose

# Clean up everything
clean:
	docker-compose down -v --rmi local
	@echo "Cleaned up containers, volumes, and local images"
```

### .env.example

```bash
# Sales AI Configuration
# Copy this file to .env and fill in your values

# Required: OpenRouter API Key
# Get one free at: https://openrouter.ai
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional: WhisperLive configuration
# WHISPER_HOST=whisper
# WHISPER_PORT=9090
# WHISPER_MODEL=base

# Optional: Buffer configuration
# BUFFER_TIME_THRESHOLD=3.0
# BUFFER_MIN_SEGMENTS=2
# BUFFER_MIN_CHARS=150
```

---

## Implementation Tasks

### Task 1: Create Dockerfile for Sales AI App

Create `Dockerfile` in project root:

- Base: `python:3.10-slim-bookworm`
- Install: portaudio, ffmpeg
- Copy: pyproject.toml, src/
- Use UV for dependency management

### Task 2: Create docker-compose.yml

Create `docker-compose.yml`:

- Service: `whisper` (WhisperLive server)
- Service: `app` (Sales AI application)
- Network: internal bridge network
- Volume: Whisper model cache
- Health check for WhisperLive

### Task 3: Create docker-compose.gpu.yml

Create GPU override file:

- Use NVIDIA runtime
- Mount GPU devices
- Use GPU-enabled WhisperLive image

### Task 4: Create Makefile

Create `Makefile` with targets:

- `up`, `up-gpu`, `down`
- `logs`, `demo`, `test`
- `shell`, `clean`
- `help` (default)

### Task 5: Create .env.example

Create `.env.example` with:

- Required variables documented
- Optional variables with defaults
- Comments explaining each variable

### Task 6: Update Application for Docker

Modify `src/realtime_transcribe.py`:

- Read `WHISPER_HOST` and `WHISPER_PORT` from environment
- Default to `localhost:9090` for local development
- Support container networking (`whisper:9090`)

### Task 7: Add Sample Audio File

Add `samples/` directory with:

- Test audio file containing objections
- README explaining the samples

### Task 8: Update Documentation

Update `README.md`:

- Add Docker quickstart section
- Document all Makefile targets
- Add troubleshooting for Docker issues

### Task 9: Test End-to-End

Verify:

- `make up` starts both services
- `make demo` runs successfully
- `make down` cleans up
- Works on fresh clone

---

## GPU Support

For users with NVIDIA GPUs, provide `docker-compose.gpu.yml`:

```yaml
version: '3.8'

services:
  whisper:
    image: ghcr.io/collabora/whisperlive-gpu:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Usage: `make up-gpu`

---

## Microphone Support in Docker

Microphone input requires passing audio devices to the container:

```yaml
# docker-compose.mic.yml (optional)
services:
  app:
    devices:
      - /dev/snd:/dev/snd
    group_add:
      - audio
```

**Note:** Microphone in Docker is complex. For demos, recommend:

1. File-based demo first (`make demo`)
2. Native microphone (`python src/realtime_transcribe.py --mic`)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time from clone to demo | < 5 minutes |
| Commands to get started | 3 (`cp`, `edit`, `make`) |
| Documentation clarity | New user success rate > 90% |

---

## Out of Scope

- Kubernetes deployment
- Cloud-specific configs (AWS, GCP, Azure)
- CI/CD pipeline setup
- Production hardening (secrets management, etc.)
- Windows Docker Desktop support

---

## Dependencies

### Required

- Docker Engine 20.10+
- Docker Compose V2
- ~5GB disk space (images + models)

### Optional

- NVIDIA Docker runtime (for GPU)
- `make` (standard on Linux)

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large image downloads | High | Medium | Document expected download size |
| Port 9090 conflict | Medium | Low | Document port configuration |
| GPU driver issues | Medium | Medium | Provide CPU fallback |
| Model download slow | Medium | Medium | Cache models in volume |

---

## Timeline Estimate

| Task | Effort |
|------|--------|
| Dockerfile | 30 min |
| docker-compose.yml | 30 min |
| docker-compose.gpu.yml | 15 min |
| Makefile | 30 min |
| .env.example | 10 min |
| App modifications | 20 min |
| Sample audio | 10 min |
| Documentation | 30 min |
| Testing | 30 min |
| **Total** | **~3-4 hours** |

---

## Next Steps

1. Create Dockerfile
2. Create docker-compose.yml
3. Create Makefile
4. Test locally
5. Update documentation

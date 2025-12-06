# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
# ffmpeg is useful for audio processing if needed
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY .env .

# Install Python dependencies
# We manually install only the web dependencies to avoid pulling in 
# heavy ML libraries (torch, whisper-live) required by the CLI tools.
RUN pip install --upgrade pip && \
    pip install fastapi uvicorn[standard] websockets python-dotenv jinja2 openai python-multipart httpx

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["python", "src/web/run.py"]

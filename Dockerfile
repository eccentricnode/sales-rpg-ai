# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
# ffmpeg is useful for audio processing if needed
# git is required for installing dependencies from git repositories
# portaudio19-dev and build-essential are required for PyAudio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    portaudio19-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY .env .

# Install Python dependencies
# We install directly from pyproject.toml using pip
RUN pip install --upgrade pip && \
    pip install . && \
    pip install python-dotenv websockets uvicorn

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["python", "src/web/run.py"]

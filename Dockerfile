# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y     ffmpeg     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY knowledge_base/ knowledge_base/
COPY .env .

# Install dependencies
RUN pip install --upgrade pip &&     pip install fastapi uvicorn[standard] websockets python-dotenv jinja2 openai python-multipart

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "src/web/run.py"]

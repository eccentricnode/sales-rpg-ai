# Makefile for Sales AI

.PHONY: help up down logs build clean

help: ## Show this help message
	@echo 'Usage:'
	@echo '  make up      Start all services (WhisperLive + Web UI)'
	@echo '  make down    Stop all services'
	@echo '  make logs    Show logs from all services'
	@echo '  make build   Rebuild the web application container'
	@echo '  make clean   Remove containers and artifacts'

up: ## Start all services (auto-detects GPU)
	@if command -v nvidia-smi > /dev/null 2>&1; then \
		echo "NVIDIA GPU detected. Starting with GPU support..."; \
		docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d; \
	else \
		echo "No NVIDIA GPU detected. Starting in CPU mode..."; \
		docker compose up -d; \
	fi
	@echo "Sales AI is running at http://localhost:8080"

down: ## Stop all services
	docker compose down

logs: ## Follow logs
	docker compose logs -f

build: ## Rebuild containers
	docker compose build

clean: ## Remove containers and volumes
	docker compose down -v

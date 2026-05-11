.PHONY: help install dev test lint format run clean docker-build docker-run smoke supertrend supertrend-current

help:
	@echo "Available commands:"
	@echo "  make install       Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo "  make smoke        Run quick smoke test (imports + basic validation)"
	@echo "  make test         Run test suite"
	@echo "  make test-cov     Run tests with coverage report"
	@echo "  make lint         Run linter (ruff)"
	@echo "  make format       Format code (black)"
	@echo "  make typecheck    Run mypy type checking"
	@echo "  make run          Start development server"
	@echo "  make clean        Remove build artifacts and cache"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run Docker container"
	@echo "  make supertrend   Generate daily timestamped Supertrend report + archive"
	@echo "  make supertrend-current  Update current daily_supertrend.txt with live data"

install:
	pip install -r requirements.txt

dev:
	pip install -e ".[dev]"

smoke:
	python3 smoke_test.py

test:
	pytest -v

test-cov:
	pytest --cov=app --cov-report=html -v

lint:
	ruff check app/ tests/

format:
	black app/ tests/

typecheck:
	mypy app/

run:
	python -m uvicorn app.api.webhook:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name build -exec rm -rf {} +
	find . -type d -name dist -exec rm -rf {} +
	find . -type d -name *.egg-info -exec rm -rf {} +
	rm -rf .coverage htmlcov/
	rm -rf logs/*.log

docker-build:
	docker build -t trade-vibte-webhook:latest .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env trade-vibte-webhook:latest

supertrend:
	.venv/bin/python scripts/generate_daily_supertrend.py

supertrend-current:
	.venv/bin/python scripts/update_supertrend_current.py

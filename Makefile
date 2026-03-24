IMAGE_NAME ?= searxng-mcp
IMAGE_TAG ?= latest
FULL_IMAGE = $(IMAGE_NAME):$(IMAGE_TAG)
UV ?= uv
TRANSPORT ?= stdio

.PHONY: build run run-detached dev lint install-dev clean test test-all

build:
	docker build -t $(FULL_IMAGE) .

run: build
	docker run --rm -i $(FULL_IMAGE)

run-detached:
	docker run --rm -i -d --name searxng-mcp-dev $(FULL_IMAGE)

# Local run without Docker — requires SearXNG running at SEARXNG_URL (default http://127.0.0.1:8080)
dev:
	TRANSPORT=$(TRANSPORT) uv run python src/server.py

# Requires: pip install ruff mypy
lint:
	uv run ruff check src/
	uv run ruff format --check src/
	uv run mypy src/ --ignore-missing-imports

# Install project in editable mode + dev tools
install-dev:
	uv sync --group dev

test:
	uv run pytest tests/test_server.py -v

test-all: build
	uv run pytest tests/test_e2e.py -v -s --timeout=180

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	docker rmi $(FULL_IMAGE) 2>/dev/null || true

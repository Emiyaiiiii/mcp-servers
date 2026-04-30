.PHONY: all start test lint format clean

install:
	uv sync

start:
	uv run mcp-server

test:
	python -m pytest tests/

lint:
	flake8 src/

format:
	black src/

clean:
	rm -rf __pycache__/ .venv/ logs/
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev

COPY . .

RUN mkdir -p storage logs

RUN uv run python -m src.services.storage.database.init_database

ENV PYTHONUNBUFFERED=1

EXPOSE 8082

CMD ["uv", "run", "python", "-c", "from src.server import run_server; run_server(transport='streamable-http')"]

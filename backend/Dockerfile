FROM python:3.12.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12.13-slim
RUN useradd --system --uid 10001 --home /nonexistent fido
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app app
COPY alembic alembic
COPY alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]

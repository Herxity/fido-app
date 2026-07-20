# Fido backend

Python 3.12 FastAPI service. Install with `uv sync --all-groups`, run migrations with
`uv run alembic upgrade head`, and start with `uv run uvicorn app.main:app --reload`.

Production requires PostgreSQL and `FIDO_PROVIDER_MODE=live`. Provider fakes are enabled only
when both `FIDO_ENVIRONMENT` and `FIDO_PROVIDER_MODE` explicitly select development/test.
Never place real credentials in `.env`; use the protected deployment environment file.

## Checks

```sh
uv run ruff check .
uv run mypy app
uv run pytest
uv run pip-audit
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

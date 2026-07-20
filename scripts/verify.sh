#!/usr/bin/env bash
set -Eeuo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "${repo}"

(
  echo "Fido verification"
  date -u '+UTC %Y-%m-%dT%H:%M:%SZ'
  git rev-parse HEAD
  echo "BACKEND"
  cd backend
  uv sync --frozen
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy app
  uv run pytest -q
  uv run pip-audit
  cd ../frontend
  echo "FRONTEND"
  npm ci
  npm run lint
  npm run typecheck
  npm test -- --run
  npm run build
  npm audit --omit=dev
  cd ../infra
  echo "INFRASTRUCTURE"
  npm ci
  npm run build
  npm run lint
  npm run format:check
  npm test -- --run
  npm run synth
  npm audit --omit=dev
) 2>&1 | tee evidence/latest-verification.txt

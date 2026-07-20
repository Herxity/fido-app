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
  uv run python scripts/export_openapi.py
  git diff --exit-code -- openapi.json
  cd ../frontend
  echo "FRONTEND"
  npm ci
  npm run lint
  npm run typecheck
  npm test -- --run
  npm run api:generate
  git diff --exit-code -- src/api/openapi.d.ts
  npm run build
  npm audit --omit=dev
  VITE_USE_DEMO_DATA=true npm run test:e2e
  cd ../infra
  echo "INFRASTRUCTURE"
  npm ci
  npm run build
  npm run lint
  npm run format:check
  npm test -- --run
  npm run synth
  npm audit --omit=dev
  cd ..
  echo "DELIVERY"
  BACKEND_IMAGE="example.invalid/fido@sha256:$(printf 'a%.0s' {1..64})" \
    CADDY_IMAGE="caddy@sha256:$(printf 'b%.0s' {1..64})" \
    FIDO_RELEASE_DIR=/opt/fido/releases/verification \
    ORIGIN_HOSTNAME=127-0-0-1.sslip.io \
    ACME_EMAIL=operations@fido.invalid \
    FIDO_ORIGIN_VERIFY_TOKEN=01234567890123456789012345678901 \
    docker compose -f docker-compose.prod.yml config --quiet
) 2>&1 | tee evidence/latest-verification.txt

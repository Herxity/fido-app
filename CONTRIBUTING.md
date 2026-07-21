# Contributing

## Local development

Requirements: Python 3.12, `uv`, Node.js 22, npm, Docker with Compose v2, and PostgreSQL 18 for integration checks.

1. Start the isolated local PostgreSQL database with `docker compose -f docker-compose.dev.yml up -d`.
2. Copy `backend/.env.example` to `backend/.env`, point `FIDO_DATABASE_URL` at the local database, configure the Clerk development instance, and set `FIDO_DEVELOPMENT_CLERK_ORG_ID` to its synthetic shelter organization. Keep the file untracked.
3. Run `uv sync --frozen`, `uv run alembic upgrade head`, and `uv run python scripts/seed_development.py` in `backend/`, followed by `uv run pytest` and `uv run uvicorn app.main:app --reload`.
4. Copy `frontend/.env.example` to `frontend/.env.local`, configure the matching Clerk publishable key, and keep `VITE_USE_DEMO_DATA=false`. Browser-side demo data does not exercise reconciliation or persistence.
5. Run `npm ci`, `npm test`, and `npm run dev` in `frontend/`.
   Open `http://localhost:5173` (not the numeric loopback address) so Clerk's development browser and authorized-party checks use the canonical local origin.
6. Run `npm ci`, `npm test`, and `npm run synth` in `infra/`.

## Required checks

Before opening a change, run the same lint, type, unit, audit, build, OpenAPI drift, CDK synth/nag, container, and end-to-end checks defined in `.github/workflows/ci.yml`.

## Security and privacy rules

- Never commit `.env` files, credentials, webhook secrets, private keys, ID images, biometrics, raw Persona reports, or production data.
- Never print secrets in build logs or issue descriptions. Rotate any value exposed accidentally.
- Use synthetic data in tests and screenshots.
- Preserve append-only custody history; corrections link to the original record.
- Authorization belongs in FastAPI and PostgreSQL constraints/triggers, never only in React.
- A new data field requires a documented purpose, retention period, access policy, and privacy review.
- Report suspected vulnerabilities privately to the repository owner rather than opening a public issue.

## Changes and review

Keep commits scoped, include tests for authorization and tenant boundaries, and update `evidence/CHECKLIST_EVIDENCE.md` when an acceptance condition changes. Stateful AWS changes require `cdk diff`, backup/restore consideration, and explicit approval before replacement or deletion.

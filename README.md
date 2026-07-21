# Fido

Fido is a privacy-conscious, cross-shelter record of factual pet custody events. Owners verify their identity, authorize time-limited access with a QR pass, inspect their own history, and dispute errors. Participating shelters manage pets and append adoptions, returns, surrenders, reclaims, foster events, transfers, and corrections. Fido does not score owners or make adoption decisions.

## Repository

- `backend/` — FastAPI, SQLAlchemy, Alembic, Clerk, and privacy-preserving identity reconciliation.
- `frontend/` — React 19, TypeScript, Vite, Clerk, and the shelter Identity Desk.
- `infra/` — AWS CDK stacks for Lightsail PostgreSQL, compute, CloudFront, WAF, backups, and alarms.
- `deploy/` — hardened host, database-role, Caddy, and digest-pinned release tooling.
- `docs/` — architecture decisions, threat model, operations, privacy/legal gates, and contribution rules.
- `evidence/` — generated checklist and verification evidence.

The approved architecture and acceptance criteria are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); the current identity design is in [docs/MANUAL_IDENTITY_RECONCILIATION_PLAN.md](docs/MANUAL_IDENTITY_RECONCILIATION_PLAN.md). Local setup is documented in [CONTRIBUTING.md](CONTRIBUTING.md), while production operations are in [deploy/README.md](deploy/README.md).

## Safety status

The software is suitable for sandbox/staging verification. Real owner or shelter data must not be loaded until Clerk is configured, shelter verification procedures are approved, counsel completes the reviews listed in `docs/LEGAL_AND_PRIVACY_GATES.md`, and the user separately approves production deployment and DNS cutover.

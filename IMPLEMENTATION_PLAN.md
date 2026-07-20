# Fido Cross-Shelter Adoption History System

## Summary

Fido will be a U.S.-only pilot that lets participating shelters maintain a factual, cross-shelter history of pet adoptions, returns, surrenders, reclaims, fosters, and transfers. Verified owners can view and dispute their own history and generate a short-lived QR code to authorize a shelter to retrieve it.

The MVP will not calculate suitability scores, blacklist owners, or automatically approve or deny adoptions. Persona will establish and recover a canonical human identity, Clerk will authenticate users and shelter staff, and Fido will retain the factual event history.

No repository, AWS, Persona, Clerk, DNS, server, or production changes may occur beyond committing this document until the user explicitly approves further implementation.

## 1. High-Level Architecture

```text
Owner or Shelter Staff
        |
        v
Route 53 DNS
        |
        v
CloudFront + Shield Standard + AWS WAF
        |
        v
Caddy on Lightsail
   |             |
React SPA     /api/* and webhooks
                 |
                 v
          FastAPI monolith
          |      |       |
        Clerk  Persona  Private Lightsail PostgreSQL
```

Deployment shape:

- One AWS Lightsail instance running Caddy and one FastAPI container.
- React is compiled in CI and served as static files by Caddy.
- Private AWS Lightsail Managed PostgreSQL stores application data.
- CloudFront is the public entry point and AWS WAF provides application-layer filtering and rate limiting.
- Clerk provides authentication, sessions, shelter organizations, and staff membership.
- Persona provides government-ID verification, selfie/liveness checks, repeat-ID detection, fuzzy identity signals, workflows, and manual-review cases.
- GitHub Actions tests and builds the application. Production deployment requires explicit human approval before an SSH-based Docker Compose release.

## 2. Product Behavior and Access Model

### Owner experience

An owner can:

- Register using Clerk email-code authentication.
- Complete Persona identity verification.
- View their factual adoption and surrender history.
- Generate a single-use QR code valid for five minutes.
- See which shelters accessed their history.
- Dispute an inaccurate event without removing the original record.
- Recover access to an existing canonical identity if a new Clerk account or different identity document is used.

An owner cannot:

- Edit or delete custody events.
- Generate a QR code until identity verification is approved.
- See internal notes, identity-review evidence, or other owners.
- Reset their history merely by creating another Clerk or Persona account.

### Shelter experience

Each shelter is a Clerk Organization. Supported roles are:

- `shelter_admin`: manages staff and shelter settings and performs all shelter operations.
- `shelter_staff`: manages pets and custody records and performs owner lookups.
- `shelter_read_only`: views permitted records but cannot create or correct them.
- `platform_admin`: separate Fido operational role for identity review, disputes, and platform administration.

Shelters can:

- Register and manage pets.
- Redeem an owner-presented QR code.
- View the owner's factual cross-shelter custody history during the resulting lookup session.
- Record adoptions, returns, surrenders, reclaims, fosters, and transfers.
- Append corrections to events created by their shelter.
- Open or respond to disputes involving their records.

Shelters cannot:

- Search people globally by name, email, date of birth, or government identifier.
- View raw Persona documents, selfies, or biometric information.
- Change another shelter's records.
- Silently update or delete historical events.
- Receive a Fido-generated suitability score or automatic adoption recommendation.

### Lookup authorization

- The owner generates a cryptographically random, opaque QR token.
- The token expires after five minutes and can be redeemed once.
- Redemption creates a shelter-bound lookup session valid for 30 minutes.
- The session is bound to the redeeming Clerk organization and user.
- Every creation, redemption, access, failure, and expiration is audited.
- The QR contains no name, history, Persona identifier, or other personal data.

## 3. Identity, Authentication, and Fraud Controls

### Clerk responsibilities

- Email-code owner authentication.
- Shelter organization membership.
- Session and JWT issuance.
- Staff-role claims.
- Invitations and membership lifecycle.
- Signed webhook notifications for relevant user and organization changes.

FastAPI will validate Clerk JWT signatures, issuer, audience, expiration, and organization claims. Authorization is enforced by the backend; frontend route guards are convenience controls only.

### Persona responsibilities

The selected Persona flow will use:

- Government-ID verification.
- Live selfie/liveness verification.
- Selfie-to-ID comparison.
- Government ID Repeat check across Persona Accounts.
- Workflows producing `approved`, `declined`, or `needs_review`.
- Cases for manual investigation.
- Account consolidation when separate Persona Accounts are confirmed to represent one person.

Before production commitment, the Persona trial must confirm that the selected plan exposes the required Repeat checks, Workflows, Cases, webhook fields, and consolidation API.

### Canonical-person model

Custody history belongs to a Fido `person`, not directly to a Clerk user or Persona Account.

- A person may have multiple historical Clerk accounts.
- A person may have multiple Persona inquiries or accounts after recovery.
- A Clerk account maps to at most one active canonical person.
- Persona inquiry reference IDs use a Fido-generated UUID.
- Fido pre-creates Persona Embedded Flow inquiries server-side.
- Browser completion is never treated as authoritative; signed Persona webhooks determine the result.
- Creating a new account with a passport after previously using a driver's license does not automatically create a clean history.

Automatic linking or merging requires strong Persona evidence and workflow approval. Similar name or date of birth alone never triggers a merge. Ambiguous, conflicting, partial-match, or repeat-check cases go to manual review.

### Edge-case handling

- Same ID or person found across accounts: prevent a fresh identity and route to account recovery or consolidation.
- Matching details but nonmatching portrait: manual review; never automatically merge.
- Matching portrait but materially different identity details: fraud/manual review.
- Legal name change: preserve aliases and verification provenance without changing historical events.
- Twins or similar-looking relatives: require corroborating Persona results and manual review.
- Shared email or changed email: authentication recovery does not determine identity.
- Persona outage: keep inquiry pending and retry; do not bypass verification.
- Declined verification: give the owner a review/appeal path without exposing fraud rules.

### Minimized identity storage

Fido stores:

- Persona Account and Inquiry IDs.
- Verification state and relevant reason category.
- Minimum verified display name needed by the shelter.
- Verification and review timestamps.
- Linkage/consolidation provenance.
- Reviewer decision and non-sensitive explanation.

Fido does not store:

- Government-ID images or numbers.
- Selfie images or biometric templates.
- Social Security numbers.
- Raw Persona reports.
- Payment credentials.
- Date of birth or home address unless a later documented requirement and privacy review justify them.

## 4. Database Plan

Use a private, non-HA Lightsail Managed PostgreSQL database for the lean pilot. The application and database must be in the same AWS region/account, and public database access remains disabled.

### Core tables

#### `people`

- Canonical person UUID.
- Status: active, review, merged, restricted, deleted.
- Minimum verified display name.
- Verification timestamps.
- Optional `merged_into_person_id`.
- Created/updated timestamps.

#### `user_accounts`

- Clerk user ID, unique.
- Canonical person ID.
- Persona Account ID where applicable.
- Account/link status.
- Link reason and timestamps.
- No password or Clerk session data.

#### `shelters`

- Clerk Organization ID, unique.
- Shelter name and operational status.
- Contact and configuration fields.
- Created/updated timestamps.

Local organization membership is not duplicated; Clerk remains its source of truth.

#### `pets`

- Shelter-scoped pet UUID and shelter record number.
- Name, species, breed description, sex, approximate birth date, color, and altered status.
- Microchip identifier encrypted at the application layer, with a separate keyed lookup hash if exact lookup becomes necessary.
- Current lifecycle state.
- Created/updated timestamps.

#### `custody_events`

- Append-only event UUID.
- Pet, person, and recording shelter IDs.
- Event type and effective timestamp.
- Source shelter record/reference.
- Neutral structured reason category where applicable.
- Limited factual note.
- Actor and creation timestamp.
- Optional reference to the event being corrected.
- Idempotency key unique within the shelter.

Supported event types:

- `adoption`
- `return_from_adoption`
- `owner_surrender`
- `reclaim_by_owner`
- `transfer_in`
- `transfer_out`
- `foster_start`
- `foster_end`
- `correction`

Reason categories will use the Shelter Animals Count taxonomy where applicable. Reasons remain factual data and are not converted into a risk score.

#### `identity_inquiries`

- Person/account reference.
- Persona inquiry and account IDs.
- State: pending, approved, declined, needs_review, superseded.
- Repeat-check outcome category.
- Workflow/case references.
- Received and resolved timestamps.
- No raw Persona payload.

#### `lookup_tokens`

- Hashed token, never plaintext.
- Person, expiration, consumed timestamp, and generation metadata.
- Redeeming shelter/user.
- Lookup-session expiration and revocation state.

#### `disputes`

- Person, disputed event, owner's reason, status, and timestamps.
- Responsible shelter and assigned reviewer.
- Resolution summary and resulting correction event, if any.

#### `webhook_events`

- Provider and provider event ID, unique.
- Minimal event type, processing state, timestamps, attempt count, and sanitized failure information.
- Used for idempotent webhook processing.

#### `audit_log`

- Append-only actor, organization, action, resource, outcome, timestamp, request ID, and security metadata.
- No raw tokens, document data, or unnecessary personal information.

### Database invariants

- Historical custody events cannot be updated or deleted through normal application roles.
- Corrections append a new event referencing the original.
- Cross-shelter queries require a valid lookup session.
- All shelter-owned writes carry and validate a shelter ID from the authenticated organization context.
- Merging people redirects future reads to the canonical destination without rewriting custody history.
- Foreign keys, unique constraints, and transactions enforce linkage consistency.
- Alembic owns all schema changes.
- A restricted migration role and separate least-privilege runtime role are used.

### Retention defaults

Pending legal/privacy review:

- Unused lookup-token rows: remove after 24 hours.
- Lookup-session metadata: retain 30 days.
- Sanitized webhook processing metadata: retain 90 days.
- Security/audit logs: retain one year.
- Custody history and contract references: retain seven years or the legally approved period.
- Persona media and sensitive verification evidence remain in Persona under its configured retention policy.

## 5. Backend Plan

### Technology

- Python 3.12.
- FastAPI and Pydantic Settings.
- SQLAlchemy 2 asynchronous sessions with psycopg 3.
- Alembic migrations.
- HTTPX for provider calls.
- `uv` for locked Python dependencies.
- Structured JSON logs with request correlation IDs.
- Pytest, Ruff, mypy, and dependency/security scanning.
- Non-root Docker image with a read-only application filesystem where practical.

### Modules

- `auth`: Clerk JWT and role enforcement.
- `identity`: Persona inquiries, webhook processing, reviews, linkage, and consolidation.
- `shelters`: organization context and staff permissions.
- `people`: canonical identity and owner history.
- `pets`: pet registry.
- `custody`: append-only custody events.
- `lookups`: QR tokens and lookup sessions.
- `disputes`: owner disputes and shelter resolutions.
- `audit`: security and business-event auditing.
- `webhooks`: Clerk and Persona event ingestion.
- `admin`: platform review operations.

### Public API

All endpoints use `/api/v1`; all identifiers are opaque UUIDs unless they are provider IDs in internal-only payloads.

Owner endpoints:

- `GET /me`
- `POST /identity/inquiries`
- `GET /identity/status`
- `GET /me/history`
- `POST /me/lookup-tokens`
- `GET /me/access-log`
- `POST /me/disputes`

Shelter endpoints:

- `POST /lookups/redeem`
- `GET /lookups/{session_id}/history`
- `GET /shelters/{shelter_id}/pets`
- `POST /shelters/{shelter_id}/pets`
- `GET /shelters/{shelter_id}/pets/{pet_id}`
- `PATCH /shelters/{shelter_id}/pets/{pet_id}`
- `POST /custody-events`
- `POST /custody-events/{event_id}/corrections`
- `GET /disputes`
- `PATCH /disputes/{dispute_id}`

Platform endpoints:

- `GET /admin/identity-reviews`
- `POST /admin/identity-reviews/{review_id}/resolve`
- `POST /admin/people/{source_person_id}/merge`

Provider and operational endpoints:

- `POST /webhooks/clerk`
- `POST /webhooks/persona`
- `GET /health/live`
- `GET /health/ready`

### Important API types

`IdentityStatus`

- `unverified | pending | approved | declined | needs_review`

`CustodyEventType`

- The nine event types defined in the database section.

`LookupTokenResponse`

- Opaque token represented as a QR payload.
- Expiration timestamp.
- No personal information.

`HistoryEntry`

- Pet summary.
- Event type and effective date.
- Source shelter.
- Factual reason category and note.
- Correction relationship.
- Dispute status.

`DisputeStatus`

- `open | shelter_review | platform_review | resolved | rejected`

`IdentityReviewDecision`

- `link_existing | approve_new | decline | request_more_information`

### API rules

- OpenAPI is generated from FastAPI and used to generate the TypeScript client.
- CI fails if the committed/generated client drifts from OpenAPI.
- Mutating custody calls require an idempotency key.
- Pagination uses opaque cursors.
- Dates are ISO 8601 UTC; custody events also retain the entered local effective date where needed.
- Validation errors use a consistent machine-readable problem format.
- The backend returns neutral facts and never an eligibility score.
- Sensitive values, provider secrets, authorization headers, and QR tokens are redacted from logs.

### Webhooks

- Verify signatures against the raw request body before parsing.
- Reject stale or invalid signatures.
- Persist provider event IDs for idempotency.
- Acknowledge valid duplicates safely.
- Process state transitions transactionally.
- Retry temporary provider/database failures.
- Alert on sustained processing failures or an expanding retry backlog.
- Persona's signed webhook, not browser callbacks, finalizes identity status.

## 6. Frontend Plan

### Technology

- React with TypeScript and Vite.
- React Router.
- TanStack Query.
- React Hook Form with Zod.
- Clerk React SDK.
- Persona Embedded Flow SDK.
- Tailwind CSS with Radix primitives.
- Vitest, Testing Library, and Playwright.
- Locally bundled typography; no unnecessary third-party tracking or font requests.

### Owner application

- Email-code sign-in.
- Persona verification and review-status flow.
- Personal history timeline.
- QR-generation screen with countdown and consumed/expired feedback.
- Shelter-access log.
- Dispute submission and status tracking.
- Account recovery guidance when Persona identifies an existing person.

### Shelter workspace

Use a friendly shelter-workspace visual language:

- Warm exam-room cream background.
- Kennel slate and leash navy for structure.
- ID-tag brass and chart green accents.
- Restrained rust for warnings, never for owner scoring.
- Accessible contrast, keyboard navigation, and clear focus states.

The signature interaction is a cross-shelter "care journey" timeline showing custody events, source-shelter stamps, correction links, and dispute status.

Primary areas:

- Active work queue rather than generic vanity metrics.
- Pet registry/detail split rather than a generic card grid.
- Owner QR redemption.
- Neutral factual history ledger.
- Custody-event recording.
- Dispute and correction workflow.
- Staff and organization settings for administrators.

### Frontend security

- No authentication or Persona secrets in the bundle.
- No raw ID media passes through the frontend to Fido.
- Strict Content Security Policy compatible with Clerk and Persona.
- Authorization failures clear cached protected data.
- Query cache is separated by authenticated user and organization.
- History is not persisted to local storage.
- QR contents are concealed after expiration or redemption.
- All destructive or legally meaningful actions require explicit confirmation.

## 7. AWS Infrastructure Plan

### CDK organization

Use pinned AWS CDK v2 with strict TypeScript, Node.js 20+, `tsx`, and `cdk-nag`.

#### `FidoStatefulStack`

- Private Lightsail Managed PostgreSQL.
- Backup retention and deletion protection where supported.
- Retention policies and termination protection.
- Database credential rotation/configuration without embedding plaintext in templates.
- Separated so application deployments cannot replace the database accidentally.

#### `FidoAppEdgeStack`

- Lightsail `micro_3_0` instance: 1 GB RAM, approximately $7/month.
- Static IP attachment.
- Lightsail firewall configuration.
- Route 53 DNS records.
- CloudFront distribution.
- WAF web ACL and managed/rate-based rules.
- Monitoring alarms and deployment outputs.

The existing 512 MB Nano instance will not be mutated during initial build. A new CDK-managed 1 GB instance is provisioned and health-tested; DNS is cut over only after acceptance checks. The old instance is retired only after explicit user approval.

### Edge and network controls

- CloudFront is the only documented public application endpoint.
- Shield Standard protection is automatic.
- WAF begins in count mode, is reviewed for false positives, then changes to block mode.
- Enable managed common, known-bad-input, and IP-reputation rules.
- Add rate-based rules for authentication-adjacent paths, QR redemption, Persona inquiry creation, and webhook abuse.
- Static hashed assets receive long cache lifetimes.
- HTML, `/api/*`, and webhook paths are not cached.
- Authorization and required webhook headers are forwarded only where necessary.
- CloudFront sends a random origin header; Caddy rejects requests without it.
- Caddy obtains and renews origin TLS certificates.
- Only ports 80/443 are public; SSH remains restricted to approved `/32` addresses and Lightsail browser-connect where required.

The Lightsail static IP remains a residual volumetric-attack surface. The origin-header check prevents application bypass but does not provide the network isolation available with an ALB/VPC architecture. If threat level or traffic grows, migration to ECS/Fargate or EC2 behind an ALB becomes the next architecture step.

### Host and container hardening

- Ubuntu security patches and automatic security updates.
- Root SSH login disabled.
- Password authentication disabled.
- Only the `ubuntu` administrative account allowed.
- SSH forwarding and tunneling disabled.
- Fail2ban or equivalent SSH abuse monitoring.
- Docker Compose with pinned image digests.
- FastAPI binds only to the internal container network.
- Caddy is the only service binding public HTTP ports.
- Containers run as non-root with dropped Linux capabilities.
- Resource limits and log rotation protect the 1 GB host.
- Host firewall denies unneeded ingress.
- Regular encrypted instance snapshots and restore testing.

### Secrets

For the lean Lightsail deployment:

- Application secrets live in `/etc/fido/fido.env`.
- File owner is root and mode is `0600`.
- Compose references the file without committing or printing it.
- Values never appear in CDK source, CloudFormation outputs, GitHub logs, or application logs.
- Separate secrets exist for development and production.
- Rotation procedures cover database, Clerk, Persona, origin-header, and deployment credentials.

A later move to an environment with instance roles should migrate runtime secrets to AWS Secrets Manager.

### CI/CD

GitHub Actions will:

- Run frontend and backend linting, type checks, and tests.
- Build the React application.
- Generate and drift-check the TypeScript API client.
- Run Alembic migration checks.
- Scan dependencies, secrets, containers, and IaC.
- Run `cdk synth --strict`, `cdk-nag`, and `cdk diff`.
- Build the application image on CI, not on the 1 GB server.
- Push immutable images to GitHub Container Registry.
- Require an operator-approved production environment before deployment.
- Deploy through restricted SSH, pull the exact image digest, run migrations as a one-off job, perform health checks, and roll back application code if health checks fail.

AWS deployment must use a non-root IAM identity or GitHub OIDC role with least privilege. The currently authenticated AWS root session must not be used for CDK deployment.

The optional AWS IaC/Agent Toolkit MCP may assist developers with reviewed plans and diagnostics, but it is not a runtime dependency or DDoS control and receives no autonomous production-change authority.

## 8. Security, Privacy, and Operational Controls

### Application security

- Deny-by-default RBAC on every protected route.
- Organization and resource ownership checked in every shelter query.
- Tests specifically target IDOR and cross-tenant access.
- Exact CORS allowlist.
- Secure headers: CSP, HSTS, `X-Content-Type-Options`, and restrictive referrer policy.
- Request/body-size limits at WAF, Caddy, and FastAPI.
- Rate limiting at both WAF and application layers for sensitive operations.
- Parameterized database access through SQLAlchemy.
- Neutral error responses that do not disclose whether a person exists.
- Dependency and container vulnerability scanning.
- Annual penetration test before broader rollout.

### Audit and abuse monitoring

Audit:

- Identity reviews and merges.
- QR creation, redemption, expiration, and failures.
- Every cross-shelter history access.
- Pet and custody-event creation.
- Corrections and disputes.
- Staff-role changes.
- Administrative and security-sensitive actions.

Alert on:

- Repeated invalid or expired QR redemption.
- Excessive owner lookups by one staff account or shelter.
- Cross-tenant authorization failures.
- Persona or Clerk webhook signature failures.
- Identity-review backlog.
- Application or database health failures.
- Disk, memory, CPU, certificate, backup, and migration failures.
- Unexpected WAF blocks or traffic spikes.

### Privacy and fairness

- Collect only data required to establish identity and factual custody history.
- Use owner-generated QR authorization instead of global people search.
- Show owners the same factual history generally made available to shelters.
- Provide a dispute and correction process.
- Clearly label source shelter and record provenance.
- Do not infer owner quality from surrender counts.
- Do not include criminal, credit, income, landlord, disability, medical, or protected-trait screening in the MVP.
- Do not market Fido as a consumer score or guaranteed fraud-prevention system.
- Complete U.S. privacy, biometric-data, retention, terms, shelter-agreement, and potential FCRA review with counsel before production use.

## 9. Verification and Acceptance Tests

### Authentication and authorization

- Owner email-code login succeeds and no password path is exposed.
- Expired, malformed, wrong-audience, or wrong-issuer Clerk tokens are rejected.
- Each shelter role receives only its permitted operations.
- A staff member cannot access another organization's pets or disputes by changing an ID.
- Removing a Clerk organization member immediately prevents new access.
- Platform-admin endpoints reject shelter administrators.

### Persona and account fraud scenarios

- Approved Persona inquiry links the Clerk account to a canonical person.
- Browser completion without a valid signed webhook does not approve identity.
- Invalid, stale, replayed, or duplicate Persona webhooks are handled safely.
- A second account using the same driver's license does not receive a fresh person.
- A second account using a passport that Persona connects to the prior person routes to recovery/review and retains the same history.
- Name/DOB similarity without strong Persona evidence does not auto-merge people.
- Matching details with a conflicting portrait routes to manual review.
- Legal-name-change and multiple-document cases preserve one canonical history after review.
- Consolidation failure leaves both records safely in review and does not lose history.
- Persona downtime leaves inquiries pending and retryable.

### QR lookup

- Only an approved owner can generate a token.
- QR payload contains no personal data.
- Token expires after five minutes.
- Token is single use even under simultaneous redemption attempts.
- Redemption is bound to the authenticated shelter and staff member.
- Another shelter cannot reuse the resulting lookup session.
- Session expires after 30 minutes.
- Owner can see the access in their access log.
- Raw token never appears in application logs or database storage.

### Custody history

- Adoption, return, surrender, reclaim, foster, and transfer events append correctly.
- Duplicate idempotency keys do not create duplicate events.
- Existing events cannot be updated or deleted by API or runtime DB role.
- Correction creates a linked append-only event.
- Owner history spans participating shelters after authorized lookup.
- One shelter cannot correct another shelter's record.
- Dispute resolution preserves the original event and displays the correction.
- No endpoint produces a suitability score or recommendation.

### Security testing

- Automated IDOR and tenant-boundary tests pass.
- SQL injection, XSS, CSRF-relevant flows, oversized bodies, and malformed JSON are rejected safely.
- CSP works with required Clerk and Persona endpoints and blocks unapproved sources.
- Caddy rejects direct-origin requests missing the CloudFront header.
- WAF rate-based and managed rules are tested in count mode before blocking.
- SSH password/root access fails while authorized key access works.
- No secrets appear in source, images, frontend bundles, build logs, CDK output, or application logs.
- Containers run non-root and expose only expected ports.

### Reliability and operations

- Fresh environment can be recreated from CDK and documented bootstrap steps.
- `cdk synth --strict`, `cdk diff`, and `cdk-nag` pass.
- Database is unreachable publicly.
- Migrations work on an empty database and upgrade a populated staging database.
- Backup restoration is demonstrated into a separate test database.
- A failed deployment leaves or restores the previous healthy application image.
- Readiness fails when PostgreSQL is unavailable; liveness remains semantically correct.
- CloudFront does not cache authenticated API or webhook responses.
- Alarms fire in controlled tests.
- The 1 GB instance passes realistic concurrent owner/shelter smoke tests without sustained swapping or out-of-memory termination.

### User acceptance

- Owner completes registration, Persona verification, QR generation, shelter lookup, history review, and dispute submission.
- Shelter creates a pet, redeems a QR, records an adoption, records a return, and corrects an error.
- Owner sees the new history and correction with clear provenance.
- A second participating shelter sees the factual history only after a new owner-authorized lookup.
- Interface works with keyboard navigation, common mobile sizes, and WCAG AA contrast.

## 10. Assumptions and Defaults

- Initial deployment is a U.S.-only pilot.
- One production region is used initially, preferably the region containing the current Lightsail resources.
- Lightsail Managed PostgreSQL is private, standard/non-HA, and approximately $15/month.
- The application instance is Lightsail `micro_3_0`, 1 GB RAM, approximately $7/month.
- CloudFront, WAF, Route 53, storage, snapshots, bandwidth, and Persona fees are additional.
- Downtime during a database failure is accepted for the lean pilot.
- Persona, not Plaid or Stripe Identity, is the identity-proofing provider.
- Clerk email-code authentication is the owner authentication method.
- Each shelter maps to one Clerk Organization.
- The MVP supports shelter operations and an owner portal, not public pet discovery, payments, contracts/e-signatures, automated suitability decisions, or shelter billing.
- Persona feature availability and pricing are validated during trial before production commitment.
- Legal and privacy review is mandatory before real shelter or owner data is loaded.

## 11. Implementation Checklist

No item below starts until the user explicitly approves this plan. Later approval of one stage does not authorize destructive production actions in another stage.

- [ ] Record explicit user approval and define the authorized implementation stage.
- [ ] Clone `Herxity/fido-app` and create the monorepo structure for frontend, backend, infrastructure, and documentation.
- [ ] Add contribution guidance, environment templates, secret-handling rules, architecture decision records, and threat model.
- [ ] Scaffold FastAPI, React/TypeScript/Vite, Docker Compose, PostgreSQL development environment, and pinned dependencies.
- [ ] Configure linting, formatting checks, type checks, tests, security scans, and GitHub Actions.
- [ ] Create the initial SQLAlchemy models and Alembic migrations.
- [ ] Implement Clerk JWT verification, email-code owner flow, organization roles, and signed Clerk webhooks.
- [ ] Configure Persona sandbox templates, inquiry pre-creation, Embedded Flow, Workflows, Repeat checks, Cases, and signed webhooks.
- [ ] Implement canonical people, account linking, manual review, account recovery, and Persona consolidation.
- [ ] Implement pet registry and append-only custody events with idempotency and corrections.
- [ ] Implement short-lived QR tokens, redemption, lookup sessions, owner access logs, and anti-enumeration controls.
- [ ] Implement dispute creation, shelter review, platform escalation, and correction linkage.
- [ ] Implement structured audit logs, retention jobs, redaction, rate limits, and security alerts.
- [ ] Build the owner verification, history, QR, access-log, and dispute interfaces.
- [ ] Build the friendly shelter workspace, pet registry, care-journey timeline, event workflow, and dispute queue.
- [ ] Generate and drift-check the TypeScript API client from FastAPI OpenAPI.
- [ ] Create the protected CDK stateful stack for private Lightsail PostgreSQL.
- [ ] Create the CDK application/edge stack for the 1 GB Lightsail instance, static IP, DNS, CloudFront, WAF, firewall, backups, and alarms.
- [ ] Create a non-root least-privilege AWS deployment identity; do not deploy using the AWS root session.
- [ ] Harden the new host, install the container runtime and Caddy, configure origin TLS, and place secrets in the protected environment file.
- [ ] Deploy first to a non-production configuration with Clerk and Persona sandbox tenants.
- [ ] Run all automated, security, restore, performance, and user-acceptance tests.
- [ ] Validate WAF rules in count mode and correct false positives before enabling block mode.
- [ ] Complete privacy, biometric, retention, shelter-agreement, and FCRA applicability review.
- [ ] Request separate user approval for production deployment and DNS cutover.
- [ ] Deploy the exact approved image digest, run migrations, verify health, and complete production smoke tests.
- [ ] Monitor the new environment through the agreed stabilization window.
- [ ] Request separate user approval before retiring or materially changing the existing Lightsail instance.

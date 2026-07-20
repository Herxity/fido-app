# Threat model

## Assets and boundaries

Protected assets are canonical identity links, custody history, disputes, audit records, QR lookup capability, provider secrets, database credentials, and deployment access. Trust boundaries exist at the browser, CloudFront/WAF, Caddy origin, FastAPI, Clerk and Persona webhooks/APIs, PostgreSQL, GitHub Actions, and SSH.

## Principal threats and controls

| Threat | Primary controls | Verification |
|---|---|---|
| Fresh account or alternate ID hides history | Canonical person model, Persona Repeat/Workflow/Case signals, consolidation, manual review | Identity and provider tests |
| Cross-shelter IDOR | Clerk organization/role enforcement, server-derived shelter, shelter-bound lookup session | Tenant-boundary tests |
| QR theft or replay | Opaque hashed token, five-minute TTL, atomic single use, 30-minute bound session | Concurrent redemption tests |
| History tampering | Append-only API, correction linkage, runtime-role trigger, audit records | API and PostgreSQL trigger tests |
| Forged provider webhook | Raw-body HMAC verification, timestamp tolerance, idempotency, Clerk JWT validation | Security tests |
| Direct-origin or volumetric abuse | Secret CloudFront origin header, TLS, Shield Standard, WAF managed/rate rules, app limits | Origin and WAF tests |
| Credential theft | Root-disabled key-only SSH, source CIDR, non-root containers, OIDC deploy role, protected env file | Host and workflow checks |
| Injection or malicious content | Typed validation, ORM parameters, body limits, neutral text rendering, CSP/security headers | API and browser tests |
| Sensitive-data disclosure | Data minimization, structured-log redaction, no raw provider payload storage, secret scanning | Tests and repository scan |
| Destructive infrastructure change | Separate stateful stack, retain policies, termination protection, CDK diff and approvals | CDK tests and deployment record |

## Residual risks

Persona configuration quality, reviewer mistakes, shelter misuse, single-node availability, and legal obligations cannot be solved solely in code. Production requires provider sandbox evidence, staff procedures, incident response, access reviews, restore exercises, and legal/privacy sign-off.

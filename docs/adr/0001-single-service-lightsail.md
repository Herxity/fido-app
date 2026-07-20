# ADR 0001: Single-service Lightsail architecture

Status: accepted for the pilot.

Fido uses one FastAPI monolith on one Lightsail instance, a private Lightsail managed PostgreSQL database, a static React bundle served by Caddy, and CloudFront/WAF at the edge. This minimizes operational surface while retaining a clear path to scale the service later. Stateful resources are isolated in a termination-protected CDK stack with retain policies.

The tradeoff is a single application host and non-HA database. Automated snapshots, health alarms, digest-pinned rollback, and a tested restore runbook mitigate but do not eliminate pilot downtime.

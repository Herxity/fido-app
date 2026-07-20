# Fido production delivery

The production host runs only two containers: the FastAPI image and Caddy. React is built in CI and installed as a checksum-verified release artifact. PostgreSQL remains an AWS-managed private Lightsail database.

## One-time setup

1. Deploy CDK only after reviewing `npm run synth` and `npx cdk diff`. Pass `SshAllowedCidr`, a comment-free SSH public key, and a 32+ character `OriginVerifyToken`. WAF stays in count mode unless CDK context `wafBlockMode=true` is explicitly supplied after log review.
2. Run `sudo bash deploy/bootstrap-host.sh YOUR.PUBLIC.IP/32`. Supply additional comma-separated CIDRs if required. Keep the active SSH session open until a second key-only session succeeds.
3. Copy `.env.production.example` to `/etc/fido/fido.env`, populate it out of band, then set `root:root` ownership and mode `0600`. `BACKEND_IMAGE` and `FIDO_RELEASE_DIR` in that file are placeholders overridden by each deployment; `CADDY_IMAGE` must be a reviewed digest.
4. As the Lightsail database master, run `bootstrap-db.sql` before and after the first Alembic migration. Pass `migrator_password` and `runtime_password` as psql variables from a protected environment without shell tracing. The first run creates the roles/schema defaults; the second grants current tables and installs the custody-event mutation trigger. Configure Alembic with `fido_migrator` and the application with `fido_runtime`.
5. Configure GitHub’s `production` environment with required reviewers, `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `DEPLOY_USER`, `SSH_PRIVATE_KEY`, and `SSH_KNOWN_HOSTS`. The OIDC role trust must restrict `sub` to `repo:Herxity/fido-app:environment:production`; it only needs `cloudformation:DescribeStacks` for `fido-app-edge`. No static AWS key is used.

The database password cannot be emitted by the Lightsail CloudFormation resource. Retrieve and rotate it through an approved operator workflow, create a least-privilege runtime database user, and write only that runtime URL to the protected host environment file.

To rotate application database passwords, generate new random values, rerun `bootstrap-db.sql` during a maintenance window, update `/etc/fido/fido.env` through the protected operator channel, and restart the backend. Never place password values in command history, CI logs, the repository, or a process argument on a shared host. The runtime role has DML access but no DDL; a database trigger additionally rejects its updates and deletes against `custody_events`.

## Deployment and rollback

The deploy workflow builds the backend image, pins it by registry digest, builds the frontend archive, records its SHA-256, resolves the static IP through AWS OIDC, and invokes `deploy.sh` over host-key-pinned SSH. The script validates image digests, runs `alembic upgrade head`, replaces containers, and requires readiness before recording the release.

If readiness fails, the previous image and static release directory are restored automatically. Schema migrations are not reversed, so migrations must be backward-compatible with at least one prior application release. For manual rollback, rerun `deploy.sh` using the prior commit’s frontend archive and backend digest from GitHub Actions.

## Operations

- Check status: `sudo docker compose -p fido -f /opt/fido/releases/COMMIT/docker-compose.prod.yml ps`
- Inspect logs: `sudo docker compose -p fido -f /opt/fido/releases/COMMIT/docker-compose.prod.yml logs --since 30m`
- Verify origin rejection: a direct request without `X-Fido-Origin-Verify` must return 403.
- Verify edge health through the CloudFront/application URL after every release.
- Test database restore into a separate database before relying on backups.
- Review WAF sampled requests in count mode before enabling block mode.

CloudFormation cannot output the Lightsail database endpoint, Lightsail alarms have no notification target until an account notification contact is configured, and the public Lightsail IP remains a volumetric-attack surface even when Caddy rejects requests that bypass CloudFront.

The pinned CDK toolchain is build-only (`devDependencies`) and is never copied into either runtime container. As of this lockfile, a full development audit reports the upstream `aws-cdk-lib` bundled `brace-expansion` advisory GHSA-3jxr-9vmj-r5cp; the current compatible CDK upgrade does not remove that bundled copy. `npm audit --omit=dev` is clean and enforced in CI. Recheck the advisory on each pinned CDK upgrade.
